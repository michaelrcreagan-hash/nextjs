"""Daily operating job: the agent's morning routine.

    python -m hedgefund.run daily [--force-rebalance]

1. Load the panel and check data freshness (refuses to trade stale data).
2. Regime check + universe screen (the mechanical cascade).
3. Update the paper-trading ledger with the validated rules.
4. Write the morning report to ``hedgefund/reports/YYYY-MM-DD.md``.
5. Optionally deep-dive top names via the TradingAgents LLM graph when
   API keys are configured (``--deep-dive``).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd

from .backtest import StrategyParams
from .cycles import check_invalidation, cycle_report_line
from .data import load_panel
from .ledger import LEDGER_PATH, load_ledger, mark_equity, save_ledger, update_ledger
from .sell_composite import latest_sell_signals
from .themes import THEME_MAP, latest_theme_ranking
from .universe import ALL_SYMBOLS, UNIVERSE
from .workflow import deep_dive_tickers, screen

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
MAX_STALE_DAYS = 5  # weekend + holiday tolerance


def run_daily(
    force_rebalance: bool = False,
    deep_dive: bool = False,
    params: StrategyParams | None = None,
) -> str:
    p = params or StrategyParams()
    panel = load_panel(ALL_SYMBOLS)
    last_bar = panel.close.dropna(how="all").index[-1]
    stale_days = (datetime.utcnow() - last_bar.to_pydatetime()).days
    stale = stale_days > MAX_STALE_DAYS

    result = screen(panel=panel, signal_params=p.signal, regime_params=p.regime)
    reg = result["regime"]

    ledger = load_ledger()
    if stale:
        summary = {
            "date": str(last_bar.date()),
            "equity": mark_equity(ledger, panel.close.loc[last_bar]),
            "regime": reg["state"],
            "actions": [f"NO TRADING: data is {stale_days} days stale — run fetch_data"],
            "rebalanced": False,
            "positions": {},
        }
    else:
        summary = update_ledger(
            ledger, panel, UNIVERSE, params=p, force_rebalance=force_rebalance
        )
        save_ledger(ledger)

    # ---- morning report ----
    # Named by RUN date so weekend/holiday reports never overwrite the
    # last trading day's file; the header carries the market-data date.
    run_date = datetime.utcnow().strftime("%Y-%m-%d")
    lines = [
        f"# Morning Report — {run_date}",
        "",
        f"_Market data through {summary['date']}_",
        "",
        f"**Regime:** {reg['state']} (score {reg['score']}, gross "
        f"{reg['multiplier']:.0%}, breadth {reg['breadth']:.0%})"
        + ("  ⚠️ DATA STALE" if stale else ""),
        f"**Paper equity:** ${summary['equity']:,.0f} "
        f"(start ${ledger['start_equity']:,.0f}, "
        f"{(summary['equity'] / ledger['start_equity'] - 1) * 100:+.1f}%)",
        "",
        "## Actions today",
    ]
    lines += [f"- {a}" for a in summary["actions"]] or ["- none"]

    lines += ["", "## Open positions", ""]
    if summary.get("positions"):
        lines.append("| Symbol | Entry | Last | Unrealized |")
        lines.append("|---|---|---|---|")
        for s, pos in sorted(summary["positions"].items()):
            lines.append(
                f"| {s} | {pos['entry_px']:.2f} | {pos['last_px']:.2f} "
                f"| {pos['unrealized']:+.1f}% |"
            )
    else:
        lines.append("(flat)")

    wl = result["watchlist"].head(10)
    lines += ["", "## Watchlist (top 10)", "", "| Symbol | Score | Tier | Category | Asym |", "|---|---|---|---|---|"]
    for sym, row in wl.iterrows():
        lines.append(
            f"| {sym} | {row['score']} | {row['tier']} | {row['category']} "
            f"| {'⚡' if row['asymmetric'] else ''} |"
        )
    if result["asymmetric_setups"]:
        lines += ["", f"**Asymmetric setups:** {', '.join(result['asymmetric_setups'])}"]

    # ---- Theme Rotation Engine ----
    # Only themes with any cached member/proxy data score meaningfully;
    # others silently drop out (fetch_data hasn't pulled their history yet
    # — see universe.py's EXTENDED_UNIVERSE note).
    lines += ["", "## Theme Rotation", ""]
    theme_ranking = None
    try:
        usable_themes = {
            k: v for k, v in THEME_MAP.items()
            if any(t in panel.close.columns for t in v["tickers"])
        }
        theme_ranking = latest_theme_ranking(panel, theme_map=usable_themes)
        lines.append("| Theme | Score | Action |")
        lines.append("|---|---|---|")
        for theme, row in theme_ranking.iterrows():
            lines.append(f"| {theme.replace('_', ' ')} | {row['score']:.0f} | {row['action']} |")
        missing = set(THEME_MAP) - set(usable_themes)
        if missing:
            lines.append(
                f"\n_{len(missing)} themes not yet scored (no cached data): "
                f"{', '.join(sorted(missing))}_"
            )
    except Exception as e:
        lines.append(f"_Theme rotation unavailable: {e}_")

    # ---- Macro cycle overlay (4yr x 16.8yr x seasonal) ----
    lines += ["", "## Macro Cycle Overlay", ""]
    cycle_sig, cycle_inv = None, None
    try:
        from .cycles import cycle_signal

        as_of = result["as_of"]
        cycle_sig = cycle_signal(as_of)
        lines.append(cycle_report_line(panel, as_of))
        cycle_inv = check_invalidation(panel, as_of)
        if cycle_inv.get("invalidated"):
            lines.append(f"\n⚠️ **{cycle_inv['reason']}**")
    except Exception as e:
        lines.append(f"_Cycle overlay unavailable: {e}_")

    # ---- 88% Sell Composite on open positions ----
    held = list(summary.get("positions", {}).keys())
    if held:
        lines += ["", "## Sell Composite — Open Positions", ""]
        try:
            sc = latest_sell_signals(panel, held)
            lines.append("| Symbol | Measured Triggers | Action |")
            lines.append("|---|---|---|")
            for sym, row in sc.iterrows():
                lines.append(
                    f"| {sym} | {row['measured_triggers']}/3 | {row['action']} |"
                )
            lines.append(
                "\n_Counts only the 3 mechanically measurable triggers "
                "(options-flow and capex-miss triggers need data this repo "
                "doesn't fetch yet) — treat as a lower bound._"
            )
        except Exception as e:
            lines.append(f"_Sell composite unavailable: {e}_")

    # Crypto desk runs EVERY day — crypto has no weekend.
    from .crypto_desk import crypto_report_lines

    lines += crypto_report_lines()

    is_weekend = datetime.utcnow().weekday() >= 5
    if deep_dive:
        try:
            from tradingagents.default_config import DEFAULT_CONFIG
            from tradingagents.graph.trading_graph import TradingAgentsGraph

            lines += ["", "## LLM deep dives", ""]

            # Equity deep dives only on trading days.
            if not is_weekend:
                names = deep_dive_tickers(result)
                graph = TradingAgentsGraph(
                    selected_analysts=("market", "news", "ai_bottleneck", "options"),
                    config=DEFAULT_CONFIG,
                )
                for t in names:
                    final_state, decision = graph.propagate(t, summary["date"])
                    lines.append(f"### {t} — {decision}\n")
                    rationale = (final_state or {}).get("final_trade_decision", "")
                    if rationale:
                        lines.append(
                            "<details><summary>Portfolio manager rationale"
                            f"</summary>\n\n{rationale}\n\n</details>\n"
                        )

            # Crypto agents run daily, weekends included.
            crypto_graph = TradingAgentsGraph(
                selected_analysts=("crypto_algo_trader", "crypto_investor"),
                config=DEFAULT_CONFIG,
            )
            crypto_date = datetime.utcnow().strftime("%Y-%m-%d")
            final_state, decision = crypto_graph.propagate(
                "BTC-USD", crypto_date, asset_type="crypto"
            )
            lines.append(f"### BTC-USD — {decision}\n")
            rationale = (final_state or {}).get("final_trade_decision", "")
            if rationale:
                lines.append(
                    "<details><summary>Portfolio manager rationale"
                    f"</summary>\n\n{rationale}\n\n</details>\n"
                )
        except Exception as e:  # missing API keys, etc. — report, don't crash
            lines += ["", f"_Deep dive skipped: {e}_"]

    report = "\n".join(lines) + "\n"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"{run_date}.md")
    with open(path, "w") as f:
        f.write(report)

    _write_dashboard_snapshot(result, summary, ledger, stale, theme_ranking, cycle_sig, cycle_inv)

    print(report)
    print(f"[report written to {path}; ledger at {LEDGER_PATH}]")
    return path


def _write_dashboard_snapshot(
    result, summary, ledger, stale: bool,
    theme_ranking=None, cycle_sig=None, cycle_inv=None,
) -> None:
    """Structured JSON consumed by the Next.js /fund dashboard page."""
    import json

    wl = result["watchlist"]
    snapshot = {
        "as_of": str(result["as_of"].date()),
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "stale": stale,
        "regime": {
            "state": result["regime"]["state"],
            "score": int(result["regime"]["score"]),
            "multiplier": float(result["regime"]["multiplier"]),
            "breadth": round(float(result["regime"]["breadth"]), 3),
        },
        "equity": summary["equity"],
        "start_equity": ledger["start_equity"],
        "actions": summary["actions"],
        "positions": summary.get("positions", {}),
        "watchlist": [
            {
                "symbol": sym,
                "score": float(row["score"]),
                "tier": row["tier"],
                "category": row["category"],
                "trend_gate": bool(row["trend_gate"]),
                "asymmetric": bool(row["asymmetric"]),
                "rsi": float(row["rsi"]),
                "off_52w_high": float(row["off_52w_high"]),
            }
            for sym, row in wl.iterrows()
        ],
        "asymmetric_setups": result["asymmetric_setups"],
        "themes": (
            [
                {"theme": t, "score": float(row["score"]), "action": row["action"]}
                for t, row in theme_ranking.iterrows()
            ]
            if theme_ranking is not None
            else []
        ),
        "cycle": (
            {
                "year_in_cycle": cycle_sig["year_in_cycle"],
                "secular_phase": cycle_sig["secular_phase"],
                "quarter": cycle_sig["quarter"],
                "cycle_multiplier": cycle_sig["cycle_multiplier"],
                "invalidated": bool((cycle_inv or {}).get("invalidated", False)),
            }
            if cycle_sig is not None
            else None
        ),
    }
    state_dir = os.path.dirname(LEDGER_PATH)
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "dashboard.json"), "w") as f:
        json.dump(snapshot, f, indent=2)


def portfolio_summary() -> None:
    ledger = load_ledger()
    hist = pd.DataFrame(ledger["history"])
    print(f"Paper account since {ledger['created'][:10]}")
    print(f"Start equity : ${ledger['start_equity']:,.0f}")
    if not hist.empty:
        eq = hist.iloc[-1]["equity"]
        print(f"Equity       : ${eq:,.0f} ({(eq / ledger['start_equity'] - 1) * 100:+.2f}%)")
        print(f"Days tracked : {len(hist)}  |  last regime: {hist.iloc[-1]['regime']}")
    print(f"Open positions: {len(ledger['positions'])}")
    for s, pos in ledger["positions"].items():
        print(f"  {s:6s} {pos['shares']:.4f} sh @ {pos['entry_px']:.2f} since {pos['entry_date']}")
    trades = pd.DataFrame(ledger["trades"])
    if not trades.empty:
        wins = (trades["pnl"] > 0).sum()
        print(
            f"Closed trades: {len(trades)}  |  win rate {wins / len(trades) * 100:.0f}%"
            f"  |  total P&L ${trades['pnl'].sum():+,.0f}"
        )
