"""Agentic hedge fund orchestrator.

Mirrors the 6-layer cascade from the master strategy doc:

  L1 Chief Macro Officer .... regime.compute_regime
  L2 Bottleneck Analyst ..... universe.BOTTLENECK_CATEGORIES tagging
  L3 Security Selector ...... signals.compute_signals (0-100 + tiers)
  L4 Execution Desks ........ strategy rules inside backtest.run_backtest,
                              options overlay lives in the LLM options agent
  L5 Risk Governor .......... kill switches in regime + caps in backtest
  L6 Hermes (learning) ...... optimize.grid_search walk-forward

``run_daily`` is the live entry point: mechanical screen first, then the
top names can be handed to the TradingAgents LLM graph for a deep dive.
"""

from __future__ import annotations

import pandas as pd

from .data import PricePanel, load_panel
from .regime import RegimeParams, compute_regime
from .signals import SignalParams, compute_signals, tier_of
from .universe import ALL_SYMBOLS, CATEGORY_OF, UNIVERSE


def screen(
    panel: PricePanel | None = None,
    signal_params: SignalParams | None = None,
    regime_params: RegimeParams | None = None,
    top_n: int = 15,
) -> dict:
    """Regime + ranked watchlist + asymmetry flags as of the latest bar."""
    panel = panel or load_panel(ALL_SYMBOLS)
    sp = signal_params or SignalParams()
    sigs = compute_signals(panel, UNIVERSE, sp)
    reg = compute_regime(panel, UNIVERSE, regime_params)

    day = sigs.score.dropna(how="all").index[-1]
    row = sigs.score.loc[day].dropna().sort_values(ascending=False)

    table = pd.DataFrame(
        {
            "score": row.round(1),
            "tier": [tier_of(s, sp) for s in row],
            "category": [CATEGORY_OF.get(t, "?") for t in row.index],
            "trend_gate": sigs.trend_gate.loc[day, row.index],
            "asymmetric": sigs.asymmetric.loc[day, row.index],
            "rsi": sigs.components["rsi"].loc[day, row.index].round(1),
            "off_52w_high": (
                (1 - sigs.components["hi52"].loc[day, row.index]) * 100
            ).round(1),
        }
    ).head(top_n)

    return {
        "as_of": day,
        "regime": reg.loc[day].to_dict(),
        "watchlist": table,
        "asymmetric_setups": table[table["asymmetric"]].index.tolist(),
    }


def deep_dive_tickers(screen_result: dict, max_names: int = 3) -> list[str]:
    """Names worth sending into the TradingAgents LLM graph: top-scored
    names that pass the trend gate, asymmetric setups first."""
    wl = screen_result["watchlist"]
    gated = wl[wl["trend_gate"]]
    ordered = pd.concat([gated[gated["asymmetric"]], gated[~gated["asymmetric"]]])
    return ordered.index[:max_names].tolist()


def run_daily(deep_dive: bool = False, trade_date: str | None = None) -> dict:
    """Full daily workflow. With ``deep_dive`` the top names are run through
    the TradingAgents graph (requires LLM API keys; import stays lazy so the
    mechanical layer works standalone)."""
    result = screen()
    result["deep_dive_candidates"] = deep_dive_tickers(result)

    if result["regime"]["state"] == "RISK_OFF":
        result["action"] = "RISK_OFF: no new longs, review hedge book"
        return result
    result["action"] = (
        f"{result['regime']['state']}: deploy at "
        f"{result['regime']['multiplier']:.0%} gross into top gated names"
    )

    if deep_dive:
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        date = trade_date or str(result["as_of"].date())
        graph = TradingAgentsGraph(
            selected_analysts=("market", "news", "ai_bottleneck", "options"),
            config=DEFAULT_CONFIG,
        )
        reports = {}
        for ticker in result["deep_dive_candidates"]:
            final_state, decision = graph.propagate(ticker, date)
            reports[ticker] = decision
        result["llm_decisions"] = reports

    return result
