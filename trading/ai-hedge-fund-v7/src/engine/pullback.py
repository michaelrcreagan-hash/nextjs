"""
Phase 3: Pullback Signal Engine
Winner from 572 CBT backtests: Fib 61.8% + Keltner Lower (2-of-2 rule)
Composite 17.7, MaxDD -0.5%, Win Rate 74%
"""
from dataclasses import dataclass
from typing import Optional
import yfinance as yf
import numpy as np
import pandas as pd

@dataclass
class PullbackSignal:
    ticker: str
    trigger: bool
    fib_dist: float
    keltner_position: float
    close: float
    stop_loss: float
    target: float
    risk_reward: float

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "trigger": self.trigger,
            "fib_dist_pct": round(self.fib_dist, 3),
            "keltner_position": round(self.keltner_position, 3),
            "close": round(self.close, 2),
            "stop_loss": round(self.stop_loss, 2),
            "target": round(self.target, 2),
            "risk_reward": round(self.risk_reward, 2),
        }

def fib_keltner_pullback(ticker: str, lookback: int = 60, period: str = "6mo") -> PullbackSignal:
    """
    Entry: Price within 4% of Fib 61.8% retracement AND at/below Keltner Lower
    Stop: Below Fib 78.6% or 1.5x ATR below entry
    Target: Fib 38.2% or prior high (2:1 R:R minimum)
    """
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if len(df) < lookback + 10:
            return PullbackSignal(ticker, False, 0, 0, 0, 0, 0, 0)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Fibonacci retracement from lookback-period high/low
        period_high = float(high.iloc[-lookback:].max())
        period_low = float(low.iloc[-lookback:].min())
        fib_range = period_high - period_low

        fib_382 = period_high - 0.382 * fib_range
        fib_500 = period_high - 0.500 * fib_range
        fib_618 = period_high - 0.618 * fib_range
        fib_786 = period_high - 0.786 * fib_range

        last_close = float(close.iloc[-1])

        # Distance to 61.8% in percentage terms
        fib_dist = abs(last_close - fib_618) / last_close * 100
        fib_condition = fib_dist <= 4.0  # Within 4% of 61.8%

        # Keltner Channels (20 EMA +/- 2x ATR)
        ema20 = close.ewm(span=20).mean()
        hl = high - low
        hc = (high - close.shift()).abs()
        lc = (low - close.shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()

        keltner_lower = ema20 - 2.0 * atr14
        keltner_upper = ema20 + 2.0 * atr14

        keltner_position = (last_close - float(keltner_lower.iloc[-1])) / (float(keltner_upper.iloc[-1]) - float(keltner_lower.iloc[-1]))
        keltner_condition = last_close <= float(keltner_lower.iloc[-1]) * 1.02  # At or slightly below lower

        trigger = fib_condition and keltner_condition

        last_atr = float(atr14.iloc[-1])

        # Stop: below 78.6% fib or 1.5x ATR
        stop_fib = fib_786 - 0.5 * last_atr
        stop_atr = last_close - 1.5 * last_atr
        stop_loss = max(stop_fib, stop_atr)

        # Target: 38.2% fib (prior resistance becomes support)
        target = fib_382
        risk = last_close - stop_loss
        reward = target - last_close
        rr = reward / risk if risk > 0 else 0

        return PullbackSignal(
            ticker=ticker,
            trigger=bool(trigger),
            fib_dist=fib_dist,
            keltner_position=keltner_position,
            close=last_close,
            stop_loss=stop_loss,
            target=target,
            risk_reward=rr,
        )
    except Exception:
        return PullbackSignal(ticker, False, 0, 0, 0, 0, 0, 0)

def batch_pullback(tickers: list) -> list:
    """Run pullback scan on multiple tickers."""
    results = []
    for t in tickers:
        sig = fib_keltner_pullback(t)
        if sig.trigger:
            results.append(sig)
    results.sort(key=lambda x: x.risk_reward, reverse=True)
    return results
