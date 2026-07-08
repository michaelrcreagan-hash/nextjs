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
    # Defaults are the walk-forward validated config (see REPORT.md):
    # trained 2019-2022, validated 2023+, confirmed full-period.
    use_regime: bool = True
    respect_no_new_longs: bool = False  # lockout missed V-recoveries; soft gate scales instead
    tier_cutoff: float = 60.0        # min score to be a candidate
    top_n: int = 12
    max_name_weight: float = 0.12
    max_category_weight: float = 0.25
    trailing_stop: float = 0.30      # from highest close since entry
    atr_stop_mult: float = 3.0       # initial stop, ATR-proxy units
    # Entry-quality refinements (win-rate lever from the strategy docs):
    pullback_entry: bool = False     # fresh entries only near support
    pullback_rsi_hi: float = 65.0    # RSI ceiling for a "pullback zone" entry
    pullback_ema_dist: float = 0.03  # or price within this frac of EMA21
    scale_in: bool = False           # quarter-size start, full on follow-through
    hard_exit_below_200sma: bool = True
    rebalance_weekday: int = 4       # Friday decisions, Monday-close fills
    cost_bps: float = 10.0           # per side
    start_equity: float = 100_000.0
    # Golden-rule gates (default OFF: REPORT.md's validated numbers were
    # produced without them; enable + re-run optimize.py to validate
    # before trusting a backtest with these on).
    enforce_heat_check: bool = False    # 3 of last 5 trades lose -> half size
    enforce_reentry_cooldown: bool = False  # >2% loss -> N-day re-entry cooldown
    reentry_cooldown_days: int = 5


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
    rsi14 = sigs.components["rsi"]
    ema21 = close.ewm(span=21, adjust=False).mean()

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
        entry = entry_px.pop(t)
        pnl_pct = (px / entry) - 1
        trades.append(
            {
                "symbol": t,
                "exit_date": day,
                "exit_px": px,
                "entry_px": entry,
                "shares": sh,
                "pnl": proceeds - sh * trades_entry_cost[t],
                "reason": reason,
            }
        )
        if pnl_pct <= -0.02:
            failure_log.append({"symbol": t, "date": day, "pnl_pct": pnl_pct})
        peak_px.pop(t, None)
        stop_px.pop(t, None)
        trades_entry_cost.pop(t, None)

    trades_entry_cost: dict[str, float] = {}
    failure_log: list[dict] = []  # golden rule: log every >2% loss

    def heat_check_mult() -> float:
        if not p.enforce_heat_check:
            return 1.0
        recent = trades[-5:]
        if len(recent) < 5:
            return 1.0
        return 0.5 if sum(1 for tr in recent if tr["pnl"] < 0) >= 3 else 1.0

    def reentry_blocked(sym: str, day) -> bool:
        if not p.enforce_reentry_cooldown:
            return False
        for entry in reversed(failure_log):
            if entry["symbol"] != sym:
                continue
            return 0 <= (day - entry["date"]).days < p.reentry_cooldown_days
        return False

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
            no_new = (
                bool(regime.loc[day, "no_new_longs"])
                and p.use_regime
                and p.respect_no_new_longs
            )
            score_row = sigs.score.loc[day]
            gate_row = sigs.trend_gate.loc[day]
            candidates = score_row[(score_row >= p.tier_cutoff) & gate_row]
            candidates = candidates.sort_values(ascending=False).head(p.top_n)

            heat_mult = heat_check_mult()

            targets: dict[str, float] = {}
            if mult > 0 and len(candidates) > 0:
                base_w = min(1.0 / len(candidates), p.max_name_weight)
                cat_used: dict[str, float] = {}
                for t in candidates.index:
                    cat = CATEGORY_OF.get(t, "other")
                    room = p.max_category_weight - cat_used.get(cat, 0.0)
                    w = max(0.0, min(base_w, room)) * mult
                    is_new_entry = t not in shares
                    if no_new and is_new_entry:
                        continue  # kill switch: keep holds, no fresh entries
                    if is_new_entry and reentry_blocked(t, day):
                        continue  # golden rule: cooldown after a >2% loss
                    if is_new_entry:
                        w *= heat_mult  # golden rule: half size in a losing streak
                    if p.pullback_entry and t not in shares:
                        # Fresh entries only from a pullback zone: RSI below
                        # the ceiling, or price hugging EMA21. Extended names
                        # stay on the watchlist for the next pullback.
                        r_now = rsi14.loc[day, t]
                        near_ema = (
                            abs(close.loc[day, t] / ema21.loc[day, t] - 1)
                            <= p.pullback_ema_dist
                        )
                        if not (r_now <= p.pullback_rsi_hi or near_ema):
                            continue
                    if p.scale_in and t not in shares:
                        # Quarter-size start; scales to full at a later
                        # rebalance once the position shows follow-through
                        # (still a candidate and trading above entry).
                        w *= 0.25
                    elif p.scale_in and t in shares:
                        if close.loc[day, t] <= entry_px.get(t, np.inf):
                            w *= 0.25  # no follow-through yet: stay small
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
