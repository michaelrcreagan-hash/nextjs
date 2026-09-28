"""Indicator library for btc_prop_strategy_v2. All functions vectorized pandas."""
import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).rolling(period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    tr_smooth = true_range(df).ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / tr_smooth
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / tr_smooth
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def bollinger(series: pd.Series, period: int = 20, stddev: float = 2.0):
    mid = series.rolling(period).mean()
    sd = series.rolling(period).std()
    return mid, mid + stddev * sd, mid - stddev * sd


def enrich(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Add all indicator columns needed by the sub-strategies."""
    out = df.copy()
    tr_cfg = params["trend_rider"]
    rh_cfg = params["range_hunter"]

    out["ema_fast"] = ema(out["close"], tr_cfg["ema_fast"])
    out["ema_slow"] = ema(out["close"], tr_cfg["ema_slow"])
    out["adx"] = adx(out, tr_cfg["adx_period"])
    out["atr"] = atr(out, tr_cfg["atr_period"])
    out["rsi2"] = rsi(out["close"], rh_cfg["rsi_period"])
    out["bb_mid"], out["bb_upper"], out["bb_lower"] = bollinger(
        out["close"], rh_cfg["bb_period"], rh_cfg["bb_stddev"]
    )
    out["vol_ma50"] = sma(out["volume"], 50)
    out["ma200"] = sma(out["close"], 200)
    out["ma365"] = sma(out["close"], 365)
    out["ma200_slope"] = out["ma200"].diff(5)
    out["low20"] = out["low"].rolling(20).min()
    return out
