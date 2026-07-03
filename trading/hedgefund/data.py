"""CSV cache loading and price panel construction.

Cache layout: ``hedgefund/data/<SYMBOL>.csv`` with columns
``date,open,high,low,close,volume`` (full) or ``date,close,volume`` (light).
Loaders tolerate both; when OHLC is missing the high/low panels are None and
downstream code falls back to close-to-close proxies for ATR-style measures.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@dataclass
class PricePanel:
    """Aligned wide panels: index = trading dates, columns = symbols."""

    close: pd.DataFrame
    volume: pd.DataFrame
    high: pd.DataFrame | None = None
    low: pd.DataFrame | None = None

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.close.index

    def true_range(self) -> pd.DataFrame:
        """True range; falls back to |ΔC| when highs/lows are unavailable."""
        prev_close = self.close.shift(1)
        if self.high is not None and self.low is not None:
            a = self.high - self.low
            b = (self.high - prev_close).abs()
            c = (self.low - prev_close).abs()
            return pd.concat([a, b, c], keys=list("abc")).groupby(level=1).max()
        return (self.close - prev_close).abs()

    def atr(self, window: int = 20) -> pd.DataFrame:
        return self.true_range().rolling(window).mean()


def load_symbol(symbol: str, data_dir: str = DATA_DIR) -> pd.DataFrame:
    path = os.path.join(data_dir, f"{symbol}.csv")
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    # Defend against duplicate rows from chunked pulls.
    df = df[~df.index.duplicated(keep="last")]
    return df


def load_panel(
    symbols: list[str],
    data_dir: str = DATA_DIR,
    start: str | None = None,
    end: str | None = None,
) -> PricePanel:
    closes, volumes, highs, lows = {}, {}, {}, {}
    have_hl = True
    for sym in symbols:
        path = os.path.join(data_dir, f"{sym}.csv")
        if not os.path.exists(path):
            continue  # late IPOs / missing data enter point-in-time or not at all
        df = load_symbol(sym, data_dir)
        closes[sym] = df["close"]
        volumes[sym] = df.get("volume", pd.Series(np.nan, index=df.index))
        if "high" in df.columns and "low" in df.columns:
            highs[sym] = df["high"]
            lows[sym] = df["low"]
        else:
            have_hl = False
    if not closes:
        raise FileNotFoundError(
            f"no cached CSVs found in {data_dir}; run the data ingest first"
        )

    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(volumes).reindex(close.index)
    # Align to equity trading days: drop rows where every equity is NaN
    # (crypto trades weekends; those rows would poison rolling windows).
    equity_cols = [c for c in close.columns if c not in ("BTCUSD",)]
    if equity_cols:
        mask = close[equity_cols].notna().any(axis=1)
        close, volume = close[mask], volume[mask]
    # Weekend BTC prices collapse onto trading days via ffill after masking.
    close = close.ffill()

    if start:
        close, volume = close.loc[start:], volume.loc[start:]
    if end:
        close, volume = close.loc[:end], volume.loc[:end]

    high = low = None
    if have_hl and highs:
        high = pd.DataFrame(highs).reindex(close.index)
        low = pd.DataFrame(lows).reindex(close.index)

    return PricePanel(close=close, volume=volume, high=high, low=low)


def cache_status(symbols: list[str], data_dir: str = DATA_DIR) -> pd.DataFrame:
    """Coverage report used by the CLI and the ingest step."""
    rows = []
    for sym in symbols:
        path = os.path.join(data_dir, f"{sym}.csv")
        if os.path.exists(path):
            df = load_symbol(sym, data_dir)
            rows.append(
                {
                    "symbol": sym,
                    "rows": len(df),
                    "first": df.index.min().date(),
                    "last": df.index.max().date(),
                }
            )
        else:
            rows.append({"symbol": sym, "rows": 0, "first": None, "last": None})
    return pd.DataFrame(rows).set_index("symbol")
