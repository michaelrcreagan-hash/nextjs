import json
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.strategies import rank_theme_stocks, score_theme

def _json_default(value):
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)

@tool
def score_omega_theme_rotation(
    theme: Annotated[str, "Omega theme key, e.g. ai_compute, power_infrastructure"],
    relative_strength: Annotated[float, "0-100 relative strength score"],
    analyst_revisions: Annotated[float, "0-100 analyst revision score"],
    earnings_momentum: Annotated[float, "0-100 earnings momentum score"],
    institutional_buying: Annotated[float, "0-100 institutional accumulation score"],
    options_flow: Annotated[float, "0-100 unusual options flow score"],
    volume_trend: Annotated[float, "0-100 volume expansion score"],
    macro_tailwinds: Annotated[float, "0-100 macro tailwind score"],
    news_catalyst: Annotated[float, "0-100 catalyst/news score"],
    above_50dma_pct: Annotated[float | None, "Percent of theme constituents above 50DMA"] = None,
    above_200dma_pct: Annotated[float | None, "Percent of theme constituents above 200DMA"] = None,
avg_relative_strength_vs_spy: Annotated[float | None, "Average theme relative strength vs SPY"] = None,
    improved_signals_json: Annotated[
        str | None,
        "Optional JSON object of capital-rotation signals; true values count toward the 5-of-7 upgrade",
    ] = None,
) -> str:
    """Score an Omega institutional theme rotation setup and return JSON."""
    improved_signals = {}
    if improved_signals_json:
        improved_signals = json.loads(improved_signals_json)

    result = score_theme(
        theme,
        {
            "relative_strength": relative_strength,
            "analyst_revisions": analyst_revisions,
            "earnings_momentum": earnings_momentum,
            "institutional_buying": institutional_buying,
            "options_flow": options_flow,
            "volume_trend": volume_trend,
            "macro_tailwinds": macro_tailwinds,
            "news_catalyst": news_catalyst,
        },
        above_50dma_pct=above_50dma_pct,
        above_200dma_pct=above_200dma_pct,
        avg_relative_strength_vs_spy=avg_relative_strength_vs_spy,
        improved_signals=improved_signals,
    )
    return json.dumps(result, default=_json_default, sort_keys=True)

@tool
def rank_omega_theme_stocks(
    theme: Annotated[str, "Omega theme key, e.g. ai_networking"],
    candidates_json: Annotated[
        str,
        (
            "JSON object keyed by ticker. Each value can include conviction, trend, "
            "relative_strength, analyst_revisions, fundamentals, institutional_buying, "
            "expected_return, and options_score on a 0-100 scale."
        ),
    ],
    limit: Annotated[int, "Maximum ranked stocks to return"] = 3,
) -> str:
    """Rank stock candidates inside an Omega theme and return JSON."""
    candidates = json.loads(candidates_json)
    ranked = rank_theme_stocks(theme, candidates, limit=limit)
    return json.dumps(ranked, default=_json_default, sort_keys=True)