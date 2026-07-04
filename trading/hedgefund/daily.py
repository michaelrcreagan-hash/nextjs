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
from .data import load_panel
from .ledger import LEDGER_PATH, load_ledger, mark_equity, save_ledger, update_ledger
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
    lines = [
        f"# Morning Report — {summary['date']}",
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

    if deep_dive:
        try:
            from tradingagents.default_config import DEFAULT_CONFIG
            from tradingagents.graph.trading_graph import TradingAgentsGraph

            names = deep_dive_tickers(result)
            graph = TradingAgentsGraph(
                selected_analysts=("market", "news", "ai_bottleneck", "options"),
                config=DEFAULT_CONFIG,
            )
            lines += ["", "## LLM deep dives", ""]
            for t in names:
                final_state, decision = graph.propagate(t, summary["date"])
                lines.append(f"### {t} — {decision}\n")
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
    path = os.path.join(REPORTS_DIR, f"{summary['date']}.md")
    with open(path, "w") as f:
        f.write(report)

    _write_dashboard_snapshot(result, summary, ledger, stale)

    print(report)
    print(f"[report written to {path}; ledger at {LEDGER_PATH}]")
    return path


def _write_dashboard_snapshot(result, summary, ledger, stale: bool) -> None:
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
