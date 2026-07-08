"""Strategy wrapper that reads knowledge-brain outputs and exposes them to TradingAgents."""
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

ROOT = Path(
    r"C:\Users\mcrea\AppData\Local\hermes\skills\knowledge-group-brains\output"
)
CAMPAIGNS_PATH = ROOT / "integrated_campaigns.json"
SIGNALS_PATH = ROOT / "signals.json"
REPORT_PATH = ROOT / "group_brain_report.json"


@dataclass(frozen=True)
class KnowledgeBrainStratContext:
    regime_score: int
    regime_name: str
    regime_delta: str
    themes: list[ThemeScore]
    options: list[OptionCandidate]
    alerts: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _theme_inputs_from_campaigns(payload: dict[str, Any]) -> dict[str, dict[str, float | int | None]]:
    theme_inputs: dict[str, dict[str, float | int | None]] = {}
    for c in payload.get("campaigns", []):
        ticker = str(c.get("ticker", "")).upper()
        if not ticker:
            continue
        theme = str(c.get("sleeve", "Thematic"))
        score = float(c.get("confluence_score", 50) or 50)
        inputs = theme_inputs.setdefault(theme, {})
        inputs["relative_strength"] = _clamp((inputs.get("relative_strength") or 0.0) + score * 0.20)
        inputs["analyst_revisions"] = _clamp((inputs.get("analyst_revisions") or 0.0) + score * 0.20)
        inputs["earnings_momentum"] = _clamp((inputs.get("earnings_momentum") or 0.0) + score * 0.15)
        inputs["institutional_buying"] = _clamp((inputs.get("institutional_buying") or 0.0) + score * 0.15)
        inputs["options_flow"] = _clamp((inputs.get("options_flow") or 0.0) + score * 0.10)
        inputs["volume_trend"] = _clamp((inputs.get("volume_trend") or 0.0) + score * 0.10)
        inputs["macro_tailwinds"] = _clamp((inputs.get("macro_tailwinds") or 0.0) + score * 0.05)
        inputs["news_catalyst"] = _clamp((inputs.get("news_catalyst") or 0.0) + score * 0.05)
    return theme_inputs


def _option_candidates_from_campaigns(payload: dict[str, Any]) -> list[OptionCandidate]:
    candidates: list[OptionCandidate] = []
    for c in payload.get("campaigns", []):
        ticker = str(c.get("ticker", "")).upper()
        if not ticker:
            continue
        structure = str(c.get("structure", "debit spread"))
        if "call debit" in structure.lower():
            opt_structure = OptionStructure.CALL_DEBIT_SPREAD
            bias = OptionBias.BULLISH
        elif "put debit" in structure.lower():
            opt_structure = OptionStructure.PUT_DEBIT_SPREAD
            bias = OptionBias.BULLISH
        elif "put credit" in structure.lower() or "cash secured put" in structure.lower():
            opt_structure = OptionStructure.CASH_SECURED_PUT
            bias = OptionBias.NEUTRAL_TO_BULLISH
        else:
            opt_structure = OptionStructure.CALL_DEBIT_SPREAD
            bias = OptionBias.NEUTRAL_TO_BULLISH
        score = float(c.get("confluence_score", 50) or 50)
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
                theme_score=score,
                technical_score=score,
                catalyst_score=score,
            )
        )
    return candidates


def build_knowledge_brain_strategy_context(config: Mapping[str, Any] | None = None) -> str:
    if config is None:
        config = {}
    campaign_data = _load_json(CAMPAIGNS_PATH)
    signals = _load_json(SIGNALS_PATH)
    report = _load_json(REPORT_PATH)
    regime_score = int(report.get("regime", {}).get("score", 50))
    regime_name = str(report.get("regime", {}).get("mood", "neutral"))
    regime_delta = str(report.get("regime", {}).get("delta", "stable"))
    theme_inputs = _theme_inputs_from_campaigns(campaign_data)
    for item in signals.get("themes", []):
        theme = str(item.get("theme", item.get("catalyst", "Thematic"))).split(":")[0].strip()
        score = float(item.get("score", 50))
        inputs = theme_inputs.setdefault(theme, {})
        inputs["macro_tailwinds"] = _clamp((inputs.get("macro_tailwinds") or 0.0) + score * 0.05)
        inputs["news_catalyst"] = _clamp((inputs.get("news_catalyst") or 0.0) + score * 0.05)
    theme_scores = rank_themes(theme_inputs)
    option_candidates = _option_candidates_from_campaigns(campaign_data)
    alerts = signals.get("alerts", [])
    ctx = KnowledgeBrainStratContext(
        regime_score=regime_score,
        regime_name=regime_name,
        regime_delta=regime_delta,
        themes=theme_scores,
        options=option_candidates,
        alerts=list(alerts[:20]),
    )
    lines = [
        "# Knowledge Brain Strategy Context",
        f"Regime: {ctx.regime_name} ({ctx.regime_score}/100)",
        f"Delta: {ctx.regime_delta}",
        "",
        "## Theme Scores",
    ]
    for t in ctx.themes[:20]:
        etfs = ", ".join(t.etfs) if t.etfs else "—"
        lines.append(f"- {t.theme}: {t.score:.1f} -> {t.action.value} | ETF: {etfs}")
    lines.extend(["", "## Option Candidates"])
    for cand in ctx.options[:20]:
        lines.append(
            f"- {cand.ticker}: {cand.structure.value} {cand.bias.value} expiry={cand.expiry} max_loss={cand.max_loss}"
        )
    lines.extend(["", "## Alerts"])
    for a in ctx.alerts[:20]:
        lines.append(f"- {a}")
    return "\n".join(lines)
