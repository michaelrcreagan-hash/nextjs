"""Outperformer identifier: 0-100 conviction score, tiering, asymmetry flags.

Security Selector layer. Scores every name every day (vectorized) so the
backtester can rebalance on any schedule and the live screener can rank the
universe as of today.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import PricePanel
from .indicators import (
    bollinger_bandwidth,
    ema,
    high_52w_proximity,
    macd_hist,
    relative_strength,
    rolling_percentile_rank,
    rsi,
    rvol,
    sma,
)


@dataclass
class SignalParams:
    rs_short: int = 63           # ~3 months
    rs_long: int = 126           # ~6 months
    rsi_lo: float = 45.0         # entry sweet spot band
    rsi_hi: float = 70.0
    hi52_near: float = 0.95      # within 5% of 52w high
    hi52_ok: float = 0.85        # within 15%
    rvol_lo: float = 1.2         # volume confirmation band
    rvol_hi: float = 3.0
    squeeze_pct: float = 0.20    # bandwidth percentile for asymmetry flag
    # component weights, sum = 100
    w_rs_short: float = 20.0
    w_rs_long: float = 20.0
    w_ema_stack: float = 15.0
    w_rsi_band: float = 10.0
    w_macd: float = 10.0
    w_rvol: float = 10.0
    w_hi52: float = 15.0
    # tier cutoffs on the 0-100 score
    platinum: float = 85.0
    gold: float = 70.0
    silver: float = 55.0


@dataclass
class SignalSet:
    score: pd.DataFrame          # time x ticker, 0-100
    trend_gate: pd.DataFrame     # bool: price>200sma & 50sma>200sma
    asymmetric: pd.DataFrame     # bool: squeeze + trend + near high
    components: dict


def compute_signals(
    panel: PricePanel,
    universe: list[str],
    params: SignalParams | None = None,
) -> SignalSet:
    p = params or SignalParams()
    cols = [c for c in universe if c in panel.close.columns]
    close = panel.close[cols]
    volume = panel.volume[cols]
    smh = panel.close["SMH"]
    spy = panel.close["SPY"]

    ma50, ma200 = sma(close, 50), sma(close, 200)
    trend_gate = (close > ma200) & (ma50 > ma200)

    # Relative strength blended vs SMH and SPY, ranked cross-sectionally so
    # the score always identifies *relative* outperformers.
    rs_s = (
        relative_strength(close, smh, p.rs_short)
        + relative_strength(close, spy, p.rs_short)
    ) / 2
    rs_l = (
        relative_strength(close, smh, p.rs_long)
        + relative_strength(close, spy, p.rs_long)
    ) / 2
    rs_s_rank = rs_s.rank(axis=1, pct=True)
    rs_l_rank = rs_l.rank(axis=1, pct=True)

    e8, e21, e50 = ema(close, 8), ema(close, 21), ema(close, 50)
    ema_stack = (close > e8) & (e8 > e21) & (e21 > e50)

    r = rsi(close, 14)
    rsi_band = (r >= p.rsi_lo) & (r <= p.rsi_hi)

    hist = macd_hist(close)
    macd_up = (hist > 0) & (hist > hist.shift(1))

    rv = rvol(volume, 20)
    rvol_band = (rv >= p.rvol_lo) & (rv <= p.rvol_hi)

    hi52 = high_52w_proximity(close)
    hi52_score = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    hi52_score[hi52 >= p.hi52_ok] = 0.5
    hi52_score[hi52 >= p.hi52_near] = 1.0

    score = (
        rs_s_rank * p.w_rs_short
        + rs_l_rank * p.w_rs_long
        + ema_stack * p.w_ema_stack
        + rsi_band * p.w_rsi_band
        + macd_up * p.w_macd
        + rvol_band * p.w_rvol
        + hi52_score * p.w_hi52
    )
    # Trend gate is a hard filter, not a component: names below it can't be
    # bought no matter the score. Zeroing keeps ranking honest in reports.
    score = score.where(trend_gate, other=score * 0.25)
    score = score.where(close.notna())

    # Asymmetry: volatility compression while the trend is intact and price
    # is coiled near the highs — breakout carries outsized reward-to-risk.
    bw = bollinger_bandwidth(close)
    squeeze = rolling_percentile_rank(bw, 252) < p.squeeze_pct
    asymmetric = squeeze & trend_gate & (hi52 >= p.hi52_ok)

    return SignalSet(
        score=score,
        trend_gate=trend_gate,
        asymmetric=asymmetric,
        components={
            "rs_short_rank": rs_s_rank,
            "rs_long_rank": rs_l_rank,
            "ema_stack": ema_stack,
            "rsi": r,
            "macd_up": macd_up,
            "rvol": rv,
            "hi52": hi52,
            "squeeze": squeeze,
        },
    )


def tier_of(score: float, p: SignalParams) -> str:
    if np.isnan(score):
        return "n/a"
    if score >= p.platinum:
        return "Platinum"
    if score >= p.gold:
        return "Gold"
    if score >= p.silver:
        return "Silver"
    return "Bronze"
