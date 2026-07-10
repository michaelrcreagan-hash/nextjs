"""
Phase 5: Options Sizing & Selection Engine
IV-Rank based strategy selection + Position sizing
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import yfinance as yf
import numpy as np

class OptionsStrategy(Enum):
    CREDIT_SPREAD = "credit_spread"      # IV Rank > 50%
    DEBIT_SPREAD = "debit_spread"        # IV Rank 30-50%
    LONG_OPTION = "long_option"          # IV Rank < 30%
    PMCC = "pmcc"                        # LEAP covered call
    CALENDAR = "calendar"                # Low IV, neutral bias

@dataclass
class OptionsTrade:
    ticker: str
    strategy: OptionsStrategy
    direction: str          # "bullish" | "bearish" | "neutral"
    iv_rank: float
    composite_score: float
    setup_type: str         # "breakout" | "pullback"
    recommendation: str
    sizing: str
    strike_suggestion: str
    expiration_suggestion: str

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "strategy": self.strategy.value,
            "direction": self.direction,
            "iv_rank": round(self.iv_rank, 1),
            "composite_score": round(self.composite_score, 1),
            "setup_type": self.setup_type,
            "recommendation": self.recommendation,
            "sizing": self.sizing,
            "strike": self.strike_suggestion,
            "expiration": self.expiration_suggestion,
        }

def compute_iv_rank(ticker: str, period: str = "1y") -> float:
    """Compute IV rank from realized volatility as proxy."""
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if len(df) < 30: return 50.0
        close = df["Close"]
        returns = np.log(close / close.shift()).dropna()
        current_vol = float(returns.iloc[-30:].std() * np.sqrt(252) * 100)
        rolling_vol = returns.rolling(30).std() * np.sqrt(252) * 100
        vol_min = float(rolling_vol.min())
        vol_max = float(rolling_vol.max())
        if vol_max <= vol_min: return 50.0
        iv_rank = (current_vol - vol_min) / (vol_max - vol_min) * 100
        return max(0, min(100, iv_rank))
    except Exception:
        return 50.0

def select_options_strategy(iv_rank: float, composite: float, setup: str) -> OptionsStrategy:
    """Select optimal options strategy based on IV rank and setup."""
    if iv_rank > 50:
        return OptionsStrategy.CREDIT_SPREAD
    elif iv_rank > 30:
        return OptionsStrategy.DEBIT_SPREAD
    elif setup == "breakout" and composite > 65:
        return OptionsStrategy.LONG_OPTION
    elif setup == "pullback" and composite > 55:
        return OptionsStrategy.PMCC
    else:
        return OptionsStrategy.CALENDAR

def size_position(iv_rank: float, composite: float, regime: str) -> str:
    """VIX-based position sizing."""
    base = 2.0  # % of portfolio
    if regime == "RISK-ON": base = 3.0
    elif regime == "MIXED": base = 2.0
    elif regime == "CAUTION": base = 1.0
    elif regime == "RISK-OFF": base = 0.5

    if composite > 70: base *= 1.5
    elif composite > 55: base *= 1.0
    elif composite > 40: base *= 0.6
    else: base *= 0.3

    if iv_rank > 60: base *= 0.7
    elif iv_rank < 20: base *= 1.2

    return f"{min(5.0, max(0.25, base)):.2f}% of portfolio"

def build_options_trade(ticker: str, composite: float, setup: str, regime: str) -> OptionsTrade:
    """Build complete options trade recommendation."""
    iv_rank = compute_iv_rank(ticker)
    strategy = select_options_strategy(iv_rank, composite, setup)

    direction = "bullish"
    if setup == "pullback":
        direction = "bullish"
    elif composite < 40:
        direction = "bearish"

    strike = "ATM"
    expiration = "30-45 DTE"
    rec = ""

    if strategy == OptionsStrategy.CREDIT_SPREAD:
        rec = f"Sell {direction} credit spread. Collect premium with IV rank {iv_rank:.0f}%."
        strike = "0.30 delta" if direction == "bullish" else "0.30 delta put"
        expiration = "30-45 DTE"
    elif strategy == OptionsStrategy.DEBIT_SPREAD:
        rec = f"Buy {direction} debit spread. Defined risk with directional exposure."
        strike = "0.60 delta long, 0.30 delta short"
        expiration = "45-60 DTE"
    elif strategy == OptionsStrategy.LONG_OPTION:
        rec = f"Buy {direction} call. Low IV environment favors long vega."
        strike = "0.70 delta (ITM)"
        expiration = "60-90 DTE"
    elif strategy == OptionsStrategy.PMCC:
        rec = "PMCC: Buy 70-delta LEAP, sell 30-delta weekly call against it."
        strike = "LEAP: 0.70 delta; Short: 0.30 delta weekly"
        expiration = "LEAP: 12-18mo; Short: weekly"
    else:
        rec = "Calendar spread: capitalize on low IV environment."
        strike = "ATM"
        expiration = "Short: 30 DTE, Long: 60 DTE"

    sizing = size_position(iv_rank, composite, regime)

    return OptionsTrade(
        ticker=ticker,
        strategy=strategy,
        direction=direction,
        iv_rank=iv_rank,
        composite_score=composite,
        setup_type=setup,
        recommendation=rec,
        sizing=sizing,
        strike_suggestion=strike,
        expiration_suggestion=expiration,
    )
