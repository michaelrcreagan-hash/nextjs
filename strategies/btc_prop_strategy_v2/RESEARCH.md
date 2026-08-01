# Strategy Research: btc_prop_strategy_v2

**Date:** 2026-07-23
**Research Scope:** Full

---

## Executive Summary

The strategy rests on five distinct claimed edges. Independent research finds real, peer-reviewed-adjacent support for two of them (trend following, funding-rate mean reversion as a mechanism) but only practitioner-community support (not academic) for two others (MVRV Z-Score, DCB overlay), and finds one component's own accuracy claims (Funding Farmer's 70-90% win rate) likely overstated against real academic arbitrage-capture data. The multi-layer confluence architecture is itself a documented overfitting risk pattern, though DISCOVERY.md's own merge notes already mitigate part of it (collapsing correlated pairs). The most important finding has nothing to do with signal edge: published prop-firm failure rates (90-94%) are overwhelmingly caused by over-risking relative to drawdown limits, not bad strategies — which directly validates this strategy's conservative internal risk buffer as the single highest-leverage design choice already made.

**Overall Confidence:** Medium
**Recommendation:** Proceed with caution — specifically: downgrade Funding Farmer's expected win rate before using it as a build target, and treat DCB-overlay and on-chain thresholds as unvalidated practitioner heuristics pending real backtesting in `/cbt:eda`.

---

## 1. Literature Review

### Papers & Practitioner Research

| Source | Type | Relevance | Key Finding |
|--------|------|-----------|-------------|
| [Catching Crypto Trends (Zarattini, Pagani, Barbon, SSRN/SFI 2025)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907) | Academic (Swiss Finance Institute) | ⭐⭐⭐⭐⭐ | Donchian-ensemble trend following on BTC + top-20 altcoins, 2018-2025, survivorship-bias-free dataset. Sharpe ~1.5-1.6 gross, +10.8% annualized alpha vs BTC buy-hold, net of transaction costs. Strongest single piece of evidence found supporting the Trend Rider sub-strategy's category (though methodology differs: Donchian ensemble vs our EMA/Supertrend/ADX). |
| [A Trend Factor for the Cross Section of Cryptocurrency Returns (Cambridge/JFQA)](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178) | Academic (peer-reviewed) | ⭐⭐⭐⭐ | Trend factor reliably predicts crypto returns, survives transaction costs, not subsumed by known factors. Corroborates trend-following category. |
| [Perpetual Futures Pricing (Ackerer, Hugonnier, Jermann — Mathematical Finance, Wharton)](https://finance.wharton.upenn.edu/~jermann/AHJ-main-10.pdf) | Academic (peer-reviewed) | ⭐⭐⭐⭐ | Formal arbitrage-pricing model for perpetual futures; funding mechanism theoretically ensures price convergence to spot. Supports the *mechanism* behind Funding Farmer, not its claimed win rate. |
| [Funding Rate Mechanism in Perpetual Futures (Zhang, SSRN)](https://papers.ssrn.com/sol3/Delivery.cfm/6185958.pdf?abstractid=6185958&mirid=1) | Academic | ⭐⭐⭐⭐ | Linear funding rule induces an *endogenous* mean-reverting basis in continuous-time equilibrium with risk-constrained arbitrageurs. Theoretical support for funding-rate mean reversion as a real, structural phenomenon. |
| [Exploring Risk and Return Profiles of Funding Rate Arbitrage on CEX and DEX (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2096720925000818) | Academic | ⭐⭐⭐⭐⭐ | **Contradicts source-doc win-rate claim.** Only 17% of observations show economically significant funding spreads (≥20bps); of those top opportunities, only ~40% generate positive returns *after* transaction costs and spread reversals. This is far below the 70-90% win rate DISCOVERY.md's source material claimed for Funding Farmer. |
| [Cryptocurrency as an Investable Asset Class: Coming of Age (arXiv 2510.14435)](https://arxiv.org/html/2510.14435v3) | Academic (working paper) | ⭐⭐⭐⭐ | Per search-result snippet (full paper 403'd both html and pdf routes — could not verify directly, flagging as secondary-source): crypto carry-strategy Sharpe falls to 4.06 starting 2024, turns **negative in 2025**. If accurate, this directly undercuts Funding Farmer's premise going forward — needs primary-source verification before trusting. |
| [Bitcoin MVRV Z-Score — Bitcoin Magazine Pro](https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/), [Newhedge](https://newhedge.io/bitcoin/mvrv-z-score), [MacroMicro](https://en.macromicro.me/charts/30335/bitcoin-mvrv-zscore) | Industry/practitioner (not peer-reviewed) | ⭐⭐⭐ | Strong track record marking cycle tops/bottoms within ~2 weeks historically (on-chain analytics community consensus, not academic literature). Explicitly recommended as a weekly/monthly signal, not a day-trading trigger — matches DISCOVERY.md's confluence-layer (not standalone) usage. No independent academic validation found for the specific >5.5/<0 thresholds used in config.yaml; those are practitioner-community heuristics. |
| [RSI 2 Strategy (QuantifiedStrategies, StockCharts ChartSchool, multiple)](https://www.quantifiedstrategies.com/rsi-2-strategy/) | Practitioner (decades of backtesting cited, not academic) | ⭐⭐⭐ | RSI(2) mean reversion has a long, well-documented backtest history — but **specifically in equities** (>75% win rate cited), not crypto. No crypto-specific RSI(2) validation found. 34% historical max drawdown flagged as a real risk. Connors' original design explicitly omits stops (relies on mean-reversion snapping back); config.yaml's 1x ATR stop is a deliberate deviation, not backed by the original research, and worth testing both ways in `/cbt:eda`. |
| [Dead Cat Bounce in Crypto (FinanceFeeds, BingX, others)](https://financefeeds.com/dead-cat-bounce-in-crypto-what-it-means/) | Practitioner/journalistic | ⭐⭐ | Pattern is real and qualitatively well-documented (2018: 15-25% bounces before further declines; May 2021 crash comparable). **No independently-verified quantitative win-rate statistics found** for DCB-short setups. The specific 68-82% accuracy figures in DISCOVERY.md's source docs remain unverified practitioner estimates — several of those source docs self-flagged this same caveat. |

### Key Insights
1. Trend following on BTC has the strongest independent academic backing of any component in this strategy (SFI 2025 paper, JFQA paper) — reasonable to trust Trend Rider's category, though the specific EMA/Supertrend/ADX implementation itself is unvalidated (the academic papers use Donchian ensembles).
2. Funding-rate mean reversion is real as a *mechanism* (peer-reviewed theory) but the *magnitude* of exploitable edge is much smaller in practice than DISCOVERY.md's source docs claimed (40% success after costs on top-quintile opportunities, not 70-90% blanket win rate).
3. MVRV Z-Score, RHODL, and DCB-specific signal accuracy figures all trace back to on-chain-analytics-community and single-source-document claims, not peer-reviewed research — treat as hypotheses to test, not established facts, consistent with what several of the original source docs themselves already flagged.

### Recommended Reading
- [Catching Crypto Trends](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907) — most directly actionable methodology reference for improving Trend Rider.
- [Exploring Risk and Return Profiles of Funding Rate Arbitrage](https://www.sciencedirect.com/science/article/pii/S2096720925000818) — required reading before trusting Funding Farmer's win-rate target.

---

## 2. Existing Implementations

No GitHub repository search was run this pass (scope prioritized literature + risk validation given the strategy's own source docs already included a working `main.py`/`config.py`/`README.md` scaffold — see `IDEA.md`). Recommend a targeted implementations search in a follow-up `/cbt:research implementations` pass once the on-chain/Coinglass data-sourcing question (open in DISCOVERY.md) is resolved, since that will determine what's actually buildable.

---

## 3. Edge Validation

### Is This Edge Real?

| Factor | Assessment | Notes |
|--------|------------|-------|
| Trend Rider (academic support) | Partial-to-Yes | Real peer-reviewed support for the *category*; specific indicator choice (EMA/Supertrend/ADX vs Donchian ensemble) untested independently. |
| Funding Farmer (academic support) | Partial | Mechanism is real; claimed win rate (70-90%) contradicted by academic arbitrage-capture data (~40% after costs on top opportunities). Recommend downgrading target win rate before build. |
| Range Hunter / RSI(2) (academic support) | Partial | Real equities track record; no crypto-specific validation found. |
| DCB overlay / on-chain thresholds | No (practitioner-only) | No peer-reviewed backing found; single-source-document accuracy claims, several self-flagged as estimates. |
| Coinglass microstructure filters | No independent check this pass | Not separately researched — same caveat as DCB overlay: single-source-document claims. |
| Theoretical basis (overall) | Strong for trend + funding mechanism, weak for on-chain/DCB thresholds | Mixed by component, not uniform across the strategy. |
| Competition level | High and rising | General crypto-quant alpha decay is well-documented and accelerating (AI-driven signal convergence); funding-rate carry specifically may already be decaying per the 2024-2025 Sharpe data found (needs primary-source confirmation). |
| Still profitable | Uncertain, component-dependent | Likely for trend following; increasingly uncertain for funding-rate carry; unverified for DCB/on-chain. |

### Regime Analysis

| Market Regime | Expected Performance |
|---------------|---------------------|
| Bull market (trending) | Trend Rider favored; academic trend-following support is strongest here. |
| Bear market (trending down) | Trend Rider + DCB overlay both active; DCB overlay's specific accuracy is the least-validated component of the whole strategy in this regime. |
| Range-bound / low ADX | Range Hunter favored; RSI(2) mean reversion has real (equities) precedent, unverified for crypto. |
| High volatility | Funding Farmer's funding-rate extremes more likely to fire, but so does the confluence scorer's macro/DCB signal jump-and-force-exit rule — expect more forced exits, not necessarily more edge. |
| Low volatility (squeeze) | Weakest regime for all three sub-strategies simultaneously; no component specifically targets this. |

### Edge Durability
Mixed. Trend following on BTC has multi-year (2018-2025) out-of-sample academic support and is the most durable component. Funding-rate carry shows documented signs of decay starting 2024 in the crypto-specific literature found — this is a real risk to the Funding Farmer allocation (20% of the book) that DISCOVERY.md did not previously flag. On-chain/DCB signal accuracy remains unvalidated against independent data and should not be trusted as a build target until `/cbt:eda` runs real historical backtests against sourced data.

---

## 4. Feature Ideas

| Feature | Source | Priority | Complexity |
|---------|--------|----------|------------|
| Donchian-channel ensemble trend signal (multiple lookback periods aggregated) | Zarattini/Pagani/Barbon SFI 2025 paper | Medium | Medium — could run alongside or replace EMA/Supertrend for Trend Rider, A/B test in `/cbt:eda` |
| Volatility-based position sizing (vs the paper's approach) | Same paper | Medium | Medium — current config uses fixed 0.5%/trade; volatility-scaling could improve risk-adjusted return within the same prop-firm risk cap |
| Cross-sectional trend factor (rotational altcoin basket) | Cambridge/JFQA trend factor paper | Low | High — out of scope for a BTC-only strategy, noted for a possible future multi-asset variant |
| Funding-rate spread threshold filter (≥20bps economically significant) | ScienceDirect funding arbitrage paper | High | Low — directly actionable refinement to Funding Farmer's entry filter, tightens the current 0.01%/8h threshold toward the paper's empirically-significant level |

### Implementation Notes
The funding-spread threshold feature is the highest-priority, lowest-complexity change: it directly addresses the win-rate contradiction found in section 3 and can be added to `strategy_params.funding_farmer` in config.yaml without touching architecture.

---

## 5. Risks & Pitfalls

### Critical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Funding Farmer win rate overstated (70-90% claimed vs ~40% academic) | High | Medium (20% allocation) | Downgrade target win rate in `expected_performance`; re-derive position sizing from realistic figure before `/cbt:build` |
| DCB-overlay and on-chain threshold accuracy unverified | High | Medium-High (10-25% weight depending on regime) | Treat as hypotheses; validate against real historical data in `/cbt:eda` before trusting in live sizing |
| Multi-layer confluence scorer is a documented overfitting pattern | Medium | High if unmitigated | Partially already mitigated (DISCOVERY.md merge notes collapse MVRV+NUPL, Puell+HashRibbons); technical layer (ADX-gated SuperTrend + 4H EMA + Ichimoku) still has correlated trend signals not yet collapsed — revisit in `/cbt:config` |
| Crypto carry/funding strategies show 2024-2025 Sharpe decay in the wild (per search snippet, unverified primary source) | Medium (needs confirmation) | Medium | Get primary-source confirmation of arXiv 2510.14435's carry-Sharpe claim before treating as fact; if confirmed, consider cutting Funding Farmer allocation below 20% |
| Prop-firm over-risking (industry-wide 90-94% failure rate) | High if internal risk rules are ever bypassed | Catastrophic (account termination) | Already well-mitigated by config.yaml's internal 0.5%/trade, 3%/6% daily/total DD buffer — this is the strategy's strongest existing risk control, confirmed correct by research, don't relax it |
| RSI(2)'s no-stop-loss original design vs config.yaml's 1x ATR stop deviation | Low-Medium | Low-Medium | Deliberate deviation from source research; A/B test both in `/cbt:eda` rather than assuming the stop helps |

### Historical Failures
- Crypto carry/funding-rate strategies are cited in the literature search as having Sharpe ratios collapsing from historically stable positive levels to negative by 2025 (per arXiv 2510.14435 abstract snippet) — directly analogous to Funding Farmer's premise and the closest thing to a "similar strategy that failed" found in this pass. Needs primary-source verification (both direct fetch attempts 403'd).
- General alpha decay research: ~50% of published academic anomalies lose predictive power after publication as investors arbitrage them away — relevant given several of this strategy's signals (MVRV Z, funding extremes, on-chain thresholds) are now widely publicized on retail-facing dashboards (Bitcoin Magazine Pro, Newhedge, CoinGlass), which is itself evidence of crowding risk.

### Red Flags to Watch
- [ ] Funding Farmer live win rate tracking meaningfully below the 70-90% source-doc claim (expect closer to 40-60% per academic data — recalibrate expectations now, not after live underperformance)
- [ ] DCB-short setups firing frequently but not resolving as predicted (would indicate the unvalidated accuracy figures are wrong)
- [ ] Technical-layer signals (SuperTrend/EMA/Ichimoku) moving in lockstep rather than independently (would confirm the correlated-signal overfitting risk)
- [ ] Realized Sharpe on Funding Farmer specifically trending toward zero or negative over rolling windows (would corroborate the carry-decay finding)

---

## 6. Research Conclusions

### Strengths
- Trend Rider sub-strategy category has genuine, recent (2025), peer-reviewed-adjacent academic support specific to BTC.
- The strategy's internal prop-firm risk buffer (0.5%/trade, 3%/6% DD) is independently validated as the correct approach by industry-wide prop-firm failure-rate data — this is not a hypothesis, it's confirmed best practice.
- DISCOVERY.md's own merge notes already show awareness of and partial mitigation for signal-redundancy/overfitting risk (collapsing MVRV+NUPL, Puell+Hash Ribbons) before this research pass even started.

### Weaknesses
- Funding Farmer's headline win-rate claim (70-90%) is not supported by academic arbitrage-capture data (~40% after costs) — the sub-strategy likely still has positive expectancy but at a meaningfully lower rate than the source docs assumed.
- DCB-overlay and on-chain-threshold accuracy figures (82%, 80%, 78%, etc.) trace to unverified single-source-document claims with no independent corroboration found.
- Possible (unconfirmed) evidence that crypto carry-strategy Sharpe is deteriorating industry-wide in 2024-2025, which would specifically threaten the Funding Farmer allocation going forward, not just its backtest-era win rate.
- Technical-layer confluence still contains partially-correlated signals (SuperTrend/EMA/Ichimoku all measure trend-alignment) that inflate apparent confluence without adding independent information.

### Recommendations
1. Downgrade Funding Farmer's `expected_performance` win-rate assumption before `/cbt:build` — use the academic ~40-60% range as the working target, not the source doc's 70-90%, and re-derive position sizing accordingly (it's already capped at prop-firm limits so this mainly affects allocation confidence, not risk breach).
2. Add a funding-spread economic-significance filter (≥20bps, from the ScienceDirect paper) to `funding_farmer` config as a higher-priority, lower-complexity refinement than anything else in the build plan.
3. Before trusting DCB-overlay or on-chain thresholds in live sizing, validate them against real historical data in `/cbt:eda` — treat current config.yaml values as starting hypotheses, exactly as DISCOVERY.md's own "Questions for Research Phase" already anticipated.
4. Attempt primary-source verification of the 2024-2025 crypto-carry-Sharpe-decay claim (arXiv 2510.14435) in a follow-up pass — both direct fetch attempts were blocked (403) this session.
5. Revisit the technical-layer weighting in `confluence_scorer` to reduce double-counting of correlated trend signals (SuperTrend + 4H EMA + Ichimoku), following the same collapsing logic DISCOVERY.md already applied to the on-chain layer.

### Updated Kill Criteria
Based on research, also abandon (or materially re-scope) if:
- [ ] Funding Farmer's realized win rate over any 30-trade rolling window falls into the 30-40% range predicted by academic arbitrage-capture data with negative expectancy after prop-firm-level costs/slippage
- [ ] Primary-source confirmation shows crypto carry-strategy Sharpe genuinely negative through 2025 (would indicate the whole sub-strategy's premise, not just its win-rate estimate, has decayed)
- [ ] `/cbt:eda` backtesting shows DCB-overlay or on-chain-threshold signals performing at or below random (would confirm those figures were unfounded practitioner estimates)

---

## Sources

### Papers
1. [Catching Crypto Trends; A Tactical Approach for Bitcoin and Altcoins (Zarattini, Pagani, Barbon, SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907)
2. [A Trend Factor for the Cross Section of Cryptocurrency Returns (Cambridge/JFQA)](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178)
3. [Perpetual Futures Pricing (Ackerer, Hugonnier, Jermann)](https://finance.wharton.upenn.edu/~jermann/AHJ-main-10.pdf)
4. [Funding Rate Mechanism in Perpetual Futures (Zhang, SSRN)](https://papers.ssrn.com/sol3/Delivery.cfm/6185958.pdf?abstractid=6185958&mirid=1)
5. [Exploring Risk and Return Profiles of Funding Rate Arbitrage on CEX and DEX (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2096720925000818)
6. [Cryptocurrency as an Investable Asset Class: Coming of Age (arXiv 2510.14435)](https://arxiv.org/html/2510.14435v3) — snippet only, primary source unverified (403)

### Articles / Industry Sources
1. [Bitcoin MVRV Z-Score — Bitcoin Magazine Pro](https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/)
2. [Bitcoin MVRV Z-Score — Newhedge](https://newhedge.io/bitcoin/mvrv-z-score)
3. [Bitcoin - MVRV Z-Score — MacroMicro](https://en.macromicro.me/charts/30335/bitcoin-mvrv-zscore)
4. [RSI 2 Strategy: Complete Guide — QuantifiedStrategies.com](https://www.quantifiedstrategies.com/rsi-2-strategy/)
5. [RSI(2) — StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2)
6. [Dead Cat Bounce in Crypto: What It Means for Traders — FinanceFeeds](https://financefeeds.com/dead-cat-bounce-in-crypto-what-it-means/)
7. [Multi-Indicator Confluence Trading System — FMZQuant/Medium](https://medium.com/@FMZQuant/multi-indicator-confluence-trading-system-886f15b18ae5)
8. [Stop Overfitting: How Indicator Diversity Improves Strategy Robustness — Medium](https://medium.com/@mariamhov/stop-overfitting-how-indicator-diversity-improves-strategy-robustness-46b021414a76)
9. [3 Simple Ways To Reduce The Risk Of Curve-fitting — Build Alpha](https://www.buildalpha.com/3-simple-ways-to-reduce-the-risk-of-curve-fitting/)
10. [What Percentage of Traders Pass Prop Firm Challenges? — Apex Trader Funding](https://apextraderfunding.com/resources/prop-trading/what-percentage-of-traders-pass-prop-firm-challenges/)
11. [Prop Firm Challenges Failure Rate: Why 94% of Traders Fail — PickMyTrade](https://blog.pickmytrade.trade/prop-firm-challenges-failure-rate/)
12. [Only 1 in 20 Traders Pass Prop Firm Challenges — Finance Magnates](https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader/)
13. [Alpha Decay in Trading: Why Strategies Stop Working Over Time](https://www.tradingengineeringlab.com/alpha-decay-in-trading-why-strategies-stop-working-over-time/)
14. [Not All Factors Crowd Equally: Modeling, Measuring, and Trading on Alpha Decay (arXiv)](https://arxiv.org/pdf/2512.11913)

---

*Generated by CBT Framework /cbt:research*
