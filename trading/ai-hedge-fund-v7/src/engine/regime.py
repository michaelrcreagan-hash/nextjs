"""
Phase 1: Macro Regime Detection Engine
Detects RISK-ON / MIXED / CAUTION / RISK-OFF from 5 signals.
"""
from enum import Enum
from typing import Dict, Tuple
import yfinance as yf

class Regime(Enum):
    RISK_ON = "RISK-ON"
    MIXED = "MIXED"
    CAUTION = "CAUTION"
    RISK_OFF = "RISK-OFF"

REGIME_MATRIX = {
    Regime.RISK_ON:  {"macro":0.40,"income":0.15,"innovation":0.35,"options":0.10,"cash":0.00},
    Regime.MIXED:    {"macro":0.35,"income":0.30,"innovation":0.20,"options":0.10,"cash":0.05},
    Regime.CAUTION:  {"macro":0.20,"income":0.45,"innovation":0.10,"options":0.05,"cash":0.20},
    Regime.RISK_OFF: {"macro":0.05,"income":0.50,"innovation":0.00,"options":0.00,"cash":0.45},
}

def detect_regime(vix: float, smh_above_200dma: bool,
                  breadth_pct: float, btc_trend: str,
                  module_f_avg: float = 50.0) -> Tuple[Regime, float]:
    score = 0.0
    score += 2.0 if vix < 17 else (-2.0 if vix > 25 else 0.0)
    score += 2.0 if smh_above_200dma else -2.0
    score += 2.0 if breadth_pct > 60 else (-2.0 if breadth_pct < 40 else 0.0)
    score += 1.0 if btc_trend == "rising" else (-1.0 if btc_trend == "falling" else 0.0)
    score += 1.0 if module_f_avg > 70 else (-1.0 if module_f_avg < 40 else 0.0)
    regime = (Regime.RISK_ON if score >= 4 else
              Regime.MIXED if score >= 1 else
              Regime.CAUTION if score >= -2 else Regime.RISK_OFF)
    if module_f_avg < 40:
        if regime == Regime.RISK_ON: regime = Regime.MIXED
        elif regime == Regime.MIXED: regime = Regime.CAUTION
    return regime, score

def fetch_regime_data() -> Dict:
    """Fetch live data for regime detection."""
    try:
        vix = float(yf.Ticker("^VIX").history(period="2d")["Close"].iloc[-1])
    except: vix = 18.0
    try:
        smh = yf.Ticker("SMH").history(period="1y")
        smh_above = float(smh["Close"].iloc[-1]) > float(smh["Close"].rolling(200).mean().iloc[-1])
    except: smh_above = True
    return {"vix": vix, "smh_above_200dma": smh_above, "breadth_pct": 60.0, "btc_trend": "neutral"}
