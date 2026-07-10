"""
Phase 4: IAE Technical Confluence Engine
8-layer scoring: Trend, Momentum, Volatility, Volume,
MeanReversion, Strength, Breadth, Execution
"""
from dataclasses import dataclass, field
from typing import Dict, List
import yfinance as yf
import numpy as np
import pandas as pd

@dataclass
class IAEConfluence:
    ticker: str
    trend: float = 0.0        # 0-100: EMA alignment
    momentum: float = 0.0     # 0-100: RSI/MACD composite
    volatility: float = 0.0   # 0-100: ATR regime (low=good)
    volume: float = 0.0       # 0-100: OBV + relative volume
    mean_rev: float = 0.0     # 0-100: Reversion potential
    strength: float = 0.0     # 0-100: ADX + price position
    breadth: float = 0.0      # 0-100: vs sector
    execution: float = 0.0    # 0-100: Spread + liquidity
    composite: float = 0.0
    regime: str = "neutral"

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "trend": round(self.trend, 1),
            "momentum": round(self.momentum, 1),
            "volatility": round(self.volatility, 1),
            "volume": round(self.volume, 1),
            "mean_rev": round(self.mean_rev, 1),
            "strength": round(self.strength, 1),
            "breadth": round(self.breadth, 1),
            "execution": round(self.execution, 1),
            "composite": round(self.composite, 1),
            "regime": self.regime,
        }

def _ema_alignment(close: pd.Series) -> float:
    e9 = close.ewm(span=9).mean()
    e21 = close.ewm(span=21).mean()
    e50 = close.ewm(span=50).mean()
    c = float(close.iloc[-1])
    score = 0
    if c > float(e9.iloc[-1]): score += 35
    if c > float(e21.iloc[-1]): score += 35
    if c > float(e50.iloc[-1]): score += 30
    return float(score)

def _momentum_score(close: pd.Series) -> float:
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - 100 / (1 + rs)
    rsi_score = max(0, 100 - abs(50 - float(rsi.iloc[-1])) * 2)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = float(ema12.iloc[-1]) - float(ema26.iloc[-1])
    macd_score = 50 + min(50, max(-50, macd / close.iloc[-1] * 500))
    return rsi_score * 0.5 + macd_score * 0.5

def _volatility_score(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_pct = atr / close * 100
    current = float(atr_pct.iloc[-1])
    median = float(atr_pct.rolling(60).median().iloc[-1])
    if current < median * 0.7: return 90.0
    if current < median * 0.9: return 75.0
    if current < median * 1.1: return 60.0
    if current < median * 1.3: return 40.0
    return 20.0

def _volume_score(close: pd.Series, volume: pd.Series) -> float:
    obv = (np.sign(close.diff()) * volume).cumsum()
    obv_ema = obv.ewm(span=20).mean()
    obv_score = 70.0 if float(obv.iloc[-1]) > float(obv_ema.iloc[-1]) else 30.0
    v_ratio = float(volume.iloc[-5:].mean()) / float(volume.iloc[-20:].mean())
    vol_score = min(100, max(0, 50 + (v_ratio - 1) * 50))
    return obv_score * 0.5 + vol_score * 0.5

def _mean_reversion(close: pd.Series) -> float:
    ema21 = close.ewm(span=21).mean()
    dist = (float(close.iloc[-1]) - float(ema21.iloc[-1])) / float(ema21.iloc[-1]) * 100
    return min(100, max(0, 50 + abs(dist) * 8))

def _strength_score(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    plus_dm = (high - high.shift()).where(lambda x: x > 0, 0)
    minus_dm = (low.shift() - low).where(lambda x: x > 0, 0)
    tr_sum = tr.rolling(14).sum()
    plus_di = 100 * plus_dm.rolling(14).sum() / tr_sum
    minus_di = 100 * minus_dm.rolling(14).sum() / tr_sum
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di) * 100).fillna(0)
    adx = dx.rolling(14).mean()
    adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 25
    adx_score = min(100, adx_val * 3)
    range_pos = (float(close.iloc[-1]) - float(low.iloc[-20:].min())) / (float(high.iloc[-20:].max()) - float(low.iloc[-20:].min())) * 100
    return adx_score * 0.5 + range_pos * 0.5

def compute_confluence_score(ticker: str, period: str = "3mo", sector_etf: str = "XLK") -> IAEConfluence:
    """Compute full 8-layer IAE confluence score."""
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if len(df) < 50:
            return IAEConfluence(ticker=ticker)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"] if "Volume" in df.columns else pd.Series([1e6] * len(df), index=df.index)

        result = IAEConfluence(ticker=ticker)
        result.trend = _ema_alignment(close)
        result.momentum = _momentum_score(close)
        result.volatility = _volatility_score(high, low, close)
        result.volume = _volume_score(close, volume)
        result.mean_rev = _mean_reversion(close)
        result.strength = _strength_score(high, low, close)

        try:
            sec = yf.download(sector_etf, period=period, progress=False, auto_adjust=True)
            if len(sec) >= 20:
                my_roc = (float(close.iloc[-1]) / float(close.iloc[-20]) - 1) * 100
                sec_roc = (float(sec["Close"].iloc[-1]) / float(sec["Close"].iloc[-20]) - 1) * 100
                result.breadth = min(100, max(0, 50 + (my_roc - sec_roc) * 10))
        except Exception:
            result.breadth = 50.0

        result.execution = min(100, max(20, float(close.iloc[-1]) / 10 * 10))

        weights = {"trend":0.18,"momentum":0.15,"volatility":0.12,"volume":0.12,"mean_rev":0.10,"strength":0.13,"breadth":0.12,"execution":0.08}
        result.composite = sum(getattr(result, k) * w for k, w in weights.items())

        if result.composite >= 65: result.regime = "strong_bullish"
        elif result.composite >= 50: result.regime = "bullish"
        elif result.composite >= 35: result.regime = "neutral"
        elif result.composite >= 20: result.regime = "bearish"
        else: result.regime = "strong_bearish"

        return result
    except Exception:
        return IAEConfluence(ticker=ticker)

def batch_confluence(tickers: list, sector_etf: str = "XLK") -> List[IAEConfluence]:
    """Run confluence scan on multiple tickers."""
    return [compute_confluence_score(t, sector_etf=sector_etf) for t in tickers]
