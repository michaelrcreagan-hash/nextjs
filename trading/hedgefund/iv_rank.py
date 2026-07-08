"""IV-Rank decision tree — options structure selector.

The validated options desk (options_sim.py) runs one structure (LEAPS
diagonal / PMCC) unconditionally because that's what walk-forward
validation supported (see REPORT.md). This module adds the broader
selector from the strategy notes as a decision-support layer for the
options_analyst LLM agent: given a volatility regime, which STRUCTURE
FAMILY should even be on the table, and what ATR-based strikes does it
imply.

No real options chain exists in this environment, so "IV Rank" here is
a realized-vol percentile proxy (HV rank), same convention as
options_sim.py's ``iv_premium`` knob — clearly not the same number a
live IV-rank tool would show, but directionally consistent (elevated
realized vol correlates with elevated IV).

Selector rules (from the "Quick Reference" note):
    IV Rank > 60%   -> sell premium (credit spread / iron condor)
                       short strike ~1.5x ATR, long ~0.5x ATR beyond short
    IV Rank 30-60%  -> buy debit spreads
                       long ~1.0x ATR, short ~2.0x ATR
    IV Rank < 30%   -> avoid selling; long strangle only with a catalyst
                       strikes ~2.5x ATR
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class IVRankParams:
    hv_window: int = 20
    rank_lookback: int = 252
    high_band: float = 60.0
    low_band: float = 30.0


def hv_rank(close: pd.Series, params: IVRankParams | None = None) -> pd.Series:
    """Trailing-year percentile rank of 20-day realized vol — the IV-rank
    proxy. 0 = cheapest vol in a year, 100 = richest."""
    p = params or IVRankParams()
    logret = np.log(close / close.shift(1))
    hv = logret.rolling(p.hv_window).std() * math.sqrt(TRADING_DAYS)
    return hv.rolling(p.rank_lookback).rank(pct=True) * 100


def select_structure(rank: float, params: IVRankParams | None = None) -> dict:
    """Structure recommendation + ATR strike multiples for a given IV rank."""
    p = params or IVRankParams()
    if np.isnan(rank):
        return {"rank": rank, "structure": "n/a", "rationale": "insufficient history"}
    if rank > p.high_band:
        return {
            "rank": round(rank, 1),
            "structure": "credit spread / iron condor (sell premium)",
            "short_atr": 1.5,
            "long_atr": 2.0,  # 0.5x beyond the short
            "rationale": f"IV rank {rank:.0f} > {p.high_band:.0f} — premium is rich, sell it",
        }
    if rank >= p.low_band:
        return {
            "rank": round(rank, 1),
            "structure": "debit spread (buy directional)",
            "long_atr": 1.0,
            "short_atr": 2.0,
            "rationale": f"IV rank {rank:.0f} in [{p.low_band:.0f},{p.high_band:.0f}] — "
                          f"defined-risk directional bet, no strong edge either way on premium",
        }
    return {
        "rank": round(rank, 1),
        "structure": "avoid selling; long strangle only with a confirmed catalyst",
        "strike_atr": 2.5,
        "rationale": f"IV rank {rank:.0f} < {p.low_band:.0f} — premium is cheap, "
                      f"selling it is a poor risk/reward",
    }


def strikes_from_atr(spot: float, atr: float, multiples: dict) -> dict:
    """Convert a structure's ATR multiples into actual strike prices."""
    out = {"spot": spot, "atr": atr}
    for key, mult in multiples.items():
        if key.endswith("_atr"):
            leg = key.replace("_atr", "")
            out[f"{leg}_strike_call"] = round(spot + mult * atr, 2)
            out[f"{leg}_strike_put"] = round(spot - mult * atr, 2)
    return out


def latest_structure_selection(
    close: pd.Series, atr: pd.Series, params: IVRankParams | None = None
) -> dict:
    """Convenience: today's rank + structure + strikes for one underlying."""
    p = params or IVRankParams()
    rank_series = hv_rank(close, p)
    day = rank_series.dropna().index[-1] if rank_series.notna().any() else close.index[-1]
    rank = rank_series.get(day, np.nan)
    rec = select_structure(rank, p)
    spot = float(close.loc[day])
    a = float(atr.loc[day]) if day in atr.index and np.isfinite(atr.get(day, np.nan)) else np.nan
    if np.isfinite(a):
        rec.update(strikes_from_atr(spot, a, rec))
    rec["date"] = str(pd.Timestamp(day).date())
    rec["spot"] = spot
    return rec
