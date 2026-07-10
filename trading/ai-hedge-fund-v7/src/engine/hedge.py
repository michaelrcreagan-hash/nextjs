"""
Phase 6: Macro Hedge Engine
4-sleeve hedge construction with VIX-based sizing
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import yfinance as yf

HEDGE_UNIVERSE = {
    "VIX": {"type": "volatility", "etf": "VIXY", "weight": 0.30},
    "TLT": {"type": "rates", "etf": "TLT", "weight": 0.25},
    "GLD": {"type": "gold", "etf": "GLD", "weight": 0.25},
    "SQQQ": {"type": "inverse", "etf": "SQQQ", "weight": 0.20},
}

@dataclass
class MacroHedge:
    regime: str
    vix_level: float
    hedges: List[Dict]
    total_allocation: float
    cash_pct: float
    reasoning: str

    def to_dict(self):
        return {
            "regime": self.regime,
            "vix": round(self.vix_level, 2),
            "hedges": self.hedges,
            "total_hedge_allocation": f"{self.total_allocation:.1f}%",
            "cash": f"{self.cash_pct:.1f}%",
            "reasoning": self.reasoning,
        }

def fetch_vix() -> float:
    try:
        vix = yf.Ticker("^VIX").history(period="2d")["Close"].iloc[-1]
        return float(vix)
    except Exception:
        return 18.0

def build_hedge_portfolio(regime: str, vix: float, portfolio_value: float = 100000) -> MacroHedge:
    """Build macro hedge allocation based on regime and VIX."""

    if regime == "RISK-ON":
        total_alloc = 5.0
        cash = 0.0
        reasoning = "RISK-ON: Minimal hedging. Small VIX calls for tail protection only."
    elif regime == "MIXED":
        total_alloc = 15.0
        cash = 5.0
        reasoning = "MIXED: Moderate hedging. Balance growth with protection."
    elif regime == "CAUTION":
        total_alloc = 30.0
        cash = 20.0
        reasoning = "CAUTION: Full hedge book. Defensive positioning required."
    else:  # RISK-OFF
        total_alloc = 45.0
        cash = 45.0
        reasoning = "RISK-OFF: Maximum defense. Cash is king."

    if vix > 30:
        total_alloc = min(50, total_alloc + 10)
        cash = min(50, cash + 10)
        reasoning += f" VIX spike to {vix:.1f} forces additional hedging."
    elif vix > 25:
        total_alloc = min(45, total_alloc + 5)
        reasoning += f" Elevated VIX ({vix:.1f}) adds hedge coverage."

    hedges = []
    for name, config in HEDGE_UNIVERSE.items():
        weight = config["weight"]
        if regime == "RISK-ON" and name in ["SQQQ", "VIX"]:
            weight *= 1.5
        elif regime == "RISK-OFF" and name == "TLT":
            weight *= 1.3

        alloc = total_alloc * weight
        dollar = portfolio_value * alloc / 100
        hedges.append({
            "instrument": config["etf"],
            "type": config["type"],
            "allocation_pct": round(alloc, 2),
            "dollar_amount": round(dollar, 0),
            "rationale": f"{config['type'].title()} hedge: {round(alloc,1)}%",
        })

    return MacroHedge(
        regime=regime,
        vix_level=vix,
        hedges=hedges,
        total_allocation=total_alloc,
        cash_pct=cash,
        reasoning=reasoning,
    )

HEDGE_SIGNALS = {
    "VIX_CALL_20_DELTA": {
        "trigger": "VIX < 17 and term structure in contango",
        "action": "Buy VIX 20-delta calls 60 DTE",
        "sizing": "0.3% portfolio",
    },
    "TLT_LONG": {
        "trigger": "10Y yield > 4.5% and trending down",
        "action": "Long TLT or TLT call spreads",
        "sizing": "2-5% portfolio",
    },
    "GLD_HEDGE": {
        "trigger": "DXY strength > 105 and geopolitical risk",
        "action": "Long GLD as currency hedge",
        "sizing": "2-3% portfolio",
    },
    "SQQQ_TAIL": {
        "trigger": "QQQ 10% above 50DMA with declining breadth",
        "action": "Small SQQQ position or put spreads on QQQ",
        "sizing": "1-2% portfolio",
    },
    "USO_INFLATION": {
        "trigger": "Oil breaking above $85 with supply concerns",
        "action": "Long USO calls or energy equity",
        "sizing": "1-2% portfolio",
    },
}

def get_active_hedge_signals() -> List[Dict]:
    """Return currently active hedge signal templates."""
    return list(HEDGE_SIGNALS.values())
