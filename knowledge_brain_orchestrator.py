"""Knowledge-brain orchestrator for TradingAgents.

Reads:
  - knowledge-group-brains/output/group_brain_report.json
  - knowledge-group-brains/output/integrated_campaigns.json
  - knowledge-group-brains/output/signals.json

Outputs:
  - TradingAgents-compatible strategy context string
  - Ranked theme inputs for ``theme_rotation.rank_themes``
  - Ranked stock candidate inputs for ``theme_rotation.rank_theme_stocks``
  - Option scan candidates compatible with ``options_scanner.OptionCandidate``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.strategies.options_scanner import (
    OptionBias,
    OptionCandidate,
    OptionStructure,
    scan_defined_risk_options,
)
from tradingagents.strategies.theme_rotation import (
    ThemeScore,
    rank_theme_stocks,
    rank_themes,
    score_theme,
)

ROOT = (
    Path(__file__).resolve().parents[2]
    / "knowledge-group-brains"
    / "output"
)
REPORT_PATH = ROOT / "group_brain_report.json"
CAMPAIGNS_PATH = ROOT / "integrated_campaigns.json"
SIGNALS_PATH = ROOT / "signals.json"


@dataclass(frozen=True)
class KnowledgeBrainStratContext:
    regime_score: int
    regime_name: str
    regime_delta: str
    theme_scores: list[ThemeScore]
    stock_candidates: Mapping[str, list[dict[str, Any]]]
    option_candidates: list[OptionCandidate]
    alerts: list[str]
    source_report: Path
    campaigns_path: Path


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_signals() -> dict[str, Any]:
    return _load_json(SIGNALS_PATH)


def _load_campaigns() -> dict[str, Any]:
    return _load_json(CAMPAIGNS_PATH)


def _load_report() -> dict[str, Any]:
    return _load_json(REPORT_PATH)


def _regime_from_report(data: dict[str, Any]) -> tuple[int, str, str]:
    regime = data.get("regime", {})
    score = int(regime.get("score", 50))
    mood = str(regime.get("mood", "neutral"))
    delta = str(regime.get("delta", "stable"))
    return score, mood, delta


def _theme_inputs_from_report(data: dict[str, Any]) -> dict[str, Mapping[str, float | int | None]]:
    theme_inputs: dict[str, dict[str, float | int | None]] = {}
    for section in (
        "buy_signals",
        "avoid_signals",
        "rotate_signals",
        "tweak_signals",
        "consensus_themes",
        "group_reports",
    ):
        items = data.get(section)
        if not isinstance(items, list):
            continue
        for text in items:
            text = str(text)
            theme = text.split(":")[0].strip() if ":" in text else section.replace("_", " ").title()
            inputs = theme_inputs.setdefault(theme, {})
            inputs["news_catalyst"] = _clamp((inputs.get("news_catalyst") or 0.0) + 18.0)
            if "bullish" in text.lower():
                inputs["macro_tailwinds"] = _clamp((inputs.get("macro_tailwinds") or 0.0) + 20.0)
                inputs["earnings_momentum"] = _clamp((inputs.get("earnings_momentum") or 0.0) + 12.0)
            if "bearish" in text.lower():
                inputs["sector_etf_inflows"] = _clamp((inputs.get("sector_etf_inflows") or 0.0) - 10.0)
    return theme_inputs


def _campaigns_to_stock_candidates(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    for c in data.get("campaigns", []):
        ticker = str(c.get("ticker", "")).upper()
        if not ticker:
            continue
        theme = str(c.get("sleeve", "Thematic"))
        inputs = {
            "conviction": _clamp((c.get("confluence_score") or 50) * 0.35),
            "trend": _clamp((c.get("confluence_score") or 50) * 0.25),
            "relative_strength": _clamp((c.get("confluence_score") or 50) * 0.20),
            "analyst_revisions": _clamp((c.get("confluence_score") or 50) * 0.10),
            "fundamentals": _clamp((c.get("confluence_score") or 50) * 0.05),
            "institutional_buying": _clamp((c.get("confluence_score") or 50) * 0.025),
            "expected_return": _clamp((c.get("confluence_score") or 50) * 0.025),
            "options_score": _clamp((c.get("confluence_score") or 50) * 0.025),
        }
        candidates.setdefault(theme, []).append({"ticker": ticker, "inputs": inputs})
    return candidates


def _campaigns_to_option_candidates(data: dict[str, Any]) -> list[OptionCandidate]:
    candidates: list[OptionCandidate] = []
    for c in data.get("campaigns", []):
        ticker = str(c.get("ticker", "")).upper()
        if not ticker:
            continue
        structure = str(c.get("structure", "debit spread"))
        if "call debit" in structure.lower():
            opt_structure = OptionStructure.CALL_DEBIT_SPREAD
            bias = OptionBias.BULLISH
        elif "put credit" in structure.lower():
            opt_structure = OptionStructure.CASH_SECURED_PUT
            bias = OptionBias.BEARISH
        else:
            opt_structure = OptionStructure.CALL_DEBIT_SPREAD
            bias = OptionBias.BULLISH

        score = int(c.get("confluence_score", 50) or 50)
        candidates.append(
            OptionCandidate(
                ticker=ticker,
                structure=opt_structure,
                bias=bias,
                expiry="2026-10-16",
                dte=90,
                underlying_price=float(c.get("price", 100) or 100),
                long_strike=float(c.get("long_strike", 100) or 100),
                net_debit=float(c.get("net_debit", 3.0) or 3.0),
                short_strike=float(c.get("short_strike", 110) or 110) if "debit" in structure.lower() else None,
                max_profit=float(c.get("max_profit", 7.0) or 7.0),
                max_loss=float(c.get("max_loss", 3.0) or 3.0),
                theme_score=float(score),
                technical_score=float(score),
                catalyst_score=float(score),
            )
        )
    return candidates


def build_knowledge_brain_strategy_context(
    config: Mapping[str, Any] | None = None,
) -> str:
    if config is None:
        config = {}
    report = _load_report()
    signals = _load_signals()
    campaigns = _load_campaigns()
    regime_score, regime_mood, regime_delta = _regime_from_report(report)
    theme_inputs = _theme_inputs_from_report(report)
    if signals:
        themes = signals.get("themes", [])
        for item in themes:
            text = str(item.get("theme", item.get("catalyst", "")))
            score = int(item.get("score", 50))
            theme = text.split(":")[0].strip() if ":" in text else text.strip() or "Thematic"
            inputs = theme_inputs.setdefault(theme, {})
            inputs["macro_tailwinds"] = _clamp((inputs.get("macro_tailwinds") or 0.0) + score * 0.05)
            inputs["news_catalyst"] = _clamp((inputs.get("news_catalyst") or 0.0) + score * 0.05)
    theme_scores = rank_themes(theme_inputs)
    stock_candidates = _campaigns_to_stock_candidates(campaigns)
    option_candidates = _campaigns_to_option_candidates(campaigns)
    alerts = signals.get("alerts", [])
    ctx = KnowledgeBrainStratContext(
        regime_score=regime_score,
        regime_name=regime_mood,
        regime_delta=regime_delta,
        theme_scores=theme_scores,
        stock_candidates=stock_candidates,
        option_candidates=option_candidates,
        alerts=list(alerts[:20]),
        source_report=REPORT_PATH,
        campaigns_path=CAMPAIGNS_PATH,
    )
    lines = [
        "# Knowledge Brain Strategy Context",
        f"Regime: {ctx.regime_name} ({ctx.regime_score}/100)",
        f"Delta: {ctx.regime_delta}",
        "",
        "## Theme Scores",
    ]
    for t in ctx.theme_scores[:20]:
        etfs = ", ".join(t.etfs) if t.etfs else "—"
        lines.append(f"- {t.theme}: {t.score:.1f} -> {t.action.value} | ETF: {etfs}")
    lines.extend(
        [
            "",
            "## Ranked Stock Candidates by Theme",
            "Each theme lists up to 3 top-1 candidates from knowledge-brain campaigns.",
        ]
    )
    for theme, candidates in list(stock_candidates.items())[:10]:
        lines.append(f"- {theme}")
        for cand in candidates[:3]:
            lines.append(f"  - {cand['ticker']}: {cand['inputs']}")
    lines.extend(
        [
            "",
            "## Option Candidates",
            "Scan these with `options_scanner.scan_defined_risk_options()`.",
        ]
    )
    for cand in ctx.option_candidates[:10]:
        lines.append(
            f"- {cand.ticker}: {cand.structure.value} {cand.bias.value} expiry={cand.expiry} max_loss={cand.max_loss}"
        )
    lines.extend(
        [
            "",
            "## Alerts",
        ]
    )
    for a in ctx.alerts[:20]:
        lines.append(f"- {a}")
    return "\n".join(lines)


__all__ = [
    "KnowledgeBrainStratContext",
    "build_knowledge_brain_strategy_context",
]
