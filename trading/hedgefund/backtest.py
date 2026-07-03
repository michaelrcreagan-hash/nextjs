"""Daily event-driven portfolio backtester.

Weekly rank rebalance + daily exit checks, costs on every fill. Fills happen
at the next session's close after a signal (no look-ahead: decisions use
data through day T, fills at close of T+1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import PricePanel
from .regime import RegimeParams, compute_regime
from .signals import SignalParams, compute_signals
from .universe import CATEGORY_OF


@dataclass
class StrategyParams:
    signal: SignalParams = field(default_factory=SignalParams)
    regime: RegimeParams = field(default_factory=RegimeParams)
    use_regime: bool = True
    tier_cutoff: float = 55.0        # min score to be a candidate (Silver)
    top_n: int = 8
    max_name_weight: float = 0.12
    max_category_weight: float = 0.25
    trailing_stop: float = 0.25      # from highest close since entry
    atr_stop_mult: float = 2.5       # initial stop, ATR-proxy units
    hard_exit_below_200sma: bool = True
    rebalance_weekday: int = 4       # Friday decisions, Monday-close fills
    cost_bps: float = 10.0           # per side
    start_equity: float = 100_000.0


@dataclass
class BacktestResult:
    equity: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame
    regime: pd.DataFrame
    params: StrategyParams


def run_backtest(
    panel: PricePanel,
    universe: list[str],
    params: StrategyParams | None = None,
    start: str | None = None,
    end: str | None = None,
) -> BacktestResult:
    p = params or StrategyParams()
    cols = [c for c in universe if c in panel.close.columns]
    close = panel.close[cols]
    sigs = compute_signals(panel, cols, p.signal)
    regime = compute_regime(panel, universe, p.regime)
    atr = panel.atr(20)[cols]
    ma200 = close.rolling(200).mean()

    dates = close.index
    if start:
        dates = dates[dates >= pd.Timestamp(start)]
    if end:
        dates = dates[dates <= pd.Timestamp(end)]

    cash = p.start_equity
    shares: dict[str, float] = {}
    entry_px: dict[str, float] = {}
    peak_px: dict[str, float] = {}
    stop_px: dict[str, float] = {}

    equity_curve = {}
    weight_rows = {}
    trades: list[dict] = []
    pending_targets: dict[str, float] | None = None

    cost = p.cost_bps / 10_000.0

    def mark(day) -> float:
        px = close.loc[day]
        return cash + sum(sh * px[t] for t, sh in shares.items() if not np.isnan(px[t]))

    def sell(day, t, px, reason):
        nonlocal cash
        sh = shares.pop(t)
        proceeds = sh * px * (1 - cost)
        cash += proceeds
        trades.append(
            {
                "symbol": t,
                "exit_date": day,
                "exit_px": px,
                "entry_px": entry_px.pop(t),
                "shares": sh,
                "pnl": proceeds - sh * trades_entry_cost[t],
                "reason": reason,
            }
        )
        peak_px.pop(t, None)
        stop_px.pop(t, None)
        trades_entry_cost.pop(t, None)

    trades_entry_cost: dict[str, float] = {}

    for i, day in enumerate(dates):
        px = close.loc[day]

        # ---- 1. execute pending rebalance targets at today's close ----
        if pending_targets is not None:
            nav = mark(day)
            # exits & trims first (free cash), then buys
            for t in list(shares.keys()):
                tgt = pending_targets.get(t, 0.0)
                cur_val = shares[t] * px[t]
                tgt_val = tgt * nav
                if tgt_val < cur_val - 1e-9:
                    if tgt <= 0:
                        sell(day, t, px[t], "rebalance_exit")
                    else:
                        d_sh = (cur_val - tgt_val) / px[t]
                        shares[t] -= d_sh
                        cash += d_sh * px[t] * (1 - cost)
            for t, tgt in pending_targets.items():
                if np.isnan(px.get(t, np.nan)) or tgt <= 0:
                    continue
                cur_val = shares.get(t, 0.0) * px[t]
                tgt_val = tgt * nav
                if tgt_val > cur_val + 1e-9:
                    spend = min(tgt_val - cur_val, cash)
                    if spend <= 0:
                        continue
                    d_sh = spend / (px[t] * (1 + cost))
                    if t not in shares:
                        shares[t] = 0.0
                        entry_px[t] = px[t]
                        peak_px[t] = px[t]
                        a = atr.loc[day, t]
                        stop_px[t] = (
                            px[t] - p.atr_stop_mult * a if not np.isnan(a) else np.nan
                        )
                        trades_entry_cost[t] = px[t] * (1 + cost)
                    shares[t] += d_sh
                    cash -= spend
            pending_targets = None

        # ---- 2. daily exit checks on holdings (use today's close) ----
        for t in list(shares.keys()):
            price = px[t]
            if np.isnan(price):
                continue
            peak_px[t] = max(peak_px.get(t, price), price)
            hit_trail = price < peak_px[t] * (1 - p.trailing_stop)
            hit_stop = not np.isnan(stop_px.get(t, np.nan)) and price < stop_px[t]
            below_200 = (
                p.hard_exit_below_200sma
                and not np.isnan(ma200.loc[day, t])
                and price < ma200.loc[day, t]
            )
            if hit_stop or hit_trail or below_200:
                reason = (
                    "atr_stop" if hit_stop else "trail_stop" if hit_trail else "ma200_break"
                )
                sell(day, t, price, reason)

        # ---- 3. weekly decision: build targets for next session ----
        if day.weekday() == p.rebalance_weekday and i + 1 < len(dates):
            mult = regime.loc[day, "multiplier"] if p.use_regime else 1.0
            no_new = bool(regime.loc[day, "no_new_longs"]) and p.use_regime
            score_row = sigs.score.loc[day]
            gate_row = sigs.trend_gate.loc[day]
            candidates = score_row[(score_row >= p.tier_cutoff) & gate_row]
            candidates = candidates.sort_values(ascending=False).head(p.top_n)

            targets: dict[str, float] = {}
            if mult > 0 and len(candidates) > 0:
                base_w = min(1.0 / len(candidates), p.max_name_weight)
                cat_used: dict[str, float] = {}
                for t in candidates.index:
                    cat = CATEGORY_OF.get(t, "other")
                    room = p.max_category_weight - cat_used.get(cat, 0.0)
                    w = max(0.0, min(base_w, room)) * mult
                    if no_new and t not in shares:
                        continue  # kill switch: keep holds, no fresh entries
                    if w > 0:
                        targets[t] = w
                        cat_used[cat] = cat_used.get(cat, 0.0) + min(base_w, room)
            pending_targets = targets

        equity_curve[day] = mark(day)
        weight_rows[day] = {
            t: shares.get(t, 0.0) * px[t] / equity_curve[day]
            for t in shares
            if not np.isnan(px[t])
        }

    equity = pd.Series(equity_curve).sort_index()
    weights = pd.DataFrame.from_dict(weight_rows, orient="index").fillna(0.0)
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df["ret"] = trades_df["pnl"] / (
            trades_df["entry_px"] * trades_df["shares"]
        )
    return BacktestResult(
        equity=equity, weights=weights, trades=trades_df, regime=regime, params=p
    )
