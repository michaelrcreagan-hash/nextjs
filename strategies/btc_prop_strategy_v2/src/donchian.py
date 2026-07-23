"""Donchian breakout strategy on 4H bars with daily trend filter + ATR trailing stop.

Literature basis (RESEARCH.md addendum): Turtle-style Donchian channel breakout,
long/short, with a higher-timeframe trend filter and 2.5-3.5x ATR trailing stop.
The only 4H approach found with multi-source evidence of positive performance
across both bull and bear regimes, and category-consistent with the SFI 2025
Donchian-ensemble paper (the strategy family with real academic support).

Rules:
  Long entry:  close breaks above highest high of last N 4H bars AND daily
               trend filter bullish (close > daily-equivalent EMA).
  Short entry: close breaks below lowest low of last N bars AND filter bearish.
  Exit: ATR trailing stop (k x ATR14) only -- classic trend-following, no
        profit target (let winners run), stop ratchets with favorable moves.
  One position at a time. Signals on bar t close, execution at t+1 open.

Prop-challenge evaluation: rolling-window pass simulation instead of a single
permanent-halt run -- for every rolling window of `challenge_bars`, does equity
hit +10% before breaching the 3% daily / 6% total internal buffers?
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class DonchianParams:
    entry_lookback: int = 55      # 4H bars (55 bars ~ 9 days)
    trail_atr_mult: float = 3.0
    atr_period: int = 14
    daily_filter: bool = True
    daily_ema_bars: int = 120     # 120 x 4H = 20 days ~ daily EMA20 equivalent
    risk_per_trade_pct: float = 0.5
    max_leverage: float = 3.0
    fee_pct: float = 0.04
    slip_pct: float = 0.02


def prepare(df: pd.DataFrame, p: DonchianParams) -> pd.DataFrame:
    out = df.copy()
    high_low = out["high"] - out["low"]
    high_close = (out["high"] - out["close"].shift()).abs()
    low_close = (out["low"] - out["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    out["atr"] = tr.rolling(p.atr_period).mean()
    out["don_high"] = out["high"].rolling(p.entry_lookback).max().shift(1)
    out["don_low"] = out["low"].rolling(p.entry_lookback).min().shift(1)
    out["trend_ema"] = out["close"].ewm(span=p.daily_ema_bars, adjust=False).mean()
    return out


def run(df_raw: pd.DataFrame, p: DonchianParams, initial_equity: float = 50000.0) -> dict:
    df = prepare(df_raw, p)
    equity = initial_equity
    pos = None  # dict(direction, entry, units, stop)
    trades, curve = [], []

    fees = lambda notional: notional * (p.fee_pct + p.slip_pct) / 100

    for i in range(1, len(df)):
        prev, row = df.iloc[i - 1], df.iloc[i]
        if np.isnan(prev["atr"]) or np.isnan(prev["don_high"]):
            curve.append((row["date"], equity))
            continue

        # manage open position
        if pos:
            exit_price = None
            if pos["direction"] == 1 and row["low"] <= pos["stop"]:
                exit_price = min(pos["stop"], row["open"])  # gap-aware
            elif pos["direction"] == -1 and row["high"] >= pos["stop"]:
                exit_price = max(pos["stop"], row["open"])
            if exit_price is not None:
                pnl = (exit_price - pos["entry"]) * pos["units"] * pos["direction"]
                pnl -= fees(exit_price * pos["units"])
                equity += pnl
                trades.append({"dir": pos["direction"], "entry": pos["entry"],
                               "exit": exit_price, "pnl": pnl,
                               "entry_date": pos["entry_date"], "exit_date": row["date"]})
                pos = None
            else:
                # ratchet trailing stop
                if pos["direction"] == 1:
                    pos["stop"] = max(pos["stop"], row["close"] - p.trail_atr_mult * row["atr"])
                else:
                    pos["stop"] = min(pos["stop"], row["close"] + p.trail_atr_mult * row["atr"])

        # entries (signal on prev bar close, execute this bar open)
        if pos is None:
            bull_filter = (not p.daily_filter) or prev["close"] > prev["trend_ema"]
            bear_filter = (not p.daily_filter) or prev["close"] < prev["trend_ema"]
            direction = 0
            if prev["close"] > prev["don_high"] and bull_filter:
                direction = 1
            elif prev["close"] < prev["don_low"] and bear_filter:
                direction = -1
            if direction != 0:
                entry = row["open"]
                stop_dist = p.trail_atr_mult * prev["atr"]
                risk_usd = equity * p.risk_per_trade_pct / 100
                units = risk_usd / stop_dist
                units = min(units, equity * p.max_leverage / entry)
                if units > 0:
                    equity -= fees(entry * units)
                    pos = {"direction": direction, "entry": entry, "units": units,
                           "stop": entry - direction * stop_dist, "entry_date": row["date"]}

        curve.append((row["date"], equity))

    eq = pd.DataFrame(curve, columns=["date", "equity"])
    return _metrics(trades, eq, initial_equity)


def _metrics(trades, eq, initial_equity, periods_per_year=365 * 6):
    if eq.empty or not trades:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "total_return_pct": 0.0, "max_dd_pct": 0.0,
                "win_rate_pct": 0.0, "trades": 0, "profit_factor": 0.0, "equity": eq,
                "trade_list": trades}
    eq = eq.copy()
    eq["ret"] = eq["equity"].pct_change()
    sharpe = eq["ret"].mean() / eq["ret"].std() * np.sqrt(periods_per_year) if eq["ret"].std() > 0 else 0.0
    peak = eq["equity"].cummax()
    max_dd = ((eq["equity"] - peak) / peak).min() * 100
    years = len(eq) / periods_per_year
    total = eq["equity"].iloc[-1] / initial_equity
    cagr = (total ** (1 / years) - 1) * 100 if years > 0 else 0.0
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf["pnl"] > 0]["pnl"].sum()
    losses = -tdf[tdf["pnl"] <= 0]["pnl"].sum()
    return {
        "sharpe": round(float(sharpe), 3),
        "cagr_pct": round(float(cagr), 2),
        "total_return_pct": round((total - 1) * 100, 2),
        "max_dd_pct": round(float(max_dd), 2),
        "win_rate_pct": round((tdf["pnl"] > 0).mean() * 100, 1),
        "trades": len(tdf),
        "profit_factor": round(wins / losses, 2) if losses > 0 else float("inf"),
        "equity": eq,
        "trade_list": trades,
    }


def challenge_pass_analysis(eq: pd.DataFrame, target_pct=10.0, daily_buffer_pct=3.0,
                            total_buffer_pct=6.0, challenge_bars=360, step=30) -> dict:
    """Rolling-window prop-challenge simulation on the continuous equity curve.

    challenge_bars=360 4H bars = 60 days. For each window starting every `step`
    bars: normalize equity to window start, check whether +target hit before
    breaching total buffer (from window-start equity) or any single day losing
    more than daily buffer.
    """
    eq = eq.reset_index(drop=True)
    n = len(eq)
    results = []
    for start in range(0, n - challenge_bars, step):
        w = eq.iloc[start:start + challenge_bars]
        base = w["equity"].iloc[0]
        norm = w["equity"] / base
        # daily loss check: group by date, compare day close to prev day close
        daily = w.groupby(w["date"].dt.date)["equity"].last()
        daily_loss_breach = (daily.pct_change() < -daily_buffer_pct / 100).any()
        hit_target = (norm >= 1 + target_pct / 100)
        hit_breach = (norm <= 1 - total_buffer_pct / 100)
        t_target = hit_target.idxmax() if hit_target.any() else None
        t_breach = hit_breach.idxmax() if hit_breach.any() else None
        if t_target is not None and (t_breach is None or t_target < t_breach) and not daily_loss_breach:
            results.append("pass")
        elif t_breach is not None or daily_loss_breach:
            results.append("breach")
        else:
            results.append("timeout")
    counts = pd.Series(results).value_counts()
    total = len(results)
    return {
        "windows": total,
        "pass_rate_pct": round(counts.get("pass", 0) / total * 100, 1) if total else 0,
        "breach_rate_pct": round(counts.get("breach", 0) / total * 100, 1) if total else 0,
        "timeout_rate_pct": round(counts.get("timeout", 0) / total * 100, 1) if total else 0,
    }
