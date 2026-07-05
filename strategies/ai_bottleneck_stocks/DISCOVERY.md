# Strategy Discovery: ai_bottleneck_stocks

**Date:** 2026-07-05
**Phase:** Discovery Complete (auto, from `Edge_config.yaml` + user's Master AI Trading Strategy synthesis docs)
**Engine:** pandas
**Project Type:** indicator (composite technical/fundamental score)

---

## Core Hypothesis

Equities exposed to AI-infrastructure supply-chain bottlenecks (compute, power, memory, networking, optics, nuclear) that clear a composite fundamental/momentum bar (Four-Factor Model) and rank highly on where AI capex is currently constrained (Phase Score) are entered when technicals confirm (EMA stack, RSI, RVOL); positions are trimmed on a weighted sell-composite trigger or after a fixed post-earnings decay window.

### Market Behavior Exploited
Persistent, multi-quarter demand overhang in AI-infrastructure names (hyperscaler capex growing faster than physical supply of compute, power, memory, networking) produces trending moves. The composite score + technical filter times entries into the trend; earnings-revision momentum is cited (per the user's docs, referencing Jegadeesh-Titman and Novy-Marx) as the most empirically robust of the four factors.

### Theoretical Basis
Momentum/trend persistence in a structurally supply-constrained sector, filtered by a fundamentals-based Four-Factor composite to avoid low-quality names riding the same narrative, further filtered by which specific bottleneck layer (Phase) is currently binding.

**Honest framing from the user's own reference material (Bottleneck Capital Fund-of-Agents doc):** this is fundamentally one correlated bet on AI capex. Published multi-agent/LLM trading backtests reporting Sharpe 5-8 or 78-91% win rates are called out in that doc as overfit/not deployable once realistic costs and information-leakage controls are applied — realistic expectations are ~55-62% win rate, ~1.0-1.5 Sharpe, 18-25% max drawdown, deployable via a real coded backtest with walk-forward validation, not an LLM-estimated one. This project should build and run an actual backtest (`/cbt:build`, `/cbt:run`) rather than accept narrative performance claims from the source documents.

---

## Entry Conditions

| Condition | Description | Data Required |
|-----------|-------------|---------------|
| Four-Factor score | Composite score ≥ `four_factor_threshold`, see formula below | Earnings estimate revisions, RS vs SMH/SPX, supply-chain/scarcity data, daily OHLCV |
| Phase score | Composite score ≥ `phase_score_threshold`, see formula below | Hyperscaler capex trend, supply lead-time/backlog data, EPS revisions, analyst upgrades, price momentum |
| EMA stack | Price above EMA(8) above EMA(21) above EMA(50) above EMA(200) (bullish stack) | Daily OHLCV |
| RSI band | RSI(14) within `rsi_range` | Daily OHLCV |
| Relative volume | RVOL within `rvol_range` (elevated but not blow-off; RVOL 1.5-2.0 is the documented backtested sweet spot at ~58.8% 5-day follow-through per the user's docs) | Daily volume + average volume baseline |

**Point estimates (`Edge_config.yaml`):** `four_factor_threshold: 16`, `phase_score_threshold: 40`, `ema_stack: [8, 21, 50, 200]`, `rsi_range: [50, 65]`, `rvol_range: [1.5, 2.0]`, `max_position: 0.06` (6% of capital per position).

**Tunable grids (`Parameters_ranges.yaml`):** `four_factor_threshold: [14, 16, 18, 20]`, `phase_score_threshold: [35, 40, 45]`, `rsi_min: [45, 50, 55]`, `rsi_max: [60, 65, 70]`, `rvol_min: [1.2, 1.5, 1.8]`, `rvol_max: [1.8, 2.0, 2.5]`.

### Four-Factor Model (resolved — sourced from user's Master AI Trading Strategy v6.0 synthesis, consistent across all 3 uploaded strategy documents)

Score = sum of 4 factors, each scored 0-5, weighted, summed to a 0-25 scale:

| Factor | Weight | Points (of 25) | Scoring basis |
|--------|--------|-----------------|---------------|
| Earnings Revision Momentum | 40% | 10 pts | 5 = >50% of analysts revising EPS up >5% in 30 days; 0 = net negative revisions |
| Relative Strength vs SMH & SPX | 25% | 6.25 pts | 5 = top decile RS over 20/65-day windows; 0 = bottom quartile |
| Scarcity/Moat Durability | 20% | 5 pts | 5 = hard supply constraint confirmed (e.g. HBM sold out, CoWoS monopoly, uranium enrichment, grid interconnection queue); 0 = commoditized |
| Technicals | 15% | 3.75 pts | 5 = full EMA stack (8>21>50>200), RSI 50-65, MACD expanding, RVOL >1.5; 0 = below 200-DMA, RSI <40 or >75 |

**Tier thresholds (from score):** Tier 1 (20-25): full size. Tier 2 (16-19): half size — matches `four_factor_threshold: 16` in `Edge_config.yaml`. Tier 3 (12-15): quarter size, options preferred. <12: no entry.

### Phase Score (resolved — 0-50 composite, sourced from same docs)

5 factors, each scored 0-10, summed to 0-50:

| Factor | Data source |
|--------|-------------|
| Capex Velocity | Hyperscaler earnings transcripts — rate of capex growth directed at this layer |
| Supply Tightness | Lead-time/backlog disclosures — constrained supply scores higher |
| EPS Revision | Direction + magnitude vs prior 4 weeks |
| Analyst Upgrades | Net upgrades minus downgrades, past 30 days |
| Momentum | Price vs SPX, 1-month + 3-month relative strength |

**Thresholds:** 40-50 = STRONG BUY (matches `phase_score_threshold: 40`) → full size. 30-39 = HOLD/ADD → standard size. 20-29 = REDUCE → half size, tighten stops. <20 = EXIT → full exit.

**Current bottleneck-phase ranking** (per the user's docs, dated July 2026 — will decay, needs live refresh, not treated as static truth): Power/Cooling and Memory/HBM cited as "ACTIVE PRIMARY" bottlenecks (scores ~43/50); Networking and Custom Silicon "EMERGING" (~35-38/50); GPU Compute "EASING" as Blackwell ramps (~28/50); Physical AI/Robotics "EARLY" (~15/50).

### Entry Signal Logic
```
if four_factor_score >= four_factor_threshold
   and phase_score >= phase_score_threshold
   and EMA(8) > EMA(21) > EMA(50) > EMA(200)
   and rsi_range[0] <= RSI(14) <= rsi_range[1]
   and rvol_range[0] <= RVOL <= rvol_range[1]:
        enter(size = min(max_position, sizing_rule))
```

---

## Exit Conditions

### Sell Composite (resolved — "88% Sell Composite" per the user's docs, 5 weighted components)

| Component | Weight | Trigger |
|-----------|--------|---------|
| Options flow | 30% | Put/call ratio >1.4 (30-day avg) OR dark pool prints below bid |
| RSI exhaustion | 25% | RSI(14) >80 with bearish divergence, or RSI >80 + declining volume |
| RVOL failure | 20% | RVOL <0.6 on an attempted breakout (false breakout) |
| Hyperscaler capex signal | 15% | Guidance flat/miss + stock >5% off all-time high |
| OpEx calendar timing | 10% | 3rd-Friday options expiry ±2 days + RSI >72 |

**Trigger action:** 3 of 5 components active → scale out 50% (matches `sell_composite_count: 3` in `Edge_config.yaml`, treated as minimum trigger count, not literal component count out of an unweighted 5). 4 of 5 → scale out 75%. 5 of 5 → full exit.

### Time-based Exit
- `days_post_earnings: 60` — exit 60 trading days after the most recent earnings report (PEAD/drift window), or 3-5 days before the next earnings report, whichever is sooner.

### Stop Loss
Not a fixed %/ATR stop in the source docs — trailing stop instead: 20% from highest close in early phase (Phase 5-6 per the bottleneck ranking), tightened to 15% in mid-phase (Phase 3-4). Hard exits also fire on: Phase score <25 for 2 consecutive weeks, hyperscaler capex cut, or an auditor-resignation/governance red flag (the docs cite the 2023 SMCI lesson: exit on governance risk regardless of thesis score).

---

## Universe (resolved — consolidated from the user's Master AI Trading Strategy docs + resources/watchlist attachment)

Not an exhaustive list — full watchlist lives in the uploaded reference docs (`Ai_watchlist.txt`, `resources_and_watchlist__2.pdf`). Core names by bottleneck layer:

| Layer | Representative tickers |
|-------|------------------------|
| Compute/GPU | NVDA, AMD |
| Custom Silicon/Networking | AVGO, MRVL, ARM, QCOM |
| Memory/HBM | MU, WDC, STX, SNDK |
| Power/Cooling/Grid | VRT, VST, CEG, GEV, ETN, PWR, POWL, BE |
| Optical/Networking | ANET, COHR, LITE, CRDO, ALAB, CIEN, MTSI, AAOI, RMBS, FN |
| Semi Equipment/Foundry | TSM, ASML, AMAT, LRCX, KLAC, AMKR, ONTO, ICHR, COHU, TEL |
| Nuclear/SMR | OKLO, LEU, BWXT, CCJ, SMR |
| AI Hosting/BTC→AI pivot | IREN, CORZ, HUT, CIFR, APLD |
| Speculative/Pre-IPO beta | RKLB, ASTS, KTOS, AEHR, AXTI, NBIS |

This universe is explicitly one correlated bet on AI infrastructure capex (per the user's own docs) — treat the whole book as a single theme for correlation/risk purposes, not diversified names.

---

## Data Requirements

| Dataset | Resolution | Source | Status |
|---------|------------|--------|--------|
| Daily OHLCV (universe above) | Daily | FMP — **confirmed reachable**, verified live (NVDA quote pulled successfully) | ✅ Reachable |
| RSI/EMA/technicals | Daily | FMP `technicalIndicators` tool — reachable, same access tier as OHLCV | ✅ Reachable |
| Earnings dates | Per-ticker event | FMP calendar | Likely reachable, not yet tested |
| Earnings estimate revisions | 30/90-day | Zacks/Visible Alpha per source docs (paid, ~$30+/mo) — no equivalent free tool connected in this environment | ❌ Not reachable via connected tools |
| Relative strength vs SMH/SPX | Daily | Computable from OHLCV already reachable (SPX proxy via index; SMH itself hit an FMP plan-tier gate on `quote`/ETF endpoint — see macro_sector_dominance discovery for the same blocker) | ⚠️ Partially blocked (SMH ETF quote gated) |
| Scarcity/moat data (lead times, backlog) | Qualitative/quarterly | Supply-chain trackers (TrendForce, Everstream per source docs), earnings transcripts | ❌ Not reachable via connected tools — qualitative judgment call likely needed initially |
| Options flow / dark pool | Real-time | Unusual Whales (paid, ~$50-150/mo per source docs) | ❌ Not reachable via connected tools |
| Hyperscaler capex guidance | Quarterly | Earnings transcripts/press releases (MSFT, AMZN, GOOGL, META, ORCL) | Manually trackable, not automatable via connected tools |

### Data Scale
Small (<1M rows for a daily-bar equity universe of ~40-60 names). pandas is fine.

---

## Build Plan

**Complexity Level:** Medium. Formulas and universe are now resolved; remaining blockers are data-source access (estimate revisions, options flow, supply-chain data), not missing methodology.

| Step | Description | Output |
|------|-------------|--------|
| 1 | Lock candidate universe (table above) | `Data/universe.csv` |
| 2 | Source daily OHLCV + compute EMA/RSI/RVOL technicals via FMP (confirmed reachable) | `Data/daily_ohlcv.csv`, `src/features/technicals.py` |
| 3 | Four-Factor Model: build what's reachable (RS vs SMH/SPX, technicals sub-score) now; earnings-revision momentum and scarcity/moat sub-scores need a paid data source or manual override | `src/features/four_factor.py` |
| 4 | Phase Score: same partial-build approach — momentum sub-factor reachable now, capex/supply-tightness/analyst-upgrade sub-factors need manual/paid input | `src/features/phase_score.py` |
| 5 | Sell Composite: RVOL and RSI-divergence components buildable now; options-flow component needs a paid data source | `src/features/sell_composite.py` |
| 6 | Combine into composite entry/exit signal, honestly flagging which sub-scores are live-data-driven vs placeholder/manual | `src/signals.py` |
| 7 | Backtest with 6% max position sizing, walk-forward validation (per the user's own Fund-of-Agents doc: no LLM-estimated performance figures, run a real coded backtest) | `src/backtest.py` |

---

## Success Criteria
Realistic targets per the user's own Fund-of-Agents reference doc (explicitly flagging the 78-91% win rates and Sharpe 5-8 in some of their other source material as overfit/not deployable):
- [ ] Sharpe 1.0-1.5 (deployable, cost-realistic)
- [ ] Win rate 55-62%
- [ ] Max drawdown 18-25%
- [ ] Walk-forward out-of-sample Sharpe > 0.8 before considering live deployment

## Kill Criteria
- [ ] Cost-realistic, walk-forward OOS Sharpe < 0.8 (per the user's own doc's stated benchmark to not deploy)
- [ ] Live-vs-backtest expectancy drift > 25% during paper trading
- [ ] Simulated regime-break (2022-style semi drawdown) causes >30% drawdown

---

## Questions for Research Phase

1. Which paid data sources (if any) does the user want to connect for earnings-revision feeds (Zacks/Visible Alpha), options flow (Unusual Whales), and supply-chain data (TrendForce) — or should these sub-scores start as manual/placeholder inputs?
2. Should the Four-Factor and Phase Score sub-factors that aren't yet data-backed be simple-averaged from the reachable sub-factors only (rescaled), or left as a documented gap until paid data is connected?
3. Confirm the consolidated universe table above matches intent, or trim/expand it.

---

*Generated by CBT Framework /cbt:discover --auto, sourced from Edge_config.yaml + Parameters_ranges.yaml + user's uploaded Master AI Trading Strategy synthesis docs (3 versions) + Bottleneck Capital Fund-of-Agents architecture doc + Ai_watchlist.txt + resources_and_watchlist__2.pdf*
