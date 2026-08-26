# Strategy Research: hermes_agent

**Date:** 2026-08-26
**Research Scope:** Full (literature + implementations + edge validation + risks)
**Prior phases:** `DISCOVERY.md` (no pre-asserted edge — three candidate mechanisms), `EDA.md` (feature-quality findings that this research must be read against)

---

## Executive Summary

The literature splits hermes_agent's three candidate edge mechanisms sharply, and not in the direction the live system's design implies. **Regime-conditional exposure scaling (mechanism #2) is the best-supported** — Moreira & Muir's volatility-managed portfolios are a top-journal result, though a large follow-up study finds the Sharpe gains do not generalize across 103 strategies. **Cross-domain breadth/confluence (mechanism #1) has strong general support in the forecast-combination literature but is specifically undercut by this strategy's own EDA**: combination gains require heterogeneous information sets, and hermes_agent's 42 features collapse to ~10–15 independent signals (80 pairs correlate >0.9, several exactly 1.0). **Flow-speed (mechanism #3) is real but small and fast** — spot-ETF flows Granger-cause BTC returns (p=0.004) but explain <10% of price variation, and practitioner consensus is that CVD is "coincident at worst, slightly leading at best."

The single strongest finding is one the strategy already got right by accident: **the regime-scaled trailing stop chosen in discovery is the best-evidenced design decision in the whole project**, with crypto-specific support (Sharpe 1.12→1.42 across 147 cryptocurrencies, robust to transaction costs).

The most serious finding is adverse and cross-cutting: a 2026 audit of 77 LLM-trading-agent studies found only 2 of 19 qualifying papers used time-consistent train/test splits, 1 modeled transaction costs, 1 handled survivorship, and **none reached the top reproducibility tier** — with apparent agent alpha "largely dissolving once look-ahead bias is controlled, leaving mostly passive factor exposure." That describes hermes_agent's entire architectural class, including the TradingAgents framework this repo is built on.

**Overall Confidence:** **Low-to-Medium** — Medium for the regime-scaling + trailing-stop core; Low for the multi-agent confluence layer as currently constructed.
**Recommendation:** **Proceed with caution, and materially narrower than DISCOVERY.md's build plan.** Build the regime-scaled trend/exit core first as a standalone, honestly-costed baseline. Treat the multi-domain confluence layer and the BTC ML ensemble as ablation candidates that must *beat* that baseline to earn inclusion — not as the foundation.

---

## 1. Literature Review

### Academic Papers

| Title | Authors | Year | Relevance | Key Finding |
|---|---|---|---|---|
| [Volatility-Managed Portfolios](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513) (J. Finance) | Moreira, Muir | 2017 | ⭐⭐⭐⭐⭐ | Scaling exposure down when volatility is high produces large positive alphas and raises factor Sharpe ratios across market, value, momentum, profitability, investment factors and currency carry. Vol changes are *not* offset by proportional expected-return changes. |
| [On the performance of volatility-managed portfolios](https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X) (JFE) | Cederburg, O'Doherty, Wang, Yan | 2020 | ⭐⭐⭐⭐⭐ | **The rebuttal.** Across 103 equity strategies, *no* statistical or economic evidence that vol-managed portfolios systematically earn higher Sharpe ratios. Positive spanning-regression alphas do survive. Real-time implementability is the crux. |
| [Stop-loss rules and momentum payoffs in cryptocurrencies](https://www.sciencedirect.com/science/article/abs/pii/S2214635023000473) (J. Behav. Exp. Finance) | — | 2023 | ⭐⭐⭐⭐⭐ | 147 cryptos, Jan-2015→Jun-2022. Stop-loss momentum lifts avg weekly return 3.18%→3.47% and annualized Sharpe **1.12→1.42**. Robust to transaction costs, short-sale constraints, horizons. In crypto the gain comes from *augmented returns*, not just downside mitigation (unlike equities) — no extended momentum crashes. |
| [Risk reduction using trailing stop-loss rules](https://onlinelibrary.wiley.com/doi/abs/10.1111/irfi.12328) (Int. Rev. Finance) | Dai et al. | 2021 | ⭐⭐⭐⭐ | Trailing stops have *inferior mean returns* vs mean-variance optimal benchmarks but are effective at reducing total and downside risk, especially in declining markets. Larger thresholds remain useful net of costs. |
| [Agentic Trading: When LLM Agents Meet Financial Markets](https://arxiv.org/abs/2605.19337) | — | 2026 | ⭐⭐⭐⭐⭐ | Protocol-coded audit of **77 studies, 19 meeting minimum empirical standards**: only **2/19** report time-consistent split protocols, **1** addresses transaction costs, **1** handles survivorship. **Zero** reach R3 reproducibility. Apparent agent alpha largely dissolves once look-ahead bias is controlled, leaving mostly passive factor exposure. |
| [Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems](https://arxiv.org/pdf/2603.27539) | — | 2026 | ⭐⭐⭐⭐⭐ | "Coordination primacy": *how* agents interact matters more than how many. Central critique — many papers lack single-agent/simple baselines, so MAS superiority claims are unvalidated; **"the added complexity of coordination may not justify performance gains."** Also flags near-universal neglect of API/compute cost in evaluation. |
| [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138) | Xiao et al. | 2024 | ⭐⭐⭐⭐⭐ | The upstream framework for this repo's `trading/` directory. Claims improvements in cumulative return, Sharpe, and max drawdown vs baselines. Read alongside the two audits above — it is one of the studies the reproducibility critique targets. |
| [The Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) | Bailey, López de Prado | 2014 | ⭐⭐⭐⭐⭐ | Corrects Sharpe for selection bias under multiple testing, sample length, and non-normality. When you try many variants and keep the best, max SR is inflated **even if every candidate is pure noise**. Directly applicable to DISCOVERY.md's planned threshold grid. |
| [Crypto Carry](https://www.bis.org/publ/work1087.pdf) (BIS WP 1087 / Management Science) | Schmeling, Schrimpf, Todorov | 2023, rev. 2025 | ⭐⭐⭐⭐ | Crypto carry averages **>10% annually**, far above equities/FI/FX/commodities. Driven by convenience yields, not rate differentials. **Carry has predictive power for future crypto crashes** — relevant as a regime input, not just a trade. |
| [Time-Series and Cross-Sectional Momentum in Crypto under Realistic Assumptions](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565) | Han, Kang, Ryu | — | ⭐⭐⭐⭐ | Time-series momentum evidence is **strong**; cross-sectional is **weak**. But under realistic costs many momentum portfolios get liquidated and statistically significant returns become economically insignificant. |
| [Spot Bitcoin ETFs: Effect of Fund Flows on Price Formation](https://papers.ssrn.com/sol3/Delivery.cfm/5452994.pdf?abstractid=5452994) | Mazur, Polyzos | 2025 | ⭐⭐⭐ | Flows explain ~21% of daily return variation and predict next-day returns. Bidirectional Granger causality (flows→returns *and* returns→flows). |
| [Predictability of Funding Rates](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424) | Inan | — | ⭐⭐⭐ | DAR models beat no-change for predicting *next-period funding rate levels* on Binance/Bybit BTC. Note: predicting funding ≠ predicting price. |
| [Barber & Odean — Trading Is Hazardous to Your Wealth](https://faculty.haas.berkeley.edu/odean/papers/returns/individual_investor_performance_final.pdf) | Barber, Odean | 2000 | ⭐⭐⭐⭐⭐ | 66,465 households. Most-active traders earned **11.4%** vs market **17.9%** — a **6.5pp annual drag**, with gross returns nearly identical across groups. All destruction happened after costs. |

### Key Insights

1. **Volatility timing is the one mechanism with a top-journal result *and* a serious top-journal rebuttal.** Moreira-Muir is real; Cederburg et al. show it doesn't generalize across 103 strategies. The honest position: expect drawdown reduction (well-evidenced) rather than Sharpe improvement (contested). That is exactly what this repo's own four-sleeve work already found — its regime matrix *added* return but also *added* drawdown vs a static allocation, and the cycle overlay was a pure risk reducer. **Internal and external evidence agree.**

2. **Forecast combination works when signals are diverse — hermes_agent's aren't.** The combination literature ([Lee, Combining Forecasts with Many Predictors](https://faculty.ucr.edu/~taelee/paper/chapter7.pdf); [Ensemble Multi-Expert Forecasting, MDPI 2025](https://www.mdpi.com/1911-8074/18/6/296)) attributes gains to *heterogeneous information sets*. [Chicago Booth](https://www.chicagobooth.edu/review/turning-weak-signals-into-strong-predictions) notes LASSO-style selection struggles when the data is mostly faint signals — which is precisely EDA.md's finding (max |r| with target = 0.13). Mechanism #1's theoretical support does not transfer to this feature set as built.

3. **Flow data is genuinely informative but on a horizon hermes_agent doesn't trade.** ETF flows peak in impulse-response at days 3–4 (~1.2%); CVD is described by practitioners as reactive. A daily-cadence, cron-scheduled system with LLM synthesis latency is poorly positioned to monetize a 3-day flow impulse that <10% of price variation depends on.

4. **The multi-agent architecture is the least-validated part, not the most.** Two independent 2026 audits converge: no reproducibility, missing cost accounting, missing baselines, and alpha that evaporates under look-ahead control. The burden of proof is on the architecture.

5. **A 2026-specific regime warning on funding:** funding has spent long stretches **negative** across majors in 2026, reversing the structurally-positive 2024 regime. Any funding-carry or funding-as-bullish-signal logic calibrated on 2024 data is calibrated on a regime that has since inverted.

### Recommended Reading
- [Agentic Trading: When LLM Agents Meet Financial Markets](https://arxiv.org/abs/2605.19337) — read first; it is the strongest challenge to this project's premise.
- [On the performance of volatility-managed portfolios](https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X) — the rebuttal that keeps mechanism #2 honest.
- [Stop-loss rules and momentum payoffs in cryptocurrencies](https://www.sciencedirect.com/science/article/abs/pii/S2214635023000473) — direct empirical support for the chosen exit design.
- [The Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) — mandatory before reporting any grid-search result.

---

## 2. Existing Implementations

| Repository | Notes | Relevance |
|---|---|---|
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | Numba-accelerated vectorized backtester; packs thousands of parameter configs into NumPy arrays and runs them at once | ⭐⭐⭐⭐⭐ — directly matches this strategy's `engine: fast` (Polars/NumPy/Numba) choice and DISCOVERY.md's threshold grid-search step |
| [dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | Portfolio optimization with CDaR/CVaR constraints; ships a [multi-asset backtesting tutorial with vectorbt](https://github.com/dcajasn/Riskfolio-Lib/blob/master/examples/Tutorial%2018%20-%20Multi%20Assets%20Algorithmic%20Trading%20Backtesting%20with%20Vectorbt.ipynb) | ⭐⭐⭐⭐ — drawdown-constrained allocation is a better fit for hermes_agent's stated goals than mean-variance |
| [ArturSepp/OptimalPortfolios](https://github.com/ArturSepp/OptimalPortfolios) | Optimization analytics for constructing/backtesting optimal portfolios | ⭐⭐⭐ |
| [asavinov/intelligent-trading-bot](https://github.com/asavinov/intelligent-trading-bot) | Signal generation via ML + feature engineering; multi-signal scoring where many computed scores feed one output score | ⭐⭐⭐⭐ — closest public analogue to hermes_agent's F/T/S/M composite pattern |
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | Upstream of this repo's `trading/` directory | ⭐⭐⭐⭐⭐ — but see cost/reproducibility issues below |

### Patterns Worth Borrowing
- **Vectorized parameter sweeps over loop-based backtests.** DISCOVERY.md step 6 (grid-search confluence threshold + RR filter) is exactly vectorbt's use case, and justifies the `fast` engine selection that EDA.md flagged as otherwise unnecessary at this data scale.
- **Volatility-cluster regime labeling** ([PyQuantLab worked example](https://pyquantlab.medium.com/volatility-clustering-strategy-with-python-and-vectorbt-8c5b840e88a8)): measure vol from log returns, smooth, label clusters against a *dynamic* threshold, trade only at regime boundaries. Cleaner than a fixed VIX cutoff and closer to what EDA.md's vol-clustering finding supports.
- **Drawdown-constrained (CDaR) allocation** instead of return-maximizing weights, given that the evidenced benefit of regime scaling is drawdown reduction, not Sharpe.

### Differences from Our Approach
- None of these carry an LLM synthesis layer — they are mechanical. That is the *point*: they are the baselines hermes_agent's agent layer must beat to justify its cost and complexity.
- Upstream TradingAgents documents real operational problems: [issue #750](https://github.com/TauricResearch/TradingAgents/issues/750) reports **16–22 LLM calls per pipeline run at ~0% prompt-cache hit rate** (~30–40% avoidable API cost overhead), plus historical reports of fabricated price levels and inconsistent company resolution across runs. A reported run showed ~7% over 30 days vs S&P 4.5% — with **22% drawdown** and no repeatability guarantee.

---

## 3. Edge Validation

### Is This Edge Real?

**Mechanism #1 — Cross-domain breadth/confluence filtering**

| Factor | Assessment | Notes |
|---|---|---|
| Academic support | **Partial** | Forecast-combination theory supports it *in general*; requires diverse information sets |
| Still profitable | **Uncertain** | Untestable as built — the diversity precondition fails |
| Theoretical basis | **Weak here** | EDA: 80 feature pairs >0.9 corr, several exactly 1.0; ~10–15 real signals wearing 42 names |
| Competition level | **High** | Every desk combines macro/technical/sentiment |

**Mechanism #2 — Regime-conditional exposure scaling**

| Factor | Assessment | Notes |
|---|---|---|
| Academic support | **Yes, contested** | Moreira-Muir (JF 2017) vs Cederburg et al. (JFE 2020) |
| Still profitable | **Likely for drawdown control; uncertain for Sharpe** | Spanning alphas survive the rebuttal; Sharpe gains don't generalize |
| Theoretical basis | **Strong** | Vol is persistent and forecastable; expected returns don't scale proportionally. EDA confirms clustering (13.8% of days >1.5× median 30d vol) |
| Competition level | **High but capacity-insensitive** | Vol targeting is crowded yet doesn't decay from crowding the way an arbitrage does |

**Mechanism #3 — Flow-speed (funding / OI / CVD / ETF flows)**

| Factor | Assessment | Notes |
|---|---|---|
| Academic support | **Yes, but modest effect sizes** | Granger p=0.00406; corr 0.30; **<10% of price change explained**; IRF peak ~1.2% at days 3–4 |
| Still profitable | **Unlikely at this cadence** | Effect is short-horizon; hermes_agent runs daily cron with LLM latency |
| Theoretical basis | **Moderate** | Real order-flow information; but CVD is "coincident at worst, slightly leading at best" |
| Competition level | **Very High** | Funding arb compressed; only ~40% of top opportunities profitable after costs |

> **⚠️ Statistical red flag to avoid:** one widely-circulated claim is that ETF net flows predict BTC price with **R² = 95%**. That regresses *price levels* on *cumulative flows* — two non-stationary, trending series. EDA.md already established BTC price is non-stationary (ADF p=0.478) while returns are stationary (p<0.0001). This is a textbook spurious regression. The defensible number is FalconX's **correlation 0.30 / <10% of variation explained**. Do not let the 95% figure into any hermes_agent justification.

### Regime Analysis

| Market Regime | Expected Performance |
|---|---|
| Bull / trending | **Good** — TSMOM strong in crypto; trailing stops add return not just protection |
| Bear market | **Moderate** — regime scaling's evidenced strength; but repo's own four-sleeve work shows the matrix de-risks *after* damage starts |
| High volatility | **Good relative / poor absolute** — vol targeting cuts exposure; expect underperformance vs B&H in V-recoveries (repo's own 2020-04 and 2023-01 finding) |
| Low volatility | **Poor** — scaling up into calm markets is where Cederburg et al.'s critique bites; also where confluence thresholds fire most often on noise |
| Mean-reverting / chop | **Poor** — trailing stops whipsaw; this is the dominant failure mode |
| Negative-funding regime (2026 actual) | **Poor for any funding-carry logic** — funding has been negative for long stretches in 2026 |

### Edge Durability

Ranked, most to least durable:
1. **Regime/vol scaling** — durable because it exploits a *statistical property* (vol persistence), not a mispricing; can't be arbitraged away in the usual sense. Contested on magnitude, not existence.
2. **Trailing-stop risk management** — durable; it is risk control, not alpha extraction. Crypto evidence is recent (through 2022) and robust to costs.
3. **Cross-domain confluence** — durability unknown because the mechanism is unvalidated here. Would need genuine signal diversification first.
4. **Flow-speed** — **actively decaying**. Funding-carry returns compressed as funding cooled from late-2024 highs; only ~40% of top arb opportunities profitable after costs.

---

## 4. Feature Ideas

| Feature | Source | Priority | Complexity |
|---|---|---|---|
| **Crypto carry / futures basis as a crash-risk regime input** | [BIS WP 1087](https://www.bis.org/publ/work1087.pdf) — carry predicts future crypto crashes | **High** | Medium — needs perp+spot basis series, partially available via existing OKX/Hyperliquid feeds |
| **Dynamic (percentile) vol-cluster threshold rather than fixed cutoff** | [PyQuantLab/vectorbt](https://pyquantlab.medium.com/volatility-clustering-strategy-with-python-and-vectorbt-8c5b840e88a8) | **High** | Easy |
| **Spot-CVD vs perp-CVD divergence** (rally on perp CVD but weak spot CVD = fragile, leverage-driven) | [MarketTrace](https://markettrace.ai/blog/cumulative-volume-delta) | **Medium** | Medium — needs both venues; bus already pulls Coinbase + OKX/Hyperliquid |
| **PCA / composite collapse of the 4 duplicate ETF signal groups** | EDA.md finding + forecast-combination diversity requirement | **High** | Easy — pure preprocessing, removes false breadth |
| **Deflated Sharpe Ratio as the reported metric** | [Bailey & López de Prado](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) | **High** | Easy — closed form, needs only trial count + return moments |
| **CDaR-constrained sizing instead of fixed % per trade** | [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | Medium | Medium |

**Implementation note:** the first, fourth, and fifth items are cheap and directly address findings already in hand. They should precede any new modeling work.

---

## 5. Risks & Pitfalls

### Critical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **LLM look-ahead leakage via training cutoff** — the model has already seen how these assets moved | **High** | **High** | Restrict any LLM-in-the-loop backtest to post-cutoff data, or exclude the LLM layer from backtested claims entirely and validate it only forward in paper. This is not fixable by careful data plumbing — the leakage lives in the weights. |
| **Multiple-testing inflation from the planned threshold grid** | **High** | High | Pre-register the grid (repo already does this in `four_sleeve_portfolio/RESEARCH.md`); report **Deflated** Sharpe with the true trial count; hold out a window untouched until the end |
| **False breadth** — treating 42 collinear features as 42 independent votes | **High** (confirmed by EDA) | High | Deduplicate to independent signals before any confluence scoring; the composite is otherwise quadruple-counting BTC-ETF flow |
| **Transaction-cost drag on a small, many-position book** | **High** | **High** | See capacity note below — this is the most concrete, most user-specific risk in this document |
| **Regime scaling adds drawdown rather than removing it** | Medium | Medium | Repo's own four-sleeve ablation found exactly this (+1.5 CAGR, −7.1pp *worse* DD vs static MIXED). Ablate against a static allocation, not only against buy-and-hold |
| **Whipsaw in chop** — trailing stops' known failure mode | **High** | Medium | Dai et al.: larger thresholds outperform; literature clusters at 15–20%, matching `ai_bottleneck_stocks`' 20%/15% by phase. Do not tighten below ~15% without evidence |
| **Funding-regime inversion** — 2026 funding frequently negative | **Confirmed** | Medium | Do not calibrate funding logic on 2024; make sign-of-funding a regime state, not a constant assumption |
| **Operational cost of the agent layer** | High | Medium | Upstream reports 16–22 LLM calls/run at ~0% cache hit. Track $/run as a first-class metric — the MAS-evaluation paper names cost-blindness as a field-wide failure |
| **Short ML history** | Confirmed | Medium | Feature set starts 2025-05-08 (325 rows) vs price panel 2024-07-23 (524). Any IS/OOS split is very short; regenerate features to full history before splitting |

### ⚠️ Capacity & Cost — the most concrete risk for this specific account

Barber & Odean's most-active-trader cohort underperformed the market by **6.5pp/yr**, with *gross* returns nearly identical across activity levels — the entire gap was costs and timing. The relevant arithmetic for these accounts:

- **Merrill IRA: ~$9,860 across 69 positions ≈ $143 average position.** At a $1 commission-equivalent round trip, that is a ~1.4% hurdle per round trip before any edge. Rebalancing that book monthly is close to the pathological case the literature describes.
- **Coinbase: ~$19,846 across 20 tokens**, with a long tail (IP $4.53, MOVE $3.11, EIGEN $10.28) where per-trade spread and fees plausibly exceed any realistic edge.

**This is a strategy-design constraint, not a footnote.** hermes_agent should carry an explicit minimum-position-size floor and a maximum-positions cap derived from account equity, and its backtest must charge realistic per-trade costs on the *actual* position sizes rather than percentage-of-portfolio abstractions. A strategy that looks profitable at $143/position and 10bps assumed cost may be structurally unprofitable at these balances.

### Historical Failures
- **Vol-managed portfolios in broad samples** — Cederburg et al.'s 103-strategy test is the cautionary case: an effect that was real and publishable in the original sample failed to generalize.
- **Crypto funding-rate carry** — profitable and widely-known in 2024, compressed by 2026 as funding turned negative for extended periods; a documented live example of an edge decaying inside two years.
- **Crypto momentum under realistic assumptions** — Han/Kang/Ryu find many statistically significant momentum returns become economically insignificant after costs and liquidation constraints.
- **The BTC ML ensemble already in this system** — 0.48 directional accuracy / 0.46 AUC per its own report. An in-house failure, already documented, already deprecated by the live bus in favor of transparent rules.

### Red Flags to Watch
- [ ] Any reported Sharpe that hasn't been deflated for the number of configurations tried
- [ ] Confluence score improving as more features are added (likely counting the same signal repeatedly)
- [ ] Backtest performance concentrated in the 2025-05→2026-08 feature window (a single regime)
- [ ] Any result citing the "R²=95% ETF flows" figure or another levels-on-levels regression
- [ ] LLM-layer results reported on data predating the model's training cutoff
- [ ] Per-trade P&L smaller than modeled transaction cost on the smallest real positions
- [ ] Agent layer beating the mechanical baseline **without** a like-for-like cost-and-latency comparison

---

## 6. Research Conclusions

### Strengths
- The chosen exit design (**regime-scaled trailing stop**) is the best-evidenced decision in the project — crypto-specific, cost-robust, Sharpe 1.12→1.42, and the optimal 15–20% threshold band matches what this repo independently arrived at in `ai_bottleneck_stocks`.
- **Regime/volatility conditioning** has genuine theoretical grounding and is corroborated by the repo's own validated four-sleeve work, EDA's vol-clustering finding, and top-journal literature.
- Discovery's refusal to assert an edge up front now looks well-judged: the research would have contradicted at least one asserted mechanism.
- The strategy sits in a repo that already has validated mechanical baselines to measure against — most projects in this space have none, which is precisely the failure the MAS-evaluation audit identifies.

### Weaknesses
- **Mechanism #1's precondition fails on this feature set.** Confluence over collinear signals is not breadth.
- **Mechanism #3 is real but too small and too fast** for a daily cron cadence, and is actively decaying.
- **The multi-agent layer is the least-validated component**, carries measurable API cost, and belongs to a class whose alpha reportedly dissolves under look-ahead control.
- **Data is thin**: 325 feature rows in one regime; no historical replay for ~60+ real-holding tickers; no account equity for Fidelity/Hyperliquid.
- **Account structure fights the strategy**: 69 positions at ~$143 average is a cost structure the literature specifically identifies as return-destroying.

### Recommendations
1. **Invert the build order.** DISCOVERY.md's plan builds the confluence score (step 3) before the regime engine (step 4). Reverse it: build the regime-scaled trend + trailing-stop core first as a standalone, fully-costed baseline. That component has the evidence; it should be the thing everything else must beat.
2. **Deduplicate before scoring.** Collapse the four identical ETF return/flow/vol groups to one representative each. Cheap, and it stops the composite from quadruple-counting one signal.
3. **Make the agent layer earn inclusion by ablation**, with $/run tracked. If the mechanical core matches it, the honest answer is to ship the mechanical core.
4. **Adopt Deflated Sharpe as the headline metric** for anything grid-searched, with the trial count stated.
5. **Set position-size floors and a max-positions cap from real equity**, and charge per-trade costs on actual dollar sizes.
6. **Quarantine the LLM layer from backtested claims** — validate it forward-only in the Alpaca paper sandbox.
7. **Regenerate features to the full 2024-07-23 history** before any IS/OOS split.

### Updated Kill Criteria
Beyond DISCOVERY.md's existing criteria, abandon or de-scope if:
- The confluence layer fails to beat the regime+trailing-stop mechanical baseline on **Deflated** Sharpe after honest cost modeling
- Deduplicating the collinear features removes the confluence layer's apparent edge — this would confirm the edge was redundancy, not breadth
- Realistic per-trade costs at *actual* position sizes turn the backtest unprofitable — a capacity kill, and the most likely one
- The LLM agent layer cannot be shown to add value in forward paper trading within a defined window, at a defensible $/run
- No candidate mechanism survives IS/OOS ablation — report **"no edge found."** DISCOVERY.md already licensed this outcome and the research makes it a live possibility, not a formality

---

## Sources

### Papers
1. [Volatility-Managed Portfolios — Moreira & Muir, J. Finance 2017](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513) ([NBER WP](https://www.nber.org/papers/w22208))
2. [On the performance of volatility-managed portfolios — JFE 2020](https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X)
3. [Stop-loss rules and momentum payoffs in cryptocurrencies — JBEF 2023](https://www.sciencedirect.com/science/article/abs/pii/S2214635023000473)
4. [Risk reduction using trailing stop-loss rules — Dai et al., IRF 2021](https://onlinelibrary.wiley.com/doi/abs/10.1111/irfi.12328)
5. [Agentic Trading: When LLM Agents Meet Financial Markets — arXiv 2605.19337](https://arxiv.org/abs/2605.19337)
6. [Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems — arXiv 2603.27539](https://arxiv.org/pdf/2603.27539)
7. [TradingAgents: Multi-Agents LLM Financial Trading Framework — arXiv 2412.20138](https://arxiv.org/abs/2412.20138)
8. [The Deflated Sharpe Ratio — Bailey & López de Prado](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
9. [Crypto Carry — BIS WP 1087](https://www.bis.org/publ/work1087.pdf) ([Management Science](https://pubsonline.informs.org/doi/10.1287/mnsc.2024.05069))
10. [Time-Series and Cross-Sectional Momentum in Crypto under Realistic Assumptions](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565)
11. [Spot Bitcoin ETFs: Effect of Fund Flows on Price Formation](https://papers.ssrn.com/sol3/Delivery.cfm/5452994.pdf?abstractid=5452994)
12. [Predictability of Funding Rates — Inan](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424)
13. [Combining Forecasts with Many Predictors — Lee](https://faculty.ucr.edu/~taelee/paper/chapter7.pdf)
14. [Ensemble Multi-Expert Forecasting — MDPI JRFM 2025](https://www.mdpi.com/1911-8074/18/6/296)
15. [Look-Ahead-Freedom as Temporal Non-Interference — arXiv 2607.04958](https://arxiv.org/html/2607.04958v1)
16. [Summoning the Oracle to Slay It: Mitigating Look-Ahead Bias with LLMs — arXiv 2605.24564](https://arxiv.org/html/2605.24564)

### Code
1. [polakowo/vectorbt](https://github.com/polakowo/vectorbt)
2. [dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib)
3. [ArturSepp/OptimalPortfolios](https://github.com/ArturSepp/OptimalPortfolios)
4. [asavinov/intelligent-trading-bot](https://github.com/asavinov/intelligent-trading-bot)
5. [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) — incl. [issue #750 on prompt-cache/cost](https://github.com/TauricResearch/TradingAgents/issues/750)

### Articles
1. [FalconX — What Can Spot ETF Flows Tell Us About BTC Prices?](https://www.falconx.io/newsroom/what-can-spot-etf-flows-tell-us-about-the-trajectory-of-bitcoin-prices-a-preliminary-statistical-investigation)
2. [MarketTrace — CVD: the crypto perpetual futures trader's guide to order flow](https://markettrace.ai/blog/cumulative-volume-delta)
3. [Chicago Booth Review — Turning Weak Signals into Strong Predictions](https://www.chicagobooth.edu/review/turning-weak-signals-into-strong-predictions)
4. [Why Retail Traders Consistently Underperform Over Time](https://lanceroberts.substack.com/p/why-retail-traders-consistently-underperform) (Barber–Odean summary)
5. [BackQuant — The Basis Trade Explained](https://www.backquant.com/learn/basis-trade)
6. [Volatility Clustering Strategy with Python and VectorBT](https://pyquantlab.medium.com/volatility-clustering-strategy-with-python-and-vectorbt-8c5b840e88a8)
7. [Deflated Sharpe ratio — Wikipedia](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)

---

*Generated by CBT Framework /cbt:research*
