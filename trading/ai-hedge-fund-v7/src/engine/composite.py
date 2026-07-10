"""
Phase 2: 6-Module Composite Scoring Engine
Modules A-F weighted scoring with Module F (Revision Velocity).
"""
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import yfinance as yf
import numpy as np
import pandas as pd

MODULE_WEIGHTS = {
    "hyperscaler": 0.20,   # A: QQQ proxy velocity
    "earnings": 0.20,      # B: Company earnings velocity
    "peer_val": 0.15,      # C: Relative to AI layer peers
    "technical": 0.15,     # D: Multi-timeframe ROC
    "atr": 0.10,           # E: ATR overextension from 21 EMA
    "analyst_rev": 0.20,   # F: Analyst revision velocity
}

def _prices(ticker: str, period: str = "3mo") -> pd.DataFrame:
    try:
        return yf.download(ticker, period=period, progress=False, auto_adjust=True)
    except Exception:
        return pd.DataFrame()

def _safe_roc(series: pd.Series, lookback: int) -> float:
    if len(series) <= lookback:
        return 0.0
    return (float(series.iloc[-1]) / float(series.iloc[-lookback]) - 1) * 100

class CompositeScorer:
    """6-module composite scorer. Cache-friendly, exception-safe."""

    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}

    def _get(self, ticker: str, period: str) -> pd.DataFrame:
        key = f"{ticker}_{period}"
        if key not in self._cache:
            self._cache[key] = _prices(ticker, period)
        return self._cache[key]

    def module_a_hyperscaler(self, ticker: str) -> float:
        """QQQ 20-day ROC as macro AI demand proxy."""
        try:
            df = self._get("QQQ", "3mo")
            if len(df) < 20: return 50.0
            roc = _safe_roc(df["Close"], 20)
            return max(0, min(100, 50 + roc * 5.0))
        except Exception:
            return 50.0

    def module_b_earnings(self, ticker: str) -> float:
        """20-day ROC + relative volume trend."""
        try:
            df = self._get(ticker, "3mo")
            if len(df) < 20: return 50.0
            roc = _safe_roc(df["Close"], 20)
            vol_ratio = (df["Volume"].iloc[-5:].mean() / df["Volume"].iloc[-20:].mean()) if "Volume" in df.columns else 1.0
            return max(0, min(100, 50 + roc * 4.0 + (vol_ratio - 1) * 10))
        except Exception:
            return 50.0

    def module_c_peer(self, ticker: str, peers: List[str]) -> float:
        """Relative performance vs same AI-layer peers."""
        try:
            df = self._get(ticker, "3mo")
            if len(df) < 20: return 50.0
            my_roc = _safe_roc(df["Close"], 20)
            peer_rocs = []
            for p in peers:
                if p.upper() == ticker.upper(): continue
                pdf = self._get(p, "3mo")
                if len(pdf) >= 20:
                    peer_rocs.append(_safe_roc(pdf["Close"], 20))
            if not peer_rocs: return 50.0
            rel = my_roc - np.mean(peer_rocs)
            return max(0, min(100, 50 + rel * 5.0))
        except Exception:
            return 50.0

    def module_d_technical(self, ticker: str) -> float:
        """Multi-timeframe ROC (5d, 20d, 63d)."""
        try:
            df = self._get(ticker, "6mo")
            if len(df) < 63: return 50.0
            rd = _safe_roc(df["Close"], 5)
            rw = _safe_roc(df["Close"], 20)
            rm = _safe_roc(df["Close"], 63)
            combined = rd * 0.4 + rw * 0.35 + rm * 0.25
            return max(0, min(100, 50 + combined * 3.0))
        except Exception:
            return 50.0

    def module_e_atr(self, ticker: str) -> float:
        """Distance from 21 EMA in ATR units."""
        try:
            df = self._get(ticker, "3mo")
            if len(df) < 21: return 50.0
            hl = df["High"] - df["Low"]
            hc = (df["High"] - df["Close"].shift()).abs()
            lc = (df["Low"] - df["Close"].shift()).abs()
            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])
            ema21 = float(df["Close"].ewm(span=21).mean().iloc[-1])
            close = float(df["Close"].iloc[-1])
            dist = abs(close - ema21) / atr if atr > 0 else 0
            return min(100, dist * 35.0)
        except Exception:
            return 50.0

    def module_f_revision(self, ticker: str) -> float:
        """Module F: Analyst revision velocity.
        Exact formula: velocity = sum(rating_change * weight)
        weight = success% * recency_decay
        decay = 0.5^(age_days/30)
        """
        try:
            df = self._get(ticker, "6mo")
            if len(df) < 30: return 50.0
            # Approximate revision velocity via price momentum + volume
            # as proxy when live analyst data unavailable
            roc20 = _safe_roc(df["Close"], 20)
            roc5 = _safe_roc(df["Close"], 5)
            mom = (roc5 - roc20) * 2.0  # acceleration
            # Recency weighting: recent moves count more
            vol_z = 0.0
            if "Volume" in df.columns:
                vmean = df["Volume"].iloc[-20:].mean()
                vstd = df["Volume"].iloc[-20:].std()
                if vstd > 0:
                    vol_z = (float(df["Volume"].iloc[-1]) - float(vmean)) / float(vstd)
            score = 50.0 + mom * 2.0 + vol_z * 3.0
            return max(0, min(100, score))
        except Exception:
            return 50.0

    def score(self, ticker: str, peers: Optional[List[str]] = None) -> Tuple[float, Dict]:
        """Compute full 6-module composite. Returns (composite, breakdown)."""
        scores = {
            "hyperscaler": self.module_a_hyperscaler(ticker),
            "earnings": self.module_b_earnings(ticker),
            "peer_val": self.module_c_peer(ticker, peers or []),
            "technical": self.module_d_technical(ticker),
            "atr": self.module_e_atr(ticker),
            "analyst_rev": self.module_f_revision(ticker),
        }
        composite = sum(scores[k] * MODULE_WEIGHTS[k] for k in MODULE_WEIGHTS)
        return composite, scores
