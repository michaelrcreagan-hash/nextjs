"""Paper-trading ledger: persistent portfolio state for the live agent.

The ledger applies the SAME validated rules as the backtester — soft
regime gate, top-N conviction entries, 3xATR + 30% trailing + 200-SMA
exits, 12%/25% caps — against the latest cached data, and persists
state as JSON so the daily job builds a real out-of-sample track record.

State file: ``hedgefund/state/ledger.json`` (committed, so a scheduled
runner persists it between runs).
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from .backtest import StrategyParams
from .data import PricePanel
from .regime import compute_regime
from .signals import compute_signals
from .universe import CATEGORY_OF

STATE_DIR = os.path.join(os.path.dirname(__file__), "state")
LEDGER_PATH = os.path.join(STATE_DIR, "ledger.json")


def new_ledger(start_equity: float = 100_000.0) -> dict:
    return {
        "created": datetime.utcnow().isoformat(timespec="seconds"),
        "start_equity": start_equity,
        "cash": start_equity,
        "positions": {},   # sym -> {shares, entry_px, entry_date, stop_px, peak_px}
        "trades": [],      # closed trades
        "history": [],     # {date, equity, cash, n_positions, regime}
        "failure_log": [],  # golden rule: log every >2% loss before re-entry
        "last_run": None,
        "last_rebalance": None,
    }


def _heat_check_multiplier(trades: list[dict], lookback: int = 5) -> float:
    """Golden rule: 'never size up during a losing streak.' If 3 of the
    last 5 closed trades lost, cut new-entry size in half until the
    streak clears (3 consecutive winners resets it naturally as the
    losing trades roll out of the lookback window)."""
    recent = trades[-lookback:]
    if len(recent) < lookback:
        return 1.0
    losses = sum(1 for t in recent if t["pnl"] < 0)
    return 0.5 if losses >= 3 else 1.0


def _reentry_blocked(failure_log: list[dict], sym: str, day: pd.Timestamp, cooldown_days: int = 5) -> bool:
    """Golden rule: 'after any >2% loss, log exact failure before
    re-entering.' Mechanically: block new entries into a name for
    ``cooldown_days`` trading days after it logged a >2% loss."""
    for entry in reversed(failure_log):
        if entry["symbol"] != sym:
            continue
        days_since = (day - pd.Timestamp(entry["date"])).days
        return 0 <= days_since < cooldown_days
    return False


def load_ledger(path: str = LEDGER_PATH) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return new_ledger()


def save_ledger(ledger: dict, path: str = LEDGER_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(ledger, f, indent=2)


def mark_equity(ledger: dict, px: pd.Series) -> float:
    val = ledger["cash"]
    for sym, pos in ledger["positions"].items():
        p = px.get(sym, np.nan)
        if np.isfinite(p):
            val += pos["shares"] * p
    return float(val)


def update_ledger(
    ledger: dict,
    panel: PricePanel,
    universe: list[str],
    params: StrategyParams | None = None,
    force_rebalance: bool = False,
) -> dict:
    """One daily tick: exits every run; entry rebalance on the configured
    weekday (or when forced). Fills at the latest close with costs.
    Returns a run summary dict for the report."""
    p = params or StrategyParams()
    cost = p.cost_bps / 10_000.0

    cols = [c for c in universe if c in panel.close.columns]
    close = panel.close[cols]
    day = close.dropna(how="all").index[-1]
    day_str = str(day.date())
    px = close.loc[day]

    if ledger["history"] and ledger["history"][-1]["date"] == day_str:
        # Same bar (weekend/holiday re-run): no trading, but still report
        # the real portfolio instead of appearing flat.
        return {
            "date": day_str,
            "skipped": "already processed this bar",
            "equity": ledger["history"][-1]["equity"],
            "actions": [],
            "rebalanced": False,
            "positions": {
                s: {"shares": round(pos["shares"], 4),
                    "entry_px": pos["entry_px"],
                    "last_px": float(px.get(s, np.nan)),
                    "unrealized": round((float(px.get(s, np.nan)) - pos["entry_px"])
                                        / pos["entry_px"] * 100, 1)}
                for s, pos in ledger["positions"].items()
            },
        }

    sigs = compute_signals(panel, cols, p.signal)
    regime = compute_regime(panel, universe, p.regime)
    atr = panel.atr(20)[cols].loc[day]
    ma200 = close.rolling(200).mean().loc[day]
    reg_row = regime.loc[day]

    actions: list[str] = []

    # ---- 1. daily exit checks ----
    for sym in list(ledger["positions"].keys()):
        pos = ledger["positions"][sym]
        price = px.get(sym, np.nan)
        if not np.isfinite(price):
            continue
        pos["peak_px"] = max(pos.get("peak_px", price), price)
        reason = None
        if np.isfinite(pos.get("stop_px") or np.nan) and price < pos["stop_px"]:
            reason = "atr_stop"
        elif price < pos["peak_px"] * (1 - p.trailing_stop):
            reason = "trail_stop"
        elif p.hard_exit_below_200sma and np.isfinite(ma200[sym]) and price < ma200[sym]:
            reason = "ma200_break"
        if reason:
            proceeds = pos["shares"] * price * (1 - cost)
            ledger["cash"] += proceeds
            pnl = proceeds - pos["shares"] * pos["entry_px"] * (1 + cost)
            pnl_pct = (price / pos["entry_px"]) - 1
            ledger["trades"].append(
                {"symbol": sym, "entry_date": pos["entry_date"],
                 "entry_px": pos["entry_px"], "exit_date": day_str,
                 "exit_px": float(price), "shares": pos["shares"],
                 "pnl": round(pnl, 2), "reason": reason}
            )
            if pnl_pct <= -0.02:
                ledger["failure_log"].append(
                    {"symbol": sym, "date": day_str, "pnl_pct": round(pnl_pct, 4),
                     "reason": reason,
                     "note": f"{sym} exited {pnl_pct*100:.1f}% via {reason} — "
                              f"cooldown before re-entry"}
                )
            del ledger["positions"][sym]
            actions.append(f"EXIT {sym} @ {price:.2f} ({reason}, P&L {pnl:+,.0f})")

    # ---- 2. rebalance (weekly cadence or forced) ----
    is_rebalance_day = day.weekday() == p.rebalance_weekday or force_rebalance
    if is_rebalance_day:
        nav = mark_equity(ledger, px)
        mult = reg_row["multiplier"] if p.use_regime else 1.0
        no_new = bool(reg_row["no_new_longs"]) and p.use_regime and p.respect_no_new_longs
        score_row = sigs.score.loc[day]
        gate_row = sigs.trend_gate.loc[day]
        candidates = (
            score_row[(score_row >= p.tier_cutoff) & gate_row]
            .sort_values(ascending=False)
            .head(p.top_n)
        )

        heat_mult = _heat_check_multiplier(ledger["trades"])

        targets: dict[str, float] = {}
        if mult > 0 and len(candidates) > 0:
            base_w = min(1.0 / len(candidates), p.max_name_weight)
            cat_used: dict[str, float] = {}
            for sym in candidates.index:
                cat = CATEGORY_OF.get(sym, "other")
                room = p.max_category_weight - cat_used.get(cat, 0.0)
                w = max(0.0, min(base_w, room)) * mult
                is_new_entry = sym not in ledger["positions"]
                if no_new and is_new_entry:
                    continue
                # Golden rule: after a >2% loss, cool down before re-entry.
                if is_new_entry and _reentry_blocked(ledger["failure_log"], sym, day):
                    continue
                if is_new_entry:
                    w *= heat_mult  # golden rule: half size during a losing streak
                if p.scale_in and is_new_entry:
                    w *= 0.25
                elif p.scale_in and sym in ledger["positions"]:
                    if px[sym] <= ledger["positions"][sym]["entry_px"]:
                        w *= 0.25
                if w > 0:
                    targets[sym] = w
                    cat_used[cat] = cat_used.get(cat, 0.0) + min(base_w, room)

        # exits/trims first
        for sym in list(ledger["positions"].keys()):
            tgt_val = targets.get(sym, 0.0) * nav
            price = px.get(sym, np.nan)
            if not np.isfinite(price):
                continue
            cur_val = ledger["positions"][sym]["shares"] * price
            if tgt_val < cur_val - 1.0:
                if targets.get(sym, 0.0) <= 0:
                    pos = ledger["positions"].pop(sym)
                    proceeds = pos["shares"] * price * (1 - cost)
                    ledger["cash"] += proceeds
                    pnl = proceeds - pos["shares"] * pos["entry_px"] * (1 + cost)
                    pnl_pct = (price / pos["entry_px"]) - 1
                    ledger["trades"].append(
                        {"symbol": sym, "entry_date": pos["entry_date"],
                         "entry_px": pos["entry_px"], "exit_date": day_str,
                         "exit_px": float(price), "shares": pos["shares"],
                         "pnl": round(pnl, 2), "reason": "rebalance_exit"}
                    )
                    if pnl_pct <= -0.02:
                        ledger["failure_log"].append(
                            {"symbol": sym, "date": day_str, "pnl_pct": round(pnl_pct, 4),
                             "reason": "rebalance_exit",
                             "note": f"{sym} exited {pnl_pct*100:.1f}% on rank drop — "
                                      f"cooldown before re-entry"}
                        )
                    actions.append(f"EXIT {sym} @ {price:.2f} (rank drop, P&L {pnl:+,.0f})")
                else:
                    d_sh = (cur_val - tgt_val) / price
                    ledger["positions"][sym]["shares"] -= d_sh
                    ledger["cash"] += d_sh * price * (1 - cost)
                    actions.append(f"TRIM {sym} to {targets[sym]:.1%} @ {price:.2f}")

        # buys
        for sym, tgt in targets.items():
            price = px.get(sym, np.nan)
            if not np.isfinite(price) or tgt <= 0:
                continue
            cur_val = ledger["positions"].get(sym, {}).get("shares", 0.0) * price
            tgt_val = tgt * nav
            if tgt_val > cur_val + 1.0:
                spend = min(tgt_val - cur_val, ledger["cash"])
                if spend <= 0:
                    continue
                d_sh = spend / (price * (1 + cost))
                if sym not in ledger["positions"]:
                    a = atr.get(sym, np.nan)
                    ledger["positions"][sym] = {
                        "shares": 0.0, "entry_px": float(price),
                        "entry_date": day_str, "peak_px": float(price),
                        "stop_px": float(price - p.atr_stop_mult * a)
                        if np.isfinite(a) else None,
                    }
                    actions.append(f"BUY {sym} {tgt:.1%} @ {price:.2f}")
                else:
                    actions.append(f"ADD {sym} to {tgt:.1%} @ {price:.2f}")
                ledger["positions"][sym]["shares"] += d_sh
                ledger["cash"] -= spend
        ledger["last_rebalance"] = day_str

    equity = mark_equity(ledger, px)
    ledger["history"].append(
        {"date": day_str, "equity": round(equity, 2),
         "cash": round(ledger["cash"], 2),
         "n_positions": len(ledger["positions"]),
         "regime": reg_row["state"]}
    )
    ledger["last_run"] = datetime.utcnow().isoformat(timespec="seconds")

    return {
        "date": day_str,
        "equity": equity,
        "regime": reg_row["state"],
        "multiplier": float(reg_row["multiplier"]),
        "actions": actions,
        "rebalanced": is_rebalance_day,
        "positions": {
            s: {"shares": round(pos["shares"], 4),
                "entry_px": pos["entry_px"],
                "last_px": float(px.get(s, np.nan)),
                "unrealized": round((float(px.get(s, np.nan)) - pos["entry_px"])
                                    / pos["entry_px"] * 100, 1)}
            for s, pos in ledger["positions"].items()
        },
    }
