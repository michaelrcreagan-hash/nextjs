"""
hermes_agent -- baseline entry signal (mechanical core only)

This is the step-5 baseline's entry rule and NOTHING more: no confluence
score, no F/T/S/M, no features, no ML, no LLM. Those arrive at steps 6-9 and
each has to beat what this produces.

The rule is deliberately the plainest cross-sectional momentum filter that
could be called a strategy, because the point of step 5 is to measure what the
REGIME + EXIT machinery contributes. A clever entry rule here would confound
that measurement -- any edge found could be the entry rather than the core,
and the ablation at step 8 would have nothing clean to ablate against.

    eligible[t, s]  <=>  mom[t-1, s] > 0  AND  close[t-1, s] > SMA100[t-1, s]
    ranking          =   mom[t-1, s], descending

All inputs are shift1()'d: the decision at bar t uses only bars < t.
"""

from __future__ import annotations

import numpy as np

from .data_loader import rolling_mean, shift1


def momentum_signals(close: np.ndarray,
                     mom_lookback: int = 50,
                     trend_lookback: int = 100) -> dict:
    """
    Returns:
        eligible : bool    (n_bars, n_symbols)  entry permitted
        rank_key : float64 (n_bars, n_symbols)  higher = preferred; -inf if not eligible
    """
    prev = shift1(close)

    mom = np.full_like(close, np.nan)
    mom[mom_lookback:] = close[mom_lookback:] / close[:-mom_lookback] - 1.0
    mom = shift1(mom)

    sma = shift1(rolling_mean(close, trend_lookback))

    ok = ~np.isnan(mom) & ~np.isnan(sma) & ~np.isnan(prev)
    eligible = ok & (mom > 0.0) & (prev > sma)

    rank_key = np.where(eligible, mom, -np.inf)

    return {
        "eligible": np.ascontiguousarray(eligible),
        "rank_key": np.ascontiguousarray(rank_key, dtype=np.float64),
        "mom": mom,
    }
