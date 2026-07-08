"""Defined-risk options scanner for asymmetric Omega trade expressions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class OptionStructure(str, Enum):
    LONG_CALL = "long_call"
    CALL_DEBIT_SPREAD = "call_debit_spread"
    PUT_DEBIT_SPREAD = "put_debit_spread"
    LONG_PUT = "long_put"
    CASH_SECURED_PUT = "cash_secured_put"


class OptionBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL_TO_BULLISH = "neutral_to_bullish"


@dataclass(frozen=True)
class OptionCandidate:
    ticker: str
    structure: OptionStructure
    bias: OptionBias
    expiry: str
    dte: int
    underlying_price: float
    long_strike: float
    net_debit: float
    short_strike: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    delta: float | None = None
    implied_vol: float | None = None
    realized_vol: float | None = None
    bid_ask_spread_pct: float | None = None
    open_interest: int | None = None
    volume: int | None = None
    catalyst_score: float | None = None
    theme_score: float | None = None
    technical_score: float | None = None


@dataclass(frozen=True)
class OptionScanResult:
    candidate: OptionCandidate
    score: float
    reward_to_risk: float
    max_loss: float
    max_profit: float | None
    liquidity_score: float
    vol_value_score: float
    notes: tuple[str, ...]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _default_max_profit(candidate: OptionCandidate) -> float | None:
    if candidate.max_profit is not None:
        return candidate.max_profit
    if candidate.structure in {OptionStructure.CALL_DEBIT_SPREAD, OptionStructure.PUT_DEBIT_SPREAD}:
        if candidate.short_strike is None:
            return None
        width = abs(candidate.short_strike - candidate.long_strike)
        return max(0.0, width - candidate.net_debit)
    return None


def _default_max_loss(candidate: OptionCandidate) -> float:
    if candidate.max_loss is not None:
        return candidate.max_loss
    if candidate.structure == OptionStructure.CASH_SECURED_PUT:
        return max(0.0, candidate.long_strike - candidate.net_debit)
    return max(0.0, candidate.net_debit)


def reward_to_risk(candidate: OptionCandidate) -> float:
    max_loss = _default_max_loss(candidate)
    if max_loss <= 0:
        return 0.0
    max_profit = _default_max_profit(candidate)
    if max_profit is None:
        if candidate.structure == OptionStructure.LONG_CALL:
            intrinsic_target = max(0.0, candidate.underlying_price * 1.15 - candidate.long_strike)
        elif candidate.structure == OptionStructure.LONG_PUT:
            intrinsic_target = max(0.0, candidate.long_strike - candidate.underlying_price * 0.85)
        else:
            intrinsic_target = candidate.net_debit
        max_profit = intrinsic_target
    return round(max_profit / max_loss, 2)


def liquidity_score(candidate: OptionCandidate) -> float:
    score = 0.0
    if candidate.open_interest is not None:
        score += _clamp(candidate.open_interest / 10.0, high=35.0)
    if candidate.volume is not None:
        score += _clamp(candidate.volume / 5.0, high=35.0)
    if candidate.bid_ask_spread_pct is not None:
        spread = candidate.bid_ask_spread_pct
        if spread <= 5.0:
            score += 30.0
        elif spread <= 10.0:
            score += 20.0
        elif spread <= 20.0:
            score += 10.0
    return round(_clamp(score), 2)


def vol_value_score(candidate: OptionCandidate) -> float:
    """Score option value from implied-vs-realized vol; cheap IV is favored for debit trades."""
    if candidate.implied_vol is None or candidate.realized_vol is None:
        return 50.0
    premium = candidate.implied_vol - candidate.realized_vol
    if candidate.structure in {
        OptionStructure.LONG_CALL,
        OptionStructure.CALL_DEBIT_SPREAD,
        OptionStructure.LONG_PUT,
        OptionStructure.PUT_DEBIT_SPREAD,
    }:
        return round(_clamp(70.0 - premium * 2.0), 2)
    return round(_clamp(50.0 + premium * 1.5), 2)


def _structure_score(candidate: OptionCandidate) -> float:
    if candidate.structure == OptionStructure.CALL_DEBIT_SPREAD:
        return 90.0
    if candidate.structure == OptionStructure.PUT_DEBIT_SPREAD:
        return 85.0
    if candidate.structure in {OptionStructure.LONG_CALL, OptionStructure.LONG_PUT}:
        return 75.0
    if candidate.structure == OptionStructure.CASH_SECURED_PUT:
        return 55.0
    return 50.0


def scan_defined_risk_options(
    candidates: Iterable[OptionCandidate],
    *,
    min_reward_to_risk: float = 2.0,
    max_loss_pct_underlying: float = 12.0,
) -> list[OptionScanResult]:
    """Rank defined-risk option candidates by asymmetry, liquidity, vol value, and thesis fit."""
    results: list[OptionScanResult] = []
    for candidate in candidates:
        max_loss = _default_max_loss(candidate)
        if max_loss <= 0:
            continue
        loss_pct = max_loss / candidate.underlying_price * 100.0
        rtr = reward_to_risk(candidate)
        notes: list[str] = []
        if rtr < min_reward_to_risk:
            notes.append("Rejected: reward/risk below threshold.")
        if loss_pct > max_loss_pct_underlying:
            notes.append("Rejected: max loss too large versus underlying.")

        liq = liquidity_score(candidate)
        vol = vol_value_score(candidate)
        thesis = _clamp(
            ((candidate.theme_score or 0.0) * 0.45)
            + ((candidate.technical_score or 0.0) * 0.35)
            + ((candidate.catalyst_score or 0.0) * 0.20)
        )
        asymmetry = _clamp(rtr * 20.0)
        structure = _structure_score(candidate)
        dte_score = _clamp(100.0 - abs(candidate.dte - 75) * 1.1)

        score = round(
            asymmetry * 0.30
            + liq * 0.20
            + vol * 0.20
            + thesis * 0.20
            + structure * 0.05
            + dte_score * 0.05,
            2,
        )
        if notes:
            score = min(score, 49.0)

        results.append(
            OptionScanResult(
                candidate=candidate,
                score=score,
                reward_to_risk=rtr,
                max_loss=max_loss,
                max_profit=_default_max_profit(candidate),
                liquidity_score=liq,
                vol_value_score=vol,
                notes=tuple(notes),
            )
        )
    return sorted(results, key=lambda item: item.score, reverse=True)
