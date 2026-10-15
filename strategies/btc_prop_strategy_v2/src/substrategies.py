"""Sub-strategy signal generators. Each returns a DataFrame of signal columns.

Signals computed on bar t close; the backtester executes at bar t+1 open
(look-ahead control per PLAN.md).

Funding Farmer is a stub: no funding-rate data sourced in this environment
(see RESEARCH.md / Data/README.md), so it emits no signals and its 20%
allocation is renormalized across the other two sub-strategies.
"""
import numpy as np
import pandas as pd


def trend_rider_signals(df: pd.DataFrame, adx_threshold: float) -> pd.DataFrame:
    """9/21 EMA cross + ADX gate. Long on bullish cross, short on bearish cross.
    Exit on opposite cross (backtester also applies ATR trailing stop)."""
    bull = df["ema_fast"] > df["ema_slow"]
    cross_up = bull & ~bull.shift(1).fillna(False)
    cross_down = ~bull & bull.shift(1).fillna(True)
    trending = df["adx"] > adx_threshold
    return pd.DataFrame({
        "tr_long_entry": cross_up & trending,
        "tr_short_entry": cross_down & trending,
        "tr_long_exit": cross_down,
        "tr_short_exit": cross_up,
    }, index=df.index)


def range_hunter_signals(df: pd.DataFrame, rsi_oversold: float, rsi_overbought: float,
                         adx_max: float, volume_spike_multiple: float) -> pd.DataFrame:
    """RSI(2) extreme + BB outer band touch + ADX<max, volume confirmation hard gate
    (per config: EDA found raw RSI(2) extremes fire 55% of days)."""
    ranging = df["adx"] < adx_max
    vol_ok = df["volume"] > volume_spike_multiple * df["vol_ma50"]
    long_sig = (df["rsi2"] < rsi_oversold) & (df["close"] < df["bb_lower"]) & ranging & vol_ok
    short_sig = (df["rsi2"] > rsi_overbought) & (df["close"] > df["bb_upper"]) & ranging & vol_ok
    return pd.DataFrame({
        "rh_long_entry": long_sig,
        "rh_short_entry": short_sig,
        "rh_long_exit": df["rsi2"] > 50,
        "rh_short_exit": df["rsi2"] < 50,
    }, index=df.index)


def dcb_signals(df: pd.DataFrame, min_bounce_gain_pct: float = 15.0,
                dist_to_200dma_pct: float = 5.0) -> pd.DataFrame:
    """DCB-short overlay, price-based subset of the 5 spec'd signals (SOPR/funding/
    LTH signals need unsourced data). Active only in confirmed bear (close < 365DMA).

    Short when: bear regime AND price bounced >= min_bounce_gain_pct off its 20-day
    low AND price within dist% below a declining 200DMA."""
    bear = df["close"] < df["ma365"]
    bounce_pct = (df["close"] / df["low20"] - 1) * 100
    bounced = bounce_pct >= min_bounce_gain_pct
    below_declining_200 = (
        (df["close"] < df["ma200"])
        & (df["ma200_slope"] < 0)
        & (df["close"] > df["ma200"] * (1 - dist_to_200dma_pct / 100))
    )
    entry = bear & bounced & below_declining_200
    # exit: bounce retraced 38.2% (backtester computes per-trade target) or regime flips
    return pd.DataFrame({
        "dcb_short_entry": entry,
        "dcb_regime_exit": ~bear,
        "dcb_bounce_pct": bounce_pct,
    }, index=df.index)


def funding_farmer_signals(df: pd.DataFrame) -> pd.DataFrame:
    """STUB -- funding-rate data not sourced in this environment. Zero signals."""
    false_col = pd.Series(False, index=df.index)
    return pd.DataFrame({
        "ff_long_entry": false_col,
        "ff_short_entry": false_col,
    }, index=df.index)
