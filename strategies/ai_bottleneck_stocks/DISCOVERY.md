# Strategy Discovery: ai_bottleneck_stocks

**Date:** 2026-07-05
**Phase:** Discovery Complete (auto, from `Edge_config.yaml`)
**Engine:** pandas
**Project Type:** indicator (composite technical/fundamental score)

---

## Core Hypothesis

Equities exposed to AI-infrastructure supply-chain bottlenecks (compute, power, memory, networking, etc.) that clear a composite quality/momentum bar (a "four factor" score and a "phase score", both defined by the user, not yet specified) and show technical strength (EMA stack alignment, RSI in a bullish-but-not-overbought band, elevated relative volume) are entered; positions are trimmed on deteriorating breadth (sell-composite count) or after a fixed post-earnings decay window.

### Market Behavior Exploited
Persistent, multi-quarter demand overhang in AI-infrastructure names produces trending moves; the composite score + technical filter is meant to time entries into that trend rather than chase it blind.

### Theoretical Basis
Momentum/trend persistence in a structurally supply-constrained sector, filtered by a fundamentals-based composite ("four factor") to avoid low-quality names riding the same narrative.

---

## Entry Conditions

| Condition | Description | Data Required |
|-----------|-------------|---------------|
| Four-factor score | Composite score ≥ `four_factor_threshold` (**undefined** — factors not specified by user; needs definition in `/cbt:research`) | Undefined — likely fundamentals + technicals blend |
| Phase score | Composite score ≥ `phase_score_threshold` (**undefined** — same as above) | Undefined |
| EMA stack | Price above EMA(8) above EMA(21) above EMA(50) above EMA(200) (bullish stack) | Daily OHLCV |
| RSI band | RSI(14) within `rsi_range` | Daily OHLCV |
| Relative volume | RVOL within `rvol_range` (elevated but not blow-off) | Daily volume + average volume baseline |

**Point estimates (`Edge_config.yaml`):** `four_factor_threshold: 16`, `phase_score_threshold: 40`, `ema_stack: [8, 21, 50, 200]`, `rsi_range: [50, 65]`, `rvol_range: [1.5, 2.0]`, `max_position: 0.06` (6% of capital per position).

**Tunable grids (`Parameters_ranges.yaml`):** `four_factor_threshold: [14, 16, 18, 20]`, `phase_score_threshold: [35, 40, 45]`, `rsi_min: [45, 50, 55]`, `rsi_max: [60, 65, 70]`, `rvol_min: [1.2, 1.5, 1.8]`, `rvol_max: [1.8, 2.0, 2.5]`.

### Entry Signal Logic
```
if four_factor_score >= four_factor_threshold
   and phase_score >= phase_score_threshold
   and EMA(8) > EMA(21) > EMA(50) > EMA(200)
   and rsi_range[0] <= RSI(14) <= rsi_range[1]
   and rvol_range[0] <= RVOL <= rvol_range[1]:
        enter(size = min(max_position, sizing_rule))
```

**Open item:** `four_factor_threshold` and `phase_score_threshold` reference composite scores with no factor definitions supplied. Cannot be implemented in `/cbt:build` until the underlying factors (what four? what phases?) are specified.

---

## Exit Conditions

### Take Profit / General Exit
- **Sell-composite count:** exit when `sell_composite_count` reaches 3 (undefined composite — same open item as entry factors: what conditions increment this counter?).
- **Time-based:** exit `days_post_earnings: 60` days after the most recent earnings report, regardless of price.

### Stop Loss
Not specified in `Edge_config.yaml` — no fixed %/ATR stop defined for this strategy. Flag for `/cbt:research` or a follow-up discovery pass before `/cbt:build`.

---

## Data Requirements

| Dataset | Resolution | Source | Status |
|---------|------------|--------|--------|
| Daily OHLCV (candidate universe) | Daily | FMP or similar | [ ] Need |
| Earnings dates | Per-ticker event | FMP calendar | [ ] Need |
| Four-factor score inputs | Unknown (fundamentals?) | Undefined | [ ] Need — factors unspecified |
| Phase-score inputs | Unknown | Undefined | [ ] Need — factors unspecified |
| Candidate universe definition | — | Undefined | [ ] Need — which tickers count as "AI bottleneck stocks"? |

### Data Scale
Estimated small (<1M rows for a daily-bar equity universe) — pandas is fine.

---

## Build Plan

**Complexity Level:** Medium, blocked on two undefined composite scores and an undefined ticker universe.

| Step | Description | Output |
|------|-------------|--------|
| 1 | Define candidate universe (which AI-bottleneck names) | `Data/universe.csv` |
| 2 | Define four-factor score methodology | `src/features/four_factor.py` |
| 3 | Define phase-score methodology | `src/features/phase_score.py` |
| 4 | Define sell-composite-count methodology | `src/features/sell_composite.py` |
| 5 | Source daily OHLCV + earnings dates for universe | `Data/*.csv` |
| 6 | Build EMA stack / RSI / RVOL technical filters | `src/features/technicals.py` |
| 7 | Combine into composite entry/exit signal | `src/signals.py` |
| 8 | Backtest with 6% max position sizing | `src/backtest.py` |

---

## Success Criteria
Not specified — carry forward a default bar (Sharpe > 1.5) pending user input, or align to whatever bar is set for the portfolio as a whole.

## Kill Criteria
- [ ] Four-factor / phase-score / sell-composite definitions never get specified (strategy cannot be built as-is)
- [ ] Candidate universe too small/illiquid to backtest meaningfully

---

## Questions for Research Phase

1. What are the four factors in "four factor score", and how is "phase score" computed?
2. What defines the AI-bottleneck stock universe (specific tickers, or a screening rule)?
3. What increments the "sell composite count"?

---

*Generated by CBT Framework /cbt:discover --auto, sourced from Edge_config.yaml + Parameters_ranges.yaml*
