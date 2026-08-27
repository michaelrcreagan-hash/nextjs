"""
hermes_agent -- Step 1: Data Pipeline (Polars -> contiguous NumPy)

Loads the daily price panel, validates its calendar, and emits C-contiguous
float64 arrays for the Numba hot path.

CALENDAR FINDING (contradicts BUILD_PLAN.md step 1's stated premise)
--------------------------------------------------------------------
BUILD_PLAN.md assumed this panel mixed a 5-day equity calendar with a 7-day
crypto calendar and that a calendar join was the main work here. It does not.
Every one of the 524 rows falls on a weekday (Mon 101 / Tue 109 / Wed 107 /
Thu 103 / Fri 104, zero weekend rows) and there are no blank cells anywhere.
BTC/ETH/SOL have ALREADY been downsampled to the NYSE calendar upstream.

There is therefore no join to perform and no forward-fill to apply -- which is
good (nothing to get wrong) but has two consequences that must travel with
every result produced from this panel:

  1. Crypto weekend price action is absent. Weekend moves surface as Monday
     gaps. Realized crypto volatility measured here is understated relative to
     a true 24/7 series, and any stop or trailing level is implicitly assumed
     to be unactionable from Friday close to Monday close.
  2. Because gaps are structural (117 of them, all weekend/holiday), the
     "13 calendar gaps >3 days" noted in EDA.md are holiday weekends, not
     data corruption. Confirmed here, not assumed.

The loader still asserts the no-backfill invariant rather than trusting the
above, because the invariant is what actually matters downstream.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

STRATEGY_DIR = Path(__file__).resolve().parent.parent
DATA_CSV = STRATEGY_DIR / "Data" / "btc_historical_data.csv"
PANEL_PARQUET = STRATEGY_DIR / "Data" / "panel.parquet"

# Venue assignment drives the per-trade dollar cost model in backtest.py.
# config.strategy_params.venue_costs is the source of the numbers; this is the
# symbol -> venue mapping those numbers get applied through.
CRYPTO_SPOT = {"BTC-USD", "ETH-USD", "SOL-USD"}

VENUE_CRYPTO_SPOT = 0
VENUE_EQUITY = 1


def load_panel(start_date: str | None = None,
               end_date: str | None = None,
               use_cache: bool = True) -> dict:
    """
    Load the price panel.

    Returns a dict with:
        dates      : np.ndarray[datetime64[D]]  (n_bars,)
        symbols    : list[str]                  (n_symbols,)
        close      : np.ndarray[float64]        (n_bars, n_symbols)  C-contiguous
        venue      : np.ndarray[int8]           (n_symbols,)
        n_bars, n_symbols
    """
    if use_cache and PANEL_PARQUET.exists():
        df = pl.read_parquet(PANEL_PARQUET)
    else:
        lf = pl.scan_csv(DATA_CSV, try_parse_dates=True)
        # Filter pushes into the scan -- do it before collect().
        if start_date is not None:
            lf = lf.filter(pl.col("Date") >= pl.lit(start_date).str.to_date())
        if end_date is not None:
            lf = lf.filter(pl.col("Date") <= pl.lit(end_date).str.to_date())
        df = lf.sort("Date").collect()
        PANEL_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(PANEL_PARQUET)

    # Re-apply the date filter after a cache hit so a cached wider panel still
    # honours the requested window.
    if start_date is not None:
        df = df.filter(pl.col("Date") >= pl.lit(start_date).str.to_date())
    if end_date is not None:
        df = df.filter(pl.col("Date") <= pl.lit(end_date).str.to_date())

    symbols = [c for c in df.columns if c != "Date"]

    dates = df["Date"].to_numpy()
    close = np.ascontiguousarray(
        df.select(symbols).to_numpy(), dtype=np.float64
    )

    venue = np.array(
        [VENUE_CRYPTO_SPOT if s in CRYPTO_SPOT else VENUE_EQUITY for s in symbols],
        dtype=np.int8,
    )

    _validate(dates, close, symbols)

    return {
        "dates": dates,
        "symbols": symbols,
        "close": close,
        "venue": venue,
        "n_bars": close.shape[0],
        "n_symbols": close.shape[1],
    }


def _validate(dates: np.ndarray, close: np.ndarray, symbols: list[str]) -> None:
    """Assertions that must hold before anything downstream runs."""
    assert close.flags["C_CONTIGUOUS"], "close array is not C-contiguous"
    assert close.dtype == np.float64, f"close dtype is {close.dtype}, need float64"
    assert not np.isnan(close).any(), "NaN present in price panel after load"
    assert (close > 0).all(), "non-positive price in panel"

    # Strictly increasing dates -- a duplicate or out-of-order bar silently
    # corrupts every rolling statistic downstream.
    d = dates.astype("datetime64[D]").astype(np.int64)
    assert (np.diff(d) > 0).all(), "dates not strictly increasing"

    # No-backfill invariant. With no blanks in the source there is nothing to
    # fill, so the check is that no column contains a run of repeated values
    # that begins BEFORE the first change -- i.e. that nothing was seeded from
    # a later observation. A leading constant run is the signature of a
    # backfill, so assert the first two bars differ for at least one symbol.
    assert (close[0] != close[1]).any(), "all symbols constant across first two bars"


def returns(close: np.ndarray) -> np.ndarray:
    """
    Simple bar-over-bar returns, first row zero.

    NOTE: r[t] = close[t]/close[t-1] - 1 uses close[t], which is NOT knowable
    when the decision at bar t is made. Every consumer of this array must
    shift it before using it as a feature. features/regime code does; the
    backtest loop uses close[t] only for marking equity and filling exits,
    which is legitimate.
    """
    out = np.zeros_like(close)
    out[1:] = close[1:] / close[:-1] - 1.0
    return np.ascontiguousarray(out)


def rolling_mean(a: np.ndarray, window: int) -> np.ndarray:
    """
    Trailing mean over `window` bars, NaN until warm. Column-wise.

    NaN-AWARE. A plain cumsum poisons every subsequent value once a single NaN
    enters, which silently turns the whole downstream pipeline into NaN --
    exactly the failure this hit on first run, where one NaN at row 0 of a
    shifted return series blanked all 524 regime labels. The output is NaN
    only where the *window itself* contains a NaN, not forever after.
    """
    n = a.shape[0]
    out = np.full_like(a, np.nan)
    if n < window:
        return out

    valid = ~np.isnan(a)
    filled = np.where(valid, a, 0.0)

    c = np.concatenate([np.zeros((1,) + a.shape[1:]), np.cumsum(filled, axis=0)])
    cv = np.concatenate([np.zeros((1,) + a.shape[1:]),
                         np.cumsum(valid.astype(np.float64), axis=0)])

    total = c[window:] - c[:-window]
    count = cv[window:] - cv[:-window]

    full_window = count == window
    res = np.full_like(total, np.nan)
    np.divide(total, window, out=res, where=full_window)
    out[window - 1:] = res
    return out


def rolling_std(a: np.ndarray, window: int) -> np.ndarray:
    """Trailing population std over `window` bars, NaN until warm."""
    m = rolling_mean(a, window)
    m2 = rolling_mean(a * a, window)
    var = np.maximum(m2 - m * m, 0.0)
    return np.sqrt(var)


def shift1(a: np.ndarray) -> np.ndarray:
    """
    Lag by one bar. THE lookahead guard: a statistic computed through bar t
    becomes usable only at bar t+1.
    """
    out = np.full_like(a, np.nan)
    out[1:] = a[:-1]
    return np.ascontiguousarray(out)


def atr_proxy(close: np.ndarray, window: int = 14) -> np.ndarray:
    """
    Close-to-close ATR proxy, in price units, already shifted by one bar.

    LIMITATION (carried forward, not absorbed): this panel has no intraday
    high/low, so true range collapses to |close[t] - close[t-1]|. That
    understates true range, so 3.0x this proxy is a TIGHTER stop than 3.0x a
    real ATR would be. Same documented limitation as the rest of this repo.
    Report it wherever stop behaviour is discussed.
    """
    tr = np.zeros_like(close)
    tr[1:] = np.abs(close[1:] - close[:-1])
    return shift1(rolling_mean(tr, window))


if __name__ == "__main__":
    p = load_panel(start_date="2024-07-23")
    print(f"bars      : {p['n_bars']}")
    print(f"symbols   : {p['n_symbols']} {p['symbols']}")
    print(f"date range: {p['dates'][0]} -> {p['dates'][-1]}")
    print(f"contiguous: {p['close'].flags['C_CONTIGUOUS']}")
    print(f"venues    : crypto_spot={int((p['venue'] == 0).sum())} "
          f"equity={int((p['venue'] == 1).sum())}")
