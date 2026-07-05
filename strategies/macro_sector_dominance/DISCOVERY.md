# Strategy Discovery: macro_sector_dominance

**Date:** 2026-07-05
**Phase:** Discovery Complete (auto, from `Edge_config.yaml` + user's Master AI Trading Strategy synthesis docs)
**Engine:** pandas
**Project Type:** indicator (macro regime scoring + sector rotation)

---

## Core Hypothesis

Broad market regime (risk-on/risk-off, liquidity expanding/contracting, macro cycle position) is scored from macro factors (VIX, SMH 200-day trend as a semis/growth proxy, net liquidity, ISM, DXY). Capital rotates monthly into the top-3 ranked sectors by 3/6/12-month relative strength under the prevailing regime, rather than holding a static allocation. This feeds as an upstream macro/sector gate ahead of `ai_bottleneck_stocks`' individual-name selection (per the user's docs: "Stage 1: Macro Sector Filter" precedes "Stage 2: Relative Strength Screen" in the Security Selection Pipeline).

### Market Behavior Exploited
Sector leadership rotates with the macro cycle; a regime score built from volatility, liquidity, growth, and dollar-strength inputs identifies which sectors are favored before the rotation is obvious in price alone.

### Theoretical Basis
Standard macro-regime investing: risk appetite (VIX), growth-sensitive proxy (SMH 200d trend), liquidity conditions (net liquidity), manufacturing cycle (ISM), and dollar strength (DXY) are established macro regime inputs; combining them into a single score and ranking sectors against it is a systematic rotation approach.

---

## Regime Score (resolved — TECE v5.2 + IMRAS Fusion, sourced from the user's Master AI Trading Strategy v6.0 synthesis)

0-12 point scale:

| Component | Points | Threshold |
|-----------|--------|-----------|
| VIX | +3 | <18 |
| VIX | +1 | 18-25 |
| VIX | 0 | >25 |
| SMH > 50-DMA | +3 | sector trend |
| SMH > 200-DMA | +2 | core trend |
| SMH < 200-DMA | -2 | bear-market override |
| Fed Net Liquidity | +2 | expanding |
| Fed Net Liquidity | +1 | flat |
| Fed Net Liquidity | 0 | contracting |
| ISM New Orders | +1 | ≥50 |
| ISM New Orders | 0 | <50 |
| DXY | +1 | <105 & stable |
| DXY | 0 | ≥105 or rising fast |

**Regime labels and sizing:**

| Regime | Score | Gross Exposure | Max Margin | Thematic Cap |
|--------|-------|-----------------|------------|--------------|
| RISK-ON | 8-12 | 80% | 2.0x (max 2.5x) | 60% of equity |
| MIXED | 5-7 | 50% | 1.5x (max 1.8x) | 45% of equity |
| CAUTION | 2-4 | 25% | 1.0x (no margin) | 30% of equity |
| RISK-OFF | 0-1 | 0% | 0.5x | 0% |

**Hard kill switches (non-overridable):**
- VIX > 30 → instant RISK-OFF for 48h minimum
- SMH < 200-DMA → no new positions regardless of other signals
- 10Y Treasury > 5% AND ISM < 48 → defensive only / flat except hedges
- Financial Conditions tightening + VIX > 25 → RISK-OFF

**Net liquidity — resolved as a concrete formula, with a caveat:** the source docs cite "Fed Net Liquidity: Expanding/Flat/Contracting" only as a categorical input, inspired by Michael Howell's public commentary on the global liquidity cycle (his exact proprietary methodology isn't published). The standard, publicly computable proxy — **Fed Balance Sheet minus Treasury General Account (TGA) minus Reverse Repo (RRP)**, all from FRED — is used here as a concrete, buildable substitute for that categorical judgment call, not a claim to replicate Howell's specific model.

## Sector Rotation Logic (resolved — IMRAS Stage 1, from the same docs)

- Run macro filter, then **rank sectors by 3/6/12-month relative strength** (matches `sector_ranking_lookbacks_months: [3, 6, 12]` in `Edge_config.yaml` exactly).
- **Only the top 3 sectors advance** (matches `top_sectors: 3`).
- Rebalance monthly (matches `rotation_frequency: monthly`).
- Sector universe: standard GICS/sector-ETF style categories — the docs cite "Technology, Energy, Industrials" as the current (July 2026) leading sectors, implying the classic 11 SPDR sector ETF set (XLK, XLE, XLI, XLV, XLF, XLP, XLY, XLU, XLB, XLC, XLRE) rather than the AI-bottleneck-layer taxonomy used in `ai_bottleneck_stocks`.
- **Rank combination method:** still not explicitly formula-specified across the docs (they state the 3/6/12mo lookback and top-3 cutoff but not the exact weighting to merge 3 horizons into 1 rank). Reasonable default pending confirmation: equal-weighted average of percentile rank across the 3 lookback windows.

### Entry/Rebalance Signal Logic
```
regime_score = vix_score + smh_score + net_liquidity_score + ism_score + dxy_score
regime_label = RISK-ON (8-12) | MIXED (5-7) | CAUTION (2-4) | RISK-OFF (0-1)
sector_ranks = rank_sectors(lookbacks=[3,6,12], combine=equal_weighted_avg_percentile)  # combination weighting: assumed, not explicitly specified
monthly:
    hold top_sectors=3 sectors from sector_ranks, sized per regime_label's gross exposure/thematic cap
```

---

## Exit Conditions

Rotation strategy — exit = sector drops out of the monthly top-3 ranking, or a hard kill switch fires (forces RISK-OFF / flat regardless of sector ranking).

---

## Data Requirements

| Dataset | Resolution | Source | Status |
|---------|------------|--------|--------|
| VIX | Daily | FMP — **confirmed reachable**, verified live (15.81 pulled successfully) | ✅ Reachable |
| SMH price (50d/200d MA) | Daily | FMP — **blocked**, ETF quote endpoint hit a plan-tier gate ("requires higher plan") | ❌ Blocked (FMP plan upgrade needed) |
| Fed Balance Sheet, TGA, RRP (for net liquidity proxy) | Weekly | FRED — not tested this session, likely reachable via a FRED-connected tool if one exists, otherwise needs a new data source | Untested |
| ISM Manufacturing New Orders | Monthly | FMP `economics-indicators` — name lookup failed twice this session ("Invalid name"), unclear if wrong parameter string or plan-gated | ⚠️ Unresolved |
| DXY | Daily | FMP — **blocked**, forex quote endpoint hit the same plan-tier gate as SMH | ❌ Blocked (FMP plan upgrade needed) |
| 11 SPDR sector ETF prices | Daily | FMP — likely same ETF-quote plan gate as SMH, untested individually | ❌ Likely blocked |
| 10Y Treasury yield (for the hard kill switch) | Daily | FMP `treasury-rates` — **confirmed reachable**, verified live (full yield curve pulled) | ✅ Reachable |

### Data Scale
Small — all inputs are daily/weekly/monthly macro series. pandas is fine.

---

## Build Plan

**Complexity Level:** Simple-to-Medium. Methodology is now fully resolved (regime score, sizing table, kill switches, sector-rank spec, net-liquidity proxy). Remaining blocker is data access — 3 of 6 required feeds (SMH, DXY, sector ETFs) sit behind an FMP plan-tier gate; ISM needs a working parameter string; net liquidity needs a FRED-capable tool.

| Step | Description | Output |
|------|-------------|--------|
| 1 | Resolve FMP plan tier (or find an alternate free source) for ETF/forex quotes — unblocks SMH, DXY, all 11 sector ETFs | n/a — infra/subscription decision |
| 2 | Find working ISM parameter string or confirm it's plan-gated too | n/a |
| 3 | Source Fed Balance Sheet / TGA / RRP from FRED for the net-liquidity proxy | `src/features/net_liquidity.py` |
| 4 | Build regime score + sizing table | `src/features/regime_score.py` |
| 5 | Build 3/6/12-month sector rank (equal-weighted average assumption, confirm with user) | `src/features/sector_rank.py` |
| 6 | Backtest monthly rotation with regime-conditional sizing | `src/backtest.py` |

---

## Success Criteria
Not explicitly specified for this strategy alone — align to whatever bar is set for the portfolio as a whole (the user's Fund-of-Agents doc gives a portfolio-level honest target of Sharpe 1.0-1.5, 55-62% win rate, 18-25% max drawdown).

## Kill Criteria
- [ ] SMH/DXY/sector-ETF data remains inaccessible (no FMP upgrade, no alternate source found)
- [ ] Regime score shows no predictive relationship to realized sector leadership in backtest

---

## Questions for Research Phase

1. Upgrade FMP plan to unblock ETF/forex quotes, or is there a preferred alternate free data source for SMH/DXY/sector ETFs?
2. Confirm the equal-weighted-average assumption for combining the 3/6/12-month sector rank lookbacks, or specify a different weighting.
3. Confirm the 11 SPDR sector ETF set as the rotation universe (vs. a narrower/different set).

---

*Generated by CBT Framework /cbt:discover --auto, sourced from Edge_config.yaml + Parameters_ranges.yaml + user's uploaded Master AI Trading Strategy v6.0 synthesis (TECE v5.2 + IMRAS Fusion sections) + Bottleneck Capital Fund-of-Agents architecture doc*
