"""Omega Fund strategy profile.

Implements the institutional AI bottleneck strategy from OMEGA_FUND_2026_v3.
Maps seven departments into deterministic rules the LLM agents can follow.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class OmegaPositionTier:
    name: str
    min_score: float
    max_position_pct: float


@dataclass(frozen=True)
class OmegaLayer:
    name: str
    status: str
    tickers: tuple[str, ...]
    etf: tuple[str, ...]
    allocation_pct: float


@dataclass(frozen=True)
class OmegaStrategyProfile:
    name: str
    objective: str
    weights: Mapping[str, float]
    macro_growth_gate: float
    revision_gate: float
    variant_gate: float
    single_position_max_pct: float
    theme_max_pct: float
    drawdown_reduce_pct: float
    drawdown_freeze_pct: float
    top_bottlenecks: int
    layers: tuple[OmegaLayer, ...]
    tiers: tuple[OmegaPositionTier, ...]
    portfolio_buckets: Mapping[str, float]


DEFAULT_OMEGA_PROFILE = OmegaStrategyProfile(
    name="Omega Fund",
    objective=(
        "Maximize portfolio CAGR, risk-adjusted returns, and win rate while "
        "minimizing drawdown, correlation risk, and theme concentration risk."
    ),
    weights={
        "macro": 0.25,
        "capex": 0.20,
        "revision": 0.20,
        "bottleneck": 0.15,
        "flow": 0.10,
        "variant": 0.05,
        "technical": 0.05,
    },
    macro_growth_gate=60.0,
    revision_gate=70.0,
    variant_gate=20.0,
    single_position_max_pct=10.0,
    theme_max_pct=25.0,
    drawdown_reduce_pct=15.0,
    drawdown_freeze_pct=20.0,
    top_bottlenecks=3,
    layers=(
        OmegaLayer("Power/Grid", "BOTTLENECK", ("VST", "CEG", "CCJ", "GEV", "ETN", "OKLO", "SMR"), ("XLU", "URNM"), 12.0),
        OmegaLayer("Networking/Optical", "BOTTLENECK", ("ANET", "COHR", "LITE", "MRVL", "ALAB", "CRDO"), ("CCNR",), 10.0),
        OmegaLayer("Memory/HBM", "TIGHT", ("MU", "WDC", "STX"), ("SOXX",), 10.0),
        OmegaLayer("Compute/Packaging", "SCALING", ("NVDA", "TSM", "AVGO", "AMD"), ("SMH", "SOXX"), 12.0),
        OmegaLayer("Data Centers/Agents", "EMERGING", ("CORZ", "WULF", "TSLA", "MSFT", "META"), ("BOTZ", "AIQ"), 8.0),
    ),
    tiers=(
        OmegaPositionTier("OMEGA", 90.000001, 10.0),
        OmegaPositionTier("A", 80.0, 7.0),
        OmegaPositionTier("B", 70.0, 5.0),
        OmegaPositionTier("REJECT", 0.0, 0.0),
    ),
    portfolio_buckets={
        "current_bottleneck": 40.0,
        "emerging_bottleneck": 20.0,
        "core_compounders": 20.0,
        "sp500_alpha": 10.0,
        "cash": 10.0,
    },
)


def _normalise_score(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(100.0, float(value)))


def calculate_omega_score(
    scores: Mapping[str, float | int | None],
    profile: OmegaStrategyProfile = DEFAULT_OMEGA_PROFILE,
) -> float:
    """Return the weighted Omega score on a 0-100 scale."""
    return round(
        sum(_normalise_score(scores.get(factor)) * weight for factor, weight in profile.weights.items()),
        2,
    )


def omega_gate_failures(
    scores: Mapping[str, float | int | None],
    profile: OmegaStrategyProfile = DEFAULT_OMEGA_PROFILE,
) -> list[str]:
    """Return human-readable gate failures for available factor scores."""
    failures: list[str] = []
    macro = scores.get("macro")
    if macro is not None and _normalise_score(macro) < profile.macro_growth_gate:
        failures.append(
            f"Macro gate failed: macro score {float(macro):.1f} < {profile.macro_growth_gate:.0f}."
        )
    revision = scores.get("revision")
    if revision is not None and _normalise_score(revision) < profile.revision_gate:
        failures.append(
            f"Revision gate failed: revision score {float(revision):.1f} < {profile.revision_gate:.0f}."
        )
    variant = scores.get("variant")
    if variant is not None and _normalise_score(variant) <= profile.variant_gate:
        failures.append(
            f"Variant gate failed: variant score {float(variant):.1f} <= {profile.variant_gate:.0f}."
        )
    return failures


def omega_position_tier(
    omega_score: float | int,
    profile: OmegaStrategyProfile = DEFAULT_OMEGA_PROFILE,
) -> OmegaPositionTier:
    score = _normalise_score(omega_score)
    for tier in profile.tiers:
        if score >= tier.min_score:
            return tier
    return profile.tiers[-1]


def _format_buckets(buckets: Mapping[str, float]) -> str:
    return ", ".join(f"{name.replace('_', ' ')} {pct:.0f}%" for name, pct in buckets.items())


def render_omega_strategy_context(
    profile: OmegaStrategyProfile = DEFAULT_OMEGA_PROFILE,
) -> str:
    weights = ", ".join(
        f"{factor} {weight:.0%}" for factor, weight in profile.weights.items()
    )
    tiers = "; ".join(
        f"{tier.name}: score >= {tier.min_score:g}, max {tier.max_position_pct:.0f}%"
        for tier in profile.tiers
        if tier.name != "REJECT"
    )
    buckets = _format_buckets(profile.portfolio_buckets)
    layer_lines = "\n".join(
        f"| {layer.name} | {layer.status} | {', '.join(layer.tickers)} |"
        for layer in profile.layers
    )
    watchlist_core = ", ".join(
        ["NVDA", "TSM", "MU", "AVGO", "ANET", "VRT", "VST", "CEG", "MSTR", "BTC", "CCJ", "MSFT"]
    )
    return f"""## Omega Fund Strategy Profile

Objective: {profile.objective}

Decision frame: ask where capital is flowing, where scarcity is emerging, where earnings revisions are accelerating, and which companies have institutional accumulation before broad recognition.

Required operating gates:
- Macro regime must be risk-on for growth trades; reject or hold cash when macro score is below {profile.macro_growth_gate:.0f}.
- Revision score must be at least {profile.revision_gate:.0f}; require positive company, industry, and theme revisions when evidence is available.
- Variant perception must be above {profile.variant_gate:.0f}; prefer Reality > Expectations setups.
- Only allocate to the top {profile.top_bottlenecks} bottlenecks by scarcity ranking.

Omega score weights: {weights}.

Position tiers: {tiers}; below 70 is reject.

Portfolio construction target: {buckets}.

Institutional theme rotation layer:
- Score themes before stocks: relative strength 20%, analyst revisions 20%, earnings momentum 15%, institutional buying 15%, options flow 10%, volume trend 10%, macro tailwinds 5%, news/catalyst 5%.
- Increase allocation only when a theme scores above 90; maintain 80-90; watch 70-80; reduce below 70.
- Require theme leadership where available: more than 60% of constituents above 50DMA, more than 70% above 200DMA, and average relative strength above SPY.
- Benchmark every stock against its closest theme ETF, QQQ, and SPY rather than only the S&P 500.
- Advance only the top 3 stocks inside each leading theme.

Defined-risk options layer:
- Use options only after the underlying equity clears the theme, revision, technical, and risk gates.
- Prefer asymmetric, defined-risk structures: call debit spreads, put debit spreads, and carefully sized long calls/puts.
- Rank options by reward/risk, max loss, liquidity, implied-vs-realized volatility, catalyst fit, DTE, and theme/technical confluence.
- Do not recommend undefined-risk option structures; missing option-chain data is an implementation gap, not a reason to fabricate a trade.

Five-layer rotation map:
| Layer | Status 2026 | Primary Stocks |
|-------|-------------|----------------|
{layer_lines}

Core watchlist anchors: {watchlist_core}.

Risk rules:
- Single position max: {profile.single_position_max_pct:.0f}%.
- Theme max: {profile.theme_max_pct:.0f}%.
- If portfolio drawdown exceeds {profile.drawdown_reduce_pct:.0f}%, reduce exposure by 50%.
- If portfolio drawdown exceeds {profile.drawdown_freeze_pct:.0f}%, freeze new positions.

Agent responsibilities:
- Macro: classify risk_on, neutral, or risk_off using liquidity, financial conditions, DXY, VIX, ISM, rates, and broad macro stress.
- AI capex: look for hyperscaler capex growth, acceleration, AI/inference/GPU/data-center/power/networking mentions, and guidance revisions.
- Bottleneck migration: rank compute, networking, memory, power, cooling, data centers, robotics, and physical AI; prioritize scarcity with revisions and flows.
- Revision: treat EPS, revenue, EBITDA, and guidance revisions as the highest-signal factor.
- Flow: prefer ownership growth, new fund buyers, options sweeps, dark pools, 13F/SEC evidence, and institutional accumulation.
- Variant perception: seek reality exceeding expectations across fundamentals, narrative, social/news attention, and Google Trends-like demand.
- Technical: require relative strength in the top quintile when evidence exists; prefer RVOL 1.5-2.5 and ADR greater than ATR.

When evidence is incomplete, say what is missing and do not award score credit for unavailable factors."""


def build_strategy_context(config: Mapping[str, object]) -> str:
    """Build the configured strategy prompt context."""
    profile = str(config.get("strategy_profile") or "").strip().lower()
    if profile == "omega":
        return render_omega_strategy_context()

    custom = config.get("strategy_context")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return ""
