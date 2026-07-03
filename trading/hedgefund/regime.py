"""Macro regime engine (Chief Macro Officer layer).

Computable from cached prices alone: VIX level, SMH trend, universe breadth,
BTC trend as the liquidity proxy (global liquidity leads risk assets; BTC is
its fastest readout). Emits a daily state and gross-exposure multiplier plus
the two hard kill switches from the strategy docs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .data import PricePanel
from .indicators import pct_above, sma


@dataclass
class RegimeParams:
    vix_calm: float = 17.5
    vix_normal: float = 22.5
    vix_stress: float = 27.5
    vix_kill: float = 30.0        # VIX > 30 -> RISK_OFF for kill_days
    kill_days: int = 2            # "48h minimum"
    breadth_strong: float = 0.60
    breadth_ok: float = 0.40
    breadth_weak: float = 0.25
    # score -> state boundaries
    risk_on_min: int = 5
    mixed_min: int = 2
    caution_min: int = 0
    # gross-exposure multiplier per state
    multipliers: dict = field(
        default_factory=lambda: {
            "RISK_ON": 1.0,
            "MIXED": 0.7,
            "CAUTION": 0.4,
            "RISK_OFF": 0.0,
        }
    )


STATE_ORDER = ["RISK_OFF", "CAUTION", "MIXED", "RISK_ON"]


def compute_regime(
    panel: PricePanel,
    universe: list[str],
    params: RegimeParams | None = None,
) -> pd.DataFrame:
    """Daily regime table: score components, state, exposure multiplier,
    and the no-new-longs flag (SMH < 200-DMA kill switch)."""
    p = params or RegimeParams()
    close = panel.close

    smh = close["SMH"]
    vix = close["VIX"]
    btc = close.get("BTCUSD")

    smh_200 = sma(smh, 200)
    smh_50 = sma(smh, 50)

    uni = close[[c for c in universe if c in close.columns]]
    breadth = pct_above(uni, sma(uni, 200))

    # --- component scores ---
    vix_score = pd.Series(0, index=close.index)
    vix_score[vix < p.vix_calm] = 2
    vix_score[(vix >= p.vix_calm) & (vix < p.vix_normal)] = 1
    vix_score[(vix >= p.vix_normal) & (vix < p.vix_stress)] = 0
    vix_score[vix >= p.vix_stress] = -2

    trend_score = pd.Series(-2, index=close.index)
    trend_score[smh > smh_200] = 1
    trend_score[(smh > smh_200) & (smh > smh_50)] = 2

    breadth_score = pd.Series(0, index=close.index)
    breadth_score[breadth > p.breadth_strong] = 2
    breadth_score[(breadth <= p.breadth_strong) & (breadth > p.breadth_ok)] = 1
    breadth_score[breadth < p.breadth_weak] = -2

    if btc is not None:
        btc_score = (btc > sma(btc, 200)).astype(int) * 2 - 1  # +1 / -1
    else:
        btc_score = pd.Series(0, index=close.index)

    score = vix_score + trend_score + breadth_score + btc_score

    state = pd.Series("RISK_OFF", index=close.index)
    state[score >= p.caution_min] = "CAUTION"
    state[score >= p.mixed_min] = "MIXED"
    state[score >= p.risk_on_min] = "RISK_ON"

    # --- kill switch 1: VIX spike forces RISK_OFF for kill_days ---
    spike = vix > p.vix_kill
    forced = spike.copy()
    for d in range(1, p.kill_days + 1):
        forced |= spike.shift(d).fillna(False)
    state[forced] = "RISK_OFF"

    # --- kill switch 2: SMH below 200-DMA -> no new longs (cap CAUTION) ---
    no_new_longs = smh < smh_200
    state[no_new_longs & (state == "RISK_ON")] = "CAUTION"
    state[no_new_longs & (state == "MIXED")] = "CAUTION"

    mult = state.map(p.multipliers)

    return pd.DataFrame(
        {
            "score": score,
            "vix_score": vix_score,
            "trend_score": trend_score,
            "breadth_score": breadth_score,
            "btc_score": btc_score,
            "state": state,
            "multiplier": mult,
            "no_new_longs": no_new_longs,
            "breadth": breadth,
        }
    )
