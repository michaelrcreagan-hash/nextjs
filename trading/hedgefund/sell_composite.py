"""88% Sell Composite — mechanical exit trigger set for open positions.

Five triggers per the strategy note; 3+ triggers = scale 50%, 4+ =
full exit. Only three are computable from cached price/volume data:

  [x] RSI>80 with divergence or declining volume on the rally
  [x] RVOL failure <0.6x near a recent high (breakout that didn't confirm)
  [x] Options-expiry week (3rd Friday) + RSI>72 — OpEx date is a pure
      calendar calculation; the "unusual gamma positioning" half of the
      original trigger isn't, so this is a naive timing proxy
  [ ] Options P/C spike + dark pool distribution — no options-flow or
      dark-pool data source in this repo
  [ ] Hyperscaler CapEx flat/miss + stock >5% off ATH — no earnings/
      capex-calendar data source in this repo

The two unavailable triggers are reported as ``None`` (not ``False``) so
the composite count only reflects what was actually measured — treat any
report showing 3/5 or 4/5 as a LOWER BOUND until those two are wired to
real data (options flow, capex tracking).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass

import pandas as pd

from .data import PricePanel
from .indicators import rsi, rvol as rvol_of


@dataclass
class SellCompositeParams:
    rsi_window: int = 14
    rsi_overbought: float = 80.0
    rsi_opex: float = 72.0
    rvol_window: int = 20
    rvol_fail: float = 0.6
    near_high_pct: float = 0.03  # within 3% of a 20-day high counts as "at the top"
    scale_threshold: int = 3
    exit_threshold: int = 4


def _third_friday(year: int, month: int) -> pd.Timestamp:
    cal = calendar.monthcalendar(year, month)
    fridays = [week[calendar.FRIDAY] for week in cal if week[calendar.FRIDAY] != 0]
    return pd.Timestamp(year=year, month=month, day=fridays[2])


def is_opex_week(day: pd.Timestamp) -> bool:
    tf = _third_friday(day.year, day.month)
    return tf - pd.Timedelta(days=4) <= day <= tf


def compute_sell_composite(
    panel: PricePanel, tickers: list[str], params: SellCompositeParams | None = None
) -> dict[str, pd.DataFrame]:
    p = params or SellCompositeParams()
    cols = [t for t in tickers if t in panel.close.columns]
    close = panel.close[cols]
    volume = panel.volume[cols]

    r = rsi(close, p.rsi_window)
    vol_declining = volume.rolling(5).mean() < volume.rolling(5).mean().shift(5)
    trigger_rsi_div = (r > p.rsi_overbought) & vol_declining

    rv = rvol_of(volume, p.rvol_window)
    near_high = close >= close.rolling(20).max() * (1 - p.near_high_pct)
    trigger_rvol_fail = near_high & (rv < p.rvol_fail)

    opex_mask = pd.Series(
        [is_opex_week(d) for d in close.index], index=close.index
    )
    trigger_opex_rsi = pd.DataFrame(
        {c: (r[c] > p.rsi_opex) & opex_mask for c in cols}
    )

    triggers = {
        "rsi_overbought_declining_volume": trigger_rsi_div,
        "rvol_failure_near_high": trigger_rvol_fail,
        "opex_week_rsi_hot": trigger_opex_rsi,
        "options_flow_dark_pool": None,   # unavailable — no data source
        "capex_miss_off_ath": None,        # unavailable — no data source
    }
    count = sum(t.astype(int) for t in triggers.values() if t is not None)

    return {"triggers": triggers, "count": count}


def sell_action(count: int, p: SellCompositeParams | None = None) -> str:
    p = p or SellCompositeParams()
    if count >= p.exit_threshold:
        return "FULL EXIT"
    if count >= p.scale_threshold:
        return "SCALE 50%"
    return "HOLD"


def latest_sell_signals(
    panel: PricePanel,
    tickers: list[str],
    params: SellCompositeParams | None = None,
) -> pd.DataFrame:
    """Today's sell-composite readout for the given (typically: held)
    tickers. ``count`` counts only the 3 measurable triggers — treat as
    a lower bound (see module docstring)."""
    p = params or SellCompositeParams()
    result = compute_sell_composite(panel, tickers, p)
    day = result["count"].dropna(how="all").index[-1]
    counts = result["count"].loc[day]
    rows = {}
    for t in counts.index:
        rows[t] = {
            "measured_triggers": int(counts[t]),
            "action": sell_action(int(counts[t]), p),
        }
        for name, df in result["triggers"].items():
            rows[t][name] = None if df is None else bool(df.loc[day, t])
    return pd.DataFrame(rows).T
