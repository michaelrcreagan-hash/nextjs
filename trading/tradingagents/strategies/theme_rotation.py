"""Institutional theme rotation engine for Omega-style AI bottleneck investing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ThemeAction(str, Enum):
    INCREASE = "Increase allocation"
    MAINTAIN = "Maintain"
    WATCH = "Watch"
    REDUCE = "Reduce exposure"


THEME_SCORE_WEIGHTS: dict[str, float] = {
    "relative_strength": 20.0,
    "analyst_revisions": 20.0,
    "earnings_momentum": 15.0,
    "institutional_buying": 15.0,
    "options_flow": 10.0,
    "volume_trend": 10.0,
    "macro_tailwinds": 5.0,
    "news_catalyst": 5.0,
}


THEME_ETF_MAP: dict[str, tuple[str, ...]] = {
    "ai_compute": ("SMH", "SOXX"),
    "semiconductor_equipment": ("SMH", "SOXX"),
    "hbm_memory": ("SOXX", "SMH"),
    "advanced_packaging": ("SMH", "SOXX"),
    "ai_networking": ("SMH", "QQQ"),
    "optical_networking": ("IYZ", "QQQ"),
    "power_infrastructure": ("XLU", "PAVE"),
    "utilities": ("XLU",),
    "nuclear": ("URA", "URNM"),
    "data_centers": ("VPN", "SRVR"),
    "cybersecurity": ("CIBR", "HACK"),
    "enterprise_ai": ("AIQ", "QQQ"),
    "defense_ai": ("ITA", "XAR"),
    "robotics": ("BOTZ", "ROBO"),
    "industrial_automation": ("ROBO", "XLI"),
    "digital_infrastructure": ("VPN", "SRVR"),
    "cloud": ("SKYY", "WCLD"),
    "tokenization": ("BITQ", "IBIT"),
    "digital_assets": ("BITQ", "IBIT"),
    "bitcoin_infrastructure": ("BITQ", "IBIT"),
    "financial_infrastructure": ("FINX", "XLF"),
    "autonomous_vehicles": ("DRIV", "IDRV"),
    "space": ("ARKX", "ITA"),
    "biotech_ai": ("IBB", "XBI"),
}


AI_VALUE_CHAIN: dict[str, tuple[str, ...]] = {
    "NVDA": ("AI Compute", "Inference", "AI Factory"),
    "TSM": ("Manufacturing", "Advanced Packaging", "AI Compute"),
    "AVGO": ("Networking", "Custom Silicon", "AI Compute"),
    "AMD": ("AI Compute", "Inference", "Accelerators"),
    "MU": ("HBM Memory", "Memory Bottleneck"),
    "MRVL": ("Networking", "Custom Silicon", "Inference"),
    "ANET": ("AI Networking", "Ethernet Fabric"),
    "VRT": ("Power", "Cooling", "Data Centers"),
    "VST": ("Power", "Electricity", "AI Load Growth"),
    "CEG": ("Nuclear", "Power", "AI Load Growth"),
    "ETN": ("Grid", "Electrical Equipment", "Power Infrastructure"),
    "PLTR": ("Defense AI", "Enterprise AI", "Government"),
    "COIN": ("Tokenization", "Digital Assets", "Financial Infrastructure"),
    "MSTR": ("Bitcoin Infrastructure", "Digital Assets"),
}


@dataclass(frozen=True)
class ThemeScore:
    theme: str
    score: float
    action: ThemeAction
    inputs: Mapping[str, float | int | None]
    leadership_pass: bool | None = None
    upgraded_by_rotation: bool = False
    etfs: tuple[str, ...] = ()


@dataclass(frozen=True)
class StockCandidateScore:
    ticker: str
    theme: str
    score: float
    rank: int
    ai_layers: tuple[str, ...]
    inputs: Mapping[str, float | int | None]


def _clamp_score(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(100.0, float(value)))


def score_theme(
    theme: str,
    inputs: Mapping[str, float | int | None],
    *,
    above_50dma_pct: float | int | None = None,
    above_200dma_pct: float | int | None = None,
    avg_relative_strength_vs_spy: float | int | None = None,
    improved_signals: Mapping[str, bool] | None = None,
) -> ThemeScore:
    """Score one secular theme using the pasted institutional rotation weights."""
    raw_score = sum(_clamp_score(inputs.get(k)) * (w / 100.0) for k, w in THEME_SCORE_WEIGHTS.items())
    leadership_pass = evaluate_theme_leadership(
        above_50dma_pct=above_50dma_pct,
        above_200dma_pct=above_200dma_pct,
        avg_relative_strength_vs_spy=avg_relative_strength_vs_spy,
    )
    if leadership_pass is False:
        raw_score = min(raw_score, 79.0)

    upgraded = capital_rotation_upgrade(improved_signals or {})
    if upgraded:
        raw_score = min(100.0, raw_score + 5.0)

    score = round(raw_score, 2)
    return ThemeScore(
        theme=theme,
        score=score,
        action=theme_action(score),
        inputs=inputs,
        leadership_pass=leadership_pass,
        upgraded_by_rotation=upgraded,
        etfs=THEME_ETF_MAP.get(theme, ()),
    )


def theme_action(score: float | int) -> ThemeAction:
    score = _clamp_score(score)
    if score > 90.0:
        return ThemeAction.INCREASE
    if score >= 80.0:
        return ThemeAction.MAINTAIN
    if score >= 70.0:
        return ThemeAction.WATCH
    return ThemeAction.REDUCE


def evaluate_theme_leadership(
    *,
    above_50dma_pct: float | int | None,
    above_200dma_pct: float | int | None,
    avg_relative_strength_vs_spy: float | int | None,
) -> bool | None:
    """Return whether breadth/leadership gates pass, or None when insufficient."""
    if above_50dma_pct is None or above_200dma_pct is None or avg_relative_strength_vs_spy is None:
        return None
    return (
        float(above_50dma_pct) > 60.0
        and float(above_200dma_pct) > 70.0
        and float(avg_relative_strength_vs_spy) > 0.0
    )


def capital_rotation_upgrade(improved_signals: Mapping[str, bool]) -> bool:
    """Upgrade a theme when at least five of seven capital-rotation signals improve."""
    tracked = (
        "sector_etf_inflows",
        "analyst_upgrades",
        "earnings_revisions",
        "relative_strength_acceleration",
        "unusual_options_activity",
        "institutional_accumulation",
        "volume_expansion",
    )
    return sum(1 for key in tracked if improved_signals.get(key)) >= 5


def score_stock_candidate(
    ticker: str,
    theme: str,
    inputs: Mapping[str, float | int | None],
) -> float:
    """Rank stocks inside a theme using conviction/trend/revision/flow/option inputs."""
    weights = {
        "conviction": 25.0,
        "trend": 15.0,
        "relative_strength": 15.0,
        "analyst_revisions": 15.0,
        "fundamentals": 10.0,
        "institutional_buying": 10.0,
        "expected_return": 5.0,
        "options_score": 5.0,
    }
    return round(sum(_clamp_score(inputs.get(k)) * (w / 100.0) for k, w in weights.items()), 2)


def rank_theme_stocks(
    theme: str,
    candidates: Mapping[str, Mapping[str, float | int | None]],
    *,
    limit: int = 3,
) -> list[StockCandidateScore]:
    scored = [
        StockCandidateScore(
            ticker=ticker,
            theme=theme,
            score=score_stock_candidate(ticker, theme, inputs),
            rank=0,
            ai_layers=AI_VALUE_CHAIN.get(ticker.upper(), ()),
            inputs=inputs,
        )
        for ticker, inputs in candidates.items()
    ]
    scored.sort(key=lambda item: item.score, reverse=True)
    return [
        StockCandidateScore(
            ticker=item.ticker,
            theme=item.theme,
            score=item.score,
            rank=i + 1,
            ai_layers=item.ai_layers,
            inputs=item.inputs,
        )
        for i, item in enumerate(scored[:limit])
    ]


def rank_themes(theme_inputs: Mapping[str, Mapping[str, float | int | None]]) -> list[ThemeScore]:
    scores = [score_theme(theme, inputs) for theme, inputs in theme_inputs.items()]
    return sorted(scores, key=lambda item: item.score, reverse=True)
