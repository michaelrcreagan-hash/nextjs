"""
Phase 3: Breakout Signal Engine
Winner from 572 CBT backtests: ATR + RSI (2-of-2 rule)
Composite 23.6, MaxDD -0.9%, Expectancy +$3,265
"""
from dataclasses import dataclass
from typing import Optional
import yfinance as yf
import numpy as np
import pandas as pd

@dataclass
class BreakoutSignal:
    ticker: str
    trigger: bool
    atr_pct: float
    rsi: float
    close: float
    stop_loss: float
    target: float
    risk_reward: float
    composite: float = 0.0

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "trigger": self.trigger,
            "atr_pct": round(self.atr_pct, 3),
            "rsi": round(self.rsi, 1),
            "close": round(self.close, 2),
            "stop_loss": round(self.stop_loss, 2),
            "target": round(self.target, 2),
            "risk_reward": round(self.risk_reward, 2),
        }

def atr_rsi_breakout(ticker: str, period: str = "3mo") -> BreakoutSignal:
    """
    Entry: ATR% > 1.3x 20-day avg AND RSI 50-70
    Stop: 2x ATR below entry
    Target: 3x ATR above entry (1.5:1 R:R minimum)
    """
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if len(df) < 25:
            return BreakoutSignal(ticker, False, 0, 0, 0, 0, 0, 0)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # ATR calculation
        hl = high - low
        hc = (high - close.shift()).abs()
        lc = (low - close.shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        atr_pct = (atr / close * 100).iloc[-1]
        atr_pct_avg = (atr / close * 100).rolling(20).mean().iloc[-1]

        # RSI calculation
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - 100 / (1 + rs)).iloc[-1]

        # Signal: ATR% > 1.3x avg AND RSI 50-70
        atr_condition = float(atr_pct) > 1.3 * float(atr_pct_avg)
        rsi_condition = 50 <= float(rsi) <= 70
        trigger = atr_condition and rsi_condition

        last_close = float(close.iloc[-1])
        last_atr = float(atr.iloc[-1])

        stop_loss = last_close - 2.0 * last_atr
        target = last_close + 3.0 * last_atr
        risk = last_close - stop_loss
        reward = target - last_close
        rr = reward / risk if risk > 0 else 0

        return BreakoutSignal(
            ticker=ticker,
            trigger=bool(trigger),
            atr_pct=float(atr_pct),
            rsi=float(rsi),
            close=last_close,
            stop_loss=stop_loss,
            target=target,
            risk_reward=rr,
        )
    except Exception as e:
        return BreakoutSignal(ticker, False, 0, 0, 0, 0, 0, 0)

def batch_breakout(tickers: list) -> list:
    """Run breakout scan on multiple tickers."""
    results = []
    for t in tickers:
        sig = atr_rsi_breakout(t)
        if sig.trigger:
            results.append(sig)
    # Sort by risk-reward descending
    results.sort(key=lambda x: x.risk_reward, reverse=True)
    return results
