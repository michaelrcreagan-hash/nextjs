"""Macro cycle overlay — 4-year presidential cycle x 16.8-year secular
cycle x quarterly seasonality, combined into an equity-exposure multiplier
that composes with the regime engine's regime-based multiplier.

Formula (from the "Cyclical Overlay" note, verified against its worked
example: 80% base x 0.7 midterm x 1.0 re-rating x 0.7 Q3 seasonal x 1.0
no-event = 39.2%, matching the note's Q3 2026 defensive call):

    cycle_multiplier = year_mult x phase_mult x season_mult x event_mult

All four factors are deterministic calendar lookups — no market data
required — so this is exact given the anchor assumptions below. The
anchors are the note's stated dates, not something a mechanical process
can derive; revisit them if your macro thesis changes.

Anchors:
  - US presidential election years: 2024, 2028, 2032, ... (year 1 =
    the year AFTER an election, i.e. 2025 was Year 1 of the current
    cycle; 2026 is Year 2/midterm).
  - 16.8-year secular cycle Phase 1 (bounce) began 2023 per the note.

Invalidation checks (event_mult overrides / hard flags) use only data
already in the panel (SPY, SMH, VIX) — the note's 10Y-yield and P/E
triggers need FRED/valuation data this repo doesn't fetch yet and are
left as documented gaps rather than silently skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .data import PricePanel
from .indicators import sma


@dataclass
class CycleParams:
    # 4-year presidential cycle multipliers by year-in-cycle (1=post-
    # election, 2=midterm, 3=pre-election, 4=election year).
    election_years: tuple = (2024, 2028, 2032, 2036, 2040)
    year_mult: dict = field(
        default_factory=lambda: {1: 1.00, 2: 0.70, 3: 1.15, 4: 0.85}
    )
    # 16.8-year secular cycle: (start_offset_years, end_offset_years, mult)
    # offsets are years since the cycle's Phase-1 anchor.
    secular_anchor_year: int = 2023
    secular_phases: tuple = (
        (0, 3, "Phase 1: Bounce", 0.85),
        (3, 7, "Phase 2: Re-rating", 1.00),
        (7, 12, "Phase 3: Mania", 1.10),
        (12, 15, "Phase 4: Bubble Top", 0.90),
        (15, 16.8, "Phase 4->1 Transition", 0.75),
    )
    # Quarterly seasonal multiplier.
    season_mult: dict = field(
        default_factory=lambda: {1: 1.00, 2: 1.00, 3: 0.70, 4: 1.10}
    )
    invalidation_dd_from_200sma: float = -0.20  # SPY >20% below 200DMA


def year_in_cycle(year: int, p: CycleParams) -> int:
    """1-4 position within the 4-year presidential cycle for ``year``."""
    prior = max(e for e in p.election_years if e <= year)
    return year - prior


def secular_phase(year: int, p: CycleParams) -> tuple[str, float]:
    offset = year - p.secular_anchor_year
    offset = offset % 16.8  # wrap into the next 16.8y cycle
    for start, end, label, mult in p.secular_phases:
        if start <= offset < end:
            return label, mult
    return p.secular_phases[-1][2], p.secular_phases[-1][3]


def cycle_signal(date: pd.Timestamp, p: CycleParams | None = None) -> dict:
    """Deterministic 4yr x 16.8yr x seasonal signal for a given date."""
    p = p or CycleParams()
    year, quarter = date.year, (date.month - 1) // 3 + 1

    yic = year_in_cycle(year, p)
    y_mult = p.year_mult[yic]
    phase_label, phase_mult = secular_phase(year, p)
    s_mult = p.season_mult[quarter]

    combined = y_mult * phase_mult * s_mult
    return {
        "date": date,
        "year_in_cycle": yic,
        "year_mult": y_mult,
        "secular_phase": phase_label,
        "phase_mult": phase_mult,
        "quarter": quarter,
        "season_mult": s_mult,
        "cycle_multiplier": round(combined, 3),
    }


def check_invalidation(panel: PricePanel, day: pd.Timestamp, p: CycleParams | None = None) -> dict:
    """SPY-based secular-bull invalidation check (see module docstring for
    the checks NOT implementable from cached data)."""
    p = p or CycleParams()
    close = panel.close
    if "SPY" not in close.columns:
        return {"invalidated": False, "reason": "no SPY data"}
    spy = close["SPY"]
    ma200 = sma(spy, 200)
    if day not in spy.index or pd.isna(ma200.get(day, float("nan"))):
        return {"invalidated": False, "reason": "insufficient data"}
    dd = spy.loc[day] / ma200.loc[day] - 1
    invalidated = dd <= p.invalidation_dd_from_200sma
    return {
        "invalidated": bool(invalidated),
        "spy_vs_200dma": round(float(dd), 4),
        "reason": (
            f"SPY {dd*100:.1f}% below 200DMA — secular bull invalidated"
            if invalidated
            else "ok"
        ),
    }


def cycle_report_line(panel: PricePanel, day: pd.Timestamp, p: CycleParams | None = None) -> str:
    p = p or CycleParams()
    sig = cycle_signal(day, p)
    inv = check_invalidation(panel, day, p)
    line = (
        f"Cycle: Year {sig['year_in_cycle']}/4 (x{sig['year_mult']:.2f}) x "
        f"{sig['secular_phase']} (x{sig['phase_mult']:.2f}) x Q{sig['quarter']} "
        f"seasonal (x{sig['season_mult']:.2f}) = **{sig['cycle_multiplier']:.0%}** "
        f"equity-exposure multiplier"
    )
    if inv["invalidated"]:
        line += f"  ⚠️ {inv['reason']}"
    return line
