"""Vectorized indicator primitives shared by regime, signals, and strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(df: pd.DataFrame | pd.Series, span: int):
    return df.ewm(span=span, adjust=False).mean()


def sma(df: pd.DataFrame | pd.Series, window: int):
    return df.rolling(window).mean()


def rsi(close: pd.DataFrame | pd.Series, window: int = 14):
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def macd_hist(close: pd.DataFrame | pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def bollinger_bandwidth(close: pd.DataFrame | pd.Series, window=20, num_std=2.0):
    mid = sma(close, window)
    sd = close.rolling(window).std()
    return (2 * num_std * sd) / mid


def rolling_percentile_rank(df: pd.DataFrame | pd.Series, window: int):
    """Percentile of the latest value within its trailing window, in [0, 1]."""
    return df.rolling(window).rank(pct=True)


def relative_strength(close: pd.DataFrame, benchmark: pd.Series, lookback: int):
    """Return of each column minus benchmark return over ``lookback`` days."""
    asset_ret = close / close.shift(lookback) - 1
    bench_ret = benchmark / benchmark.shift(lookback) - 1
    return asset_ret.sub(bench_ret, axis=0)


def rvol(volume: pd.DataFrame | pd.Series, window: int = 20):
    return volume / volume.rolling(window).mean()


def pct_above(close: pd.DataFrame, ma: pd.DataFrame) -> pd.Series:
    """Cross-sectional breadth: fraction of names above their own MA."""
    valid = close.notna() & ma.notna()
    above = (close > ma) & valid
    return above.sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)


def high_52w_proximity(close: pd.DataFrame | pd.Series, window: int = 252):
    """close / trailing 52-week max — 1.0 means at the high."""
    return close / close.rolling(window, min_periods=60).max()
