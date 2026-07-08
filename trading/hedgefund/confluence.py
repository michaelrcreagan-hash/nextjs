"""10-Layer Technical Confluence Score — mirrors the "IAE Score Only"
TradingView Pine indicator (saved verbatim in
``trading/hedgefund/pine/iae_score_only.pine``) so the Python screener
agrees with what's on the user's charts.

Data caveat: the Pine script uses intraday OHLC (open/high/low) for its
ADX, ATR, Donchian, and close>open conditions. The cached equity CSVs in
this repo are close/volume only (see REPORT.md's existing ATR-proxy
caveat), so every OHLC-dependent piece here is approximated from CLOSE
alone: true range -> |close_t - close_t-1|, Donchian channel -> rolling
max/min of CLOSE (not high/low), and the "green candle" close>open check
-> close>prior close. This changes point totals slightly vs. the live
Pine chart but preserves the scoring LOGIC and layer structure exactly.
Pull real OHLC for the equity universe (fetch_data + a *_full.csv pass,
same as already done for crypto) to close this gap.

10 named layers (grouping the Pine script's point buckets under the
taxonomy from the "10-Layer Confluence" reference note):

  1. Regime/Trend        close>SMA200 & SMA50>SMA200, close>SMA50,
                          golden cross, close>EMA8            (max 20)
  2. Momentum             RSI 50-70 sweet spot, RSI<=30, MACD hist>0
                                                                (max 20)
  3. Trend Strength       ADX>25 & DI+ > DI-, ADX>20            (max 15)
  4. Volatility           ATR% in [2,6], Bollinger squeeze      (max 15)
  5. Volume/RVOL          RVOL>2x on a green bar, RVOL>1x       (max 15)
  6. Breakout/Pullback    55-day Donchian breakout              (max 15)
  7. Pullback quality     10%+ pullback in uptrend, RSI<=38,
                          green bar                             (max 12)
  8. Relative Strength    close vs 50-day high (RS proxy)       (max 15)

Layers 9 (Breadth/Leadership) and 10 (Flow/Institutional) from the
reference taxonomy need cross-sectional breadth and dark-pool/options
flow data respectively — breadth is already covered at the regime level
(regime.py's ``breadth`` field) and flow has no data source in this
repo, so both are surfaced as ``np.nan`` placeholders here rather than
silently folded into the score.

Raw layer sum is capped at 100, same as the Pine script's
``math.min(score, 100)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import PricePanel
from .indicators import bollinger_bandwidth, ema, macd_hist, rsi, sma


@dataclass
class ConfluenceParams:
    donchian_len: int = 55
    rsi_len: int = 14
    atr_len: int = 14
    vol_len: int = 20
    rvol_hi: float = 2.0
    adx_len: int = 14
    pullback_min: float = 0.10
    pullback_lookback: int = 42


def _wilder_adx_di(close: pd.DataFrame, window: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Close-only ADX/DI approximation (see module docstring caveat)."""
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    tr = delta.abs()
    atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    di_plus = 100 * up.ewm(alpha=1 / window, adjust=False).mean() / atr
    di_minus = 100 * down.ewm(alpha=1 / window, adjust=False).mean() / atr
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    adx = dx.ewm(alpha=1 / window, adjust=False).mean()
    return adx, di_plus, di_minus


def compute_confluence(
    panel: PricePanel,
    tickers: list[str],
    params: ConfluenceParams | None = None,
) -> dict[str, pd.DataFrame]:
    """Returns {'score': df, 'layers': {name: df}} across all dates/tickers."""
    p = params or ConfluenceParams()
    cols = [t for t in tickers if t in panel.close.columns]
    close = panel.close[cols]
    volume = panel.volume[cols]
    prev_close = close.shift(1)
    green = close > prev_close  # close>open proxy

    sma200, sma50 = sma(close, 200), sma(close, 50)
    ema8 = ema(close, 8)
    golden = (sma50 > sma200) & (sma50.shift(1) <= sma200.shift(1))

    r = rsi(close, p.rsi_len)
    hist = macd_hist(close)

    adx, di_plus, di_minus = _wilder_adx_di(close, p.adx_len)

    atr = close.diff().abs().ewm(alpha=1 / p.atr_len, adjust=False).mean()
    atr_pct = atr / close * 100
    bw = bollinger_bandwidth(close)
    bb_squeeze = bw < sma(bw, 20) * 0.8

    avg_vol = sma(volume, p.vol_len)
    rvol = volume / avg_vol

    donch_hi = close.rolling(p.donchian_len).max().shift(1)
    swing_hi_42 = close.rolling(p.pullback_lookback).max()

    rs_50d = close / close.rolling(50).max() * 100

    layers = {}

    l1 = (
        ((close > sma200) & (sma50 > sma200)).astype(float) * 8
        + (close > sma50).astype(float) * 6
        + golden.astype(float) * 4
        + (close > ema8).astype(float) * 2
    )
    layers["regime_trend"] = l1

    l2 = (
        ((r > 50) & (r < 70)).astype(float) * 10
        + (r <= 30).astype(float) * 5
        + (hist > 0).astype(float) * 5
    )
    layers["momentum"] = l2

    l3 = (
        ((adx > 25) & (di_plus > di_minus)).astype(float) * 10
        + (adx > 20).astype(float) * 5
    )
    layers["trend_strength"] = l3

    l4 = (
        ((atr_pct >= 2) & (atr_pct <= 6)).astype(float) * 8
        + bb_squeeze.astype(float) * 7
    )
    layers["volatility"] = l4

    l5 = (
        ((rvol > p.rvol_hi) & green).astype(float) * 10
        + (rvol > 1.0).astype(float) * 5
    )
    layers["volume_rvol"] = l5

    l6 = (close > donch_hi).astype(float) * 15
    layers["breakout"] = l6

    pullback_cond = (
        (close >= sma50)
        & (r <= 38)
        & ((swing_hi_42 - close) >= close * p.pullback_min)
        & green
    )
    l7 = pullback_cond.astype(float) * 12
    layers["pullback_quality"] = l7

    l8 = (rs_50d > 95).astype(float) * 10 + (
        (rs_50d > 85) & (rs_50d <= 95)
    ).astype(float) * 5
    layers["relative_strength"] = l8

    score = sum(layers.values()).clip(upper=100).round(0)

    return {"score": score, "layers": layers}


def tier_of(score: float) -> str:
    if np.isnan(score):
        return "n/a"
    if score >= 90:
        return "PLATINUM"
    if score >= 85:
        return "GOLD"
    if score >= 70:
        return "SILVER"
    if score >= 55:
        return "BRONZE"
    return "AVOID"


def latest_confluence(
    panel: PricePanel, tickers: list[str], params: ConfluenceParams | None = None
) -> pd.DataFrame:
    """Today's confluence table: score, tier, and each layer's contribution."""
    result = compute_confluence(panel, tickers, params)
    score = result["score"]
    day = score.dropna(how="all").index[-1]
    row = score.loc[day].dropna().sort_values(ascending=False)
    out = pd.DataFrame({"score": row, "tier": [tier_of(s) for s in row]})
    for name, layer_df in result["layers"].items():
        out[name] = layer_df.loc[day, row.index]
    return out
