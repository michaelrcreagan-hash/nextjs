"""Crypto algo desk: Turtle dual-system with ADX / Keltner / OBV filters.

Mechanical implementation of the strategy embedded in the
crypto_algo_trader LLM agent, so it can be backtested and refined:

  Layer 1  Donchian breakout, System 1 (20/10) + System 2 (55/20)
  Layer 2  ADX trend filter with hard veto below the threshold
  Layer 3  Keltner Channel breakout confirmation (EMA20 +/- 2*ATR)
  Layer 4  OBV 10-bar slope confirmation
  Sizing   N = ATR(20); 1 unit risks 1% of equity over 1N move;
           pyramid every 0.5N favorable, max units by signal strength;
           hard stop 2N from the last entry; Donchian reverse exits.

Data: daily OHLCV (``<SYM>_full.csv``). Signals on day T close, fills at
close of T+1 (no look-ahead). Long-only by default (spot desk).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CryptoParams:
    don_fast: int = 20           # System 1 entry lookback
    don_fast_exit: int = 10
    don_slow: int = 55           # System 2 entry lookback
    don_slow_exit: int = 20
    adx_window: int = 14
    adx_veto: float = 20.0       # below this: no new entries
    adx_strong: float = 40.0
    keltner_mult: float = 2.0
    obv_lookback: int = 10
    atr_window: int = 20
    # Walk-forward validated (see REPORT.md): tighter stop, fewer units,
    # wider pyramid step than classic Turtle - crypto's fat tails punish
    # 4-unit pyramids (BTC MAR 0.92 at these values vs 0.81 classic).
    stop_n: float = 1.5          # hard stop, N units from last entry
    pyramid_step_n: float = 1.0
    max_units_strong: int = 2
    max_units_buy: int = 2
    max_units_weak: int = 1
    strong_score: int = 5
    buy_score: int = 3
    weak_score: int = 1
    allow_short: bool = False
    cost_bps: float = 10.0
    start_equity: float = 100_000.0


def _wilder(s: pd.Series, window: int) -> pd.Series:
    return s.ewm(alpha=1 / window, adjust=False).mean()


def compute_indicators(df: pd.DataFrame, p: CryptoParams) -> pd.DataFrame:
    o = pd.DataFrame(index=df.index)
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    o["atr"] = _wilder(tr, p.atr_window)

    up = h.diff()
    dn = -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr_w = _wilder(tr, p.adx_window)
    o["di_plus"] = 100 * _wilder(plus_dm, p.adx_window) / atr_w
    o["di_minus"] = 100 * _wilder(minus_dm, p.adx_window) / atr_w
    dx = 100 * (o["di_plus"] - o["di_minus"]).abs() / (o["di_plus"] + o["di_minus"])
    o["adx"] = _wilder(dx.fillna(0.0), p.adx_window)

    # Donchian levels shifted one bar: today's breakout is vs the PRIOR window.
    o["don_fast_hi"] = h.rolling(p.don_fast).max().shift(1)
    o["don_fast_lo"] = l.rolling(p.don_fast).min().shift(1)
    o["don_slow_hi"] = h.rolling(p.don_slow).max().shift(1)
    o["don_slow_lo"] = l.rolling(p.don_slow).min().shift(1)
    o["exit_fast_lo"] = l.rolling(p.don_fast_exit).min().shift(1)
    o["exit_slow_lo"] = l.rolling(p.don_slow_exit).min().shift(1)
    o["exit_fast_hi"] = h.rolling(p.don_fast_exit).max().shift(1)
    o["exit_slow_hi"] = h.rolling(p.don_slow_exit).max().shift(1)

    ema20 = c.ewm(span=20, adjust=False).mean()
    o["kelt_up"] = ema20 + p.keltner_mult * o["atr"]
    o["kelt_dn"] = ema20 - p.keltner_mult * o["atr"]

    obv = (np.sign(c.diff()).fillna(0.0) * v).cumsum()
    o["obv_slope"] = obv - obv.shift(p.obv_lookback)

    o["close"] = c
    return o


def composite_score(row: pd.Series, p: CryptoParams) -> tuple[int, str | None]:
    """Layered score for one bar. Positive = long bias. ``system`` labels
    which Donchian system fired on the long side ('S1'/'S2'/'both')."""
    c = row["close"]
    l1 = 0
    system = None
    if c > row["don_slow_hi"]:
        l1 += 2
        system = "S2"
    if c > row["don_fast_hi"]:
        l1 += 1
        system = "both" if system == "S2" else "S1"
    if c < row["don_slow_lo"]:
        l1 -= 2
    if c < row["don_fast_lo"]:
        l1 -= 1

    score = l1
    if l1 != 0 and row["adx"] >= p.adx_veto:
        aligned = (row["di_plus"] > row["di_minus"]) if l1 > 0 else (
            row["di_minus"] > row["di_plus"]
        )
        if aligned and row["adx"] >= p.adx_strong:
            score += 2 * np.sign(l1)
        elif aligned and row["adx"] >= 25:
            score += 1 * np.sign(l1)

    if l1 > 0:
        score += 1 if c > row["kelt_up"] else (-1 if c < row["kelt_dn"] else 0)
        score += 1 if row["obv_slope"] > 0 else (-1 if row["obv_slope"] < 0 else 0)
    elif l1 < 0:
        score += -1 if c < row["kelt_dn"] else (1 if c > row["kelt_up"] else 0)
        score += -1 if row["obv_slope"] < 0 else (1 if row["obv_slope"] > 0 else 0)

    return int(score), system


def target_units(score: int, p: CryptoParams) -> int:
    a = abs(score)
    if a >= p.strong_score:
        return p.max_units_strong
    if a >= p.buy_score:
        return p.max_units_buy
    if a >= p.weak_score:
        return p.max_units_weak
    return 0


def run_crypto_backtest(
    df: pd.DataFrame,
    params: CryptoParams | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.Series, pd.DataFrame]:
    """Single-asset, long-only (optionally short) Turtle backtest."""
    p = params or CryptoParams()
    ind = compute_indicators(df, p)
    if start:
        ind = ind.loc[start:]
    if end:
        ind = ind.loc[:end]

    cost = p.cost_bps / 10_000.0
    cash = p.start_equity

    # position state
    direction = 0                 # +1 long / -1 short / 0 flat
    coins = 0.0
    unit_prices: list[float] = []
    unit_sizes: list[float] = []
    entry_system = "S1"
    entry_n = np.nan
    stop = np.nan
    max_units = 0

    pending: tuple[int, int, str] | None = None
    equity_hist: dict = {}
    trades: list[dict] = []

    def equity(px: float) -> float:
        return cash + direction * coins * px

    def open_unit(day, px):
        nonlocal cash, coins, stop
        size = (equity(px) * 0.01) / entry_n  # coins so that a 1N move = 1% equity
        notional = size * px
        fee = notional * cost
        if direction > 0:
            afford = max(0.0, cash - fee)
            if notional > afford:
                size = afford / px
                notional = size * px
                fee = notional * cost
            cash -= notional + fee
        else:
            cash += notional - fee
        if size <= 0:
            return
        coins += size
        unit_prices.append(px)
        unit_sizes.append(size)
        stop = px - direction * p.stop_n * entry_n

    def close_all(day, px, reason):
        nonlocal cash, coins, direction, unit_prices, unit_sizes, stop
        if direction == 0:
            return
        notional = coins * px
        fee = notional * cost
        cash += direction * notional - fee
        avg_in = float(np.average(unit_prices, weights=unit_sizes))
        trades.append(
            {
                "exit_date": day,
                "direction": "long" if direction > 0 else "short",
                "units": len(unit_prices),
                "avg_entry": avg_in,
                "exit_px": px,
                "pnl": direction * (px - avg_in) * coins - fee,
                "reason": reason,
                "system": entry_system,
            }
        )
        direction, coins = 0, 0.0
        unit_prices, unit_sizes = [], []
        stop = np.nan

    for day in ind.index:
        row = ind.loc[day]
        px = row["close"]
        if not np.isfinite(px):
            continue

        # 1. execute pending entry at today's close
        if pending is not None:
            d, tgt, system = pending
            pending = None
            if direction == 0 and np.isfinite(row["atr"]) and row["atr"] > 0:
                direction = d
                entry_n = row["atr"]
                entry_system = system
                max_units = tgt
                open_unit(day, px)

        # 2. manage open position at today's close
        if direction != 0:
            hit_stop = (direction > 0 and px < stop) or (direction < 0 and px > stop)
            if hit_stop:
                close_all(day, px, "stop_2n")
            else:
                if direction > 0:
                    ex = (
                        row["exit_slow_lo"]
                        if entry_system in ("S2", "both")
                        else row["exit_fast_lo"]
                    )
                    if np.isfinite(ex) and px < ex:
                        close_all(day, px, "donchian_exit")
                else:
                    ex = (
                        row["exit_slow_hi"]
                        if entry_system in ("S2", "both")
                        else row["exit_fast_hi"]
                    )
                    if np.isfinite(ex) and px > ex:
                        close_all(day, px, "donchian_exit")
            if direction != 0 and len(unit_prices) < max_units:
                step = p.pyramid_step_n * entry_n
                if direction > 0 and px >= unit_prices[-1] + step:
                    open_unit(day, px)
                elif direction < 0 and px <= unit_prices[-1] - step:
                    open_unit(day, px)

        # 3. signal for tomorrow's open entry
        if direction == 0 and np.isfinite(row["don_slow_hi"]) and np.isfinite(row["adx"]):
            score, system = composite_score(row, p)
            if row["adx"] >= p.adx_veto:
                tgt = target_units(score, p)
                if tgt > 0:
                    if score > 0 and system is not None:
                        pending = (1, tgt, system)
                    elif score < 0 and p.allow_short:
                        pending = (-1, tgt, "S2" if score <= -2 else "S1")

        equity_hist[day] = equity(px)

    eq = pd.Series(equity_hist).sort_index()
    tr = pd.DataFrame(trades)
    if not tr.empty:
        tr["ret"] = tr["pnl"] / (tr["avg_entry"] * tr["units"].clip(lower=1))
    return eq, tr
