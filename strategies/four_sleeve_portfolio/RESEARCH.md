# Strategy Research: four_sleeve_portfolio (per-sleeve deep dive)

**Date:** 2026-07-08
**Research Scope:** Full — applied to each sleeve individually, plus
cross-cutting portfolio mechanics
**Empirical baseline:** the completed mechanical backtest
(`trading/hedgefund/monte_carlo/SLEEVE_BACKTEST_REPORT.md`): 32.6% CAGR /
-17.3% DD (2023-2026), 9.0% CAGR / -23.0% DD (2010-2023).

---

## Executive Summary

Each sleeve rests on a *real, documented* edge — sector/industry momentum
(Sleeve 1), crisis-hedge carry (Sleeve 2), concentrated momentum in
secular growth (Sleeve 3), and capital-efficient covered-call structure
(Sleeve 4) — but every one of those edges is weaker, choppier, and more
regime-dependent in the literature than in the architecture note's
projections. The academic record directly supports our backtest's core
finding: the 50-80% annualized target is a supercycle artifact, not a
durable base rate. The strongest research-backed upgrades are (1) replace
the binary trend gate with volatility-managed sizing (Moreira-Muir), (2)
add a momentum-crash guard to the innovation sleeve (Daniel-Moskowitz),
and (3) diversify rebalance timing to kill timing luck.

**Overall Confidence:** Medium — solid foundations, inflated expectations.
**Recommendation:** Proceed with caution; optimize per-sleeve as below.

---

## Sleeve 1 — Macro Rotation (sector/theme momentum + cycle timing)

### Literature

| Finding | Source | Relevance |
|---|---|---|
| Industry momentum is real and drives much of stock-level momentum; buy past-winner industries earned ~0.43%/mo | [Moskowitz & Grinblatt 1999, *Do Industries Explain Momentum?*](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00146) ([PDF](http://www-stat.wharton.upenn.edu/~steele/Courses/956/Resource/Momentum/MoskowitzGrinblatt99.pdf)) | ⭐⭐⭐⭐⭐ |
| Sector-rotation momentum still validates out-of-sample 2020-2025; quarterly rebalancing beats faster cadences | [MDPI 2026 TSX-60 study](https://www.mdpi.com/1911-8074/19/1/70) | ⭐⭐⭐⭐ |
| Sector momentum rotational systems documented as a standing anomaly | [Quantpedia — Sector Momentum](https://quantpedia.com/strategies/sector-momentum-rotational-system) | ⭐⭐⭐⭐ |
| US/Europe evidence that sector rotation efficacy is regime-dependent and decays when crowded | [Journal of Asset Management 2020](https://link.springer.com/article/10.1057/s41260-020-00161-6) | ⭐⭐⭐⭐ |
| Presidential cycle: years 3-4 outperform years 1-2 by ~10%/yr excess; unexplained by risk premia | [Sturm, *Washington meets Wall Street*](https://www.sciencedirect.com/science/article/abs/pii/S0261560613001721); [Forbes overview](https://www.forbes.com/sites/georgecalhoun/2020/10/30/the-presidential-election-cycle-and-the-stock-market-a-classic-calendar-anomaly/) | ⭐⭐⭐⭐ |
| Midterm years ~87% positive, avg >19%; Year-3 historically strongest | [QuantifiedStrategies — election cycles](https://www.quantifiedstrategies.com/president-election-cycles/); [IBKR 2026 seasonality](https://www.interactivebrokers.com/campus/traders-insight/securities/technical-analysis/sp-500-seasonality-and-presidential-cycles-what-historical-patterns-suggest-for-2026/) | ⭐⭐⭐ |

### Verdict on the edge
Real (industry momentum is one of the most robust anomalies), but our
implementation *timed* it with a calendar-cycle overlay whose statistical
base is ~19 independent cycles — enough for a tilt, not a conviction.
Our backtest agrees: the cycle overlay cut drawdown 3.5-3.7pp at ~zero
CAGR cost — keep it as a *risk* tool, not a return tool.

### Optimization recommendations (Sleeve 1)
1. **Rank, don't gate.** Replace the binary 200DMA gate on macro members
   with cross-sectional 3/6/12-month relative-strength ranking (the
   Moskowitz-Grinblatt formulation, already how `themes.py` works) —
   the ablation showed the binary gate cost -2.8 CAGR in 2023-26.
2. **Quarterly core cadence** matches the best out-of-sample evidence;
   keep regime-change rebalances event-driven on top.
3. Treat the presidential-cycle multiplier as a de-risking modifier only
   (as backtested); never let it push weights above the regime row.

---

## Sleeve 2 — Income / Hedge / Carry (TLT, GLD, PFF, GDXJ)

### Literature

| Finding | Source | Relevance |
|---|---|---|
| 2022: 60/40 fell 17.5%, worst since 1937 — stock-bond correlation flipped positive under inflation | [QuantifiedStrategies 60/40 analysis](https://www.quantifiedstrategies.com/60-40-portfolio-strategy/); [Investing.com correlation piece](https://www.investing.com/analysis/6040-portfolio-at-risk-bondstock-correlation-shifts-in-high-inflation-200666128) | ⭐⭐⭐⭐⭐ |
| Positive stock-bond correlation was the *norm* before 2000 — the hedge is regime-conditional, not structural | [Forbes 2026, *60/40 under stress again*](https://www.forbes.com/sites/investor-hub/2026/04/17/the-6040-portfolio-is-under-stress-again-and-this-time-is-different/) | ⭐⭐⭐⭐⭐ |
| Duration hedges growth shocks but amplifies inflation shocks; stagflation breaks both hedges at once | [Mueller-Glissmann (GS) via BigGo](https://finance.biggo.com/news/62770a0a11a164db) | ⭐⭐⭐⭐ |
| Gold-enhanced 60/40 cut the 2022 drawdown from -16.9% to -14.5%; gold works precisely when correlation flips | [Man Group, *Gold: Bugs, Bears and Myths*](https://www.man.com/insights/gold-bugs-bears-myths) | ⭐⭐⭐⭐ |

### Verdict on the edge
This sleeve is insurance, not alpha — and the literature says its main
instrument (TLT) is *conditionally* unreliable: it hedges growth scares
and fails inflation shocks. Our backtest saw exactly this: standalone
income sleeve did 3.0% CAGR with a **-32.7% drawdown** over 2010-2023
(2022 was the drawdown), yet realized correlation to the macro sleeve was
-0.05 — the diversification did work on average.

### Optimization recommendations (Sleeve 2)
1. **Split the duration bet.** The note's own Part-4 ladder (TLT/IEF/SHY)
   was collapsed to TLT-only in implementation; adding IEF+SHY halves
   duration in CAUTION/RISK-OFF driven by *inflation* vs growth (a CPI
   or trend-of-TLT conditional).
2. **Gold deserves the anti-correlation slot more than bonds** in
   inflationary regimes — allow the GLD share to expand when the
   trailing 12m stock-bond correlation is positive.
3. Do not expect carry: realized sleeve return was ~3-8.6%; its job is
   the -0.05 correlation, and it did it.

---

## Sleeve 3 — Innovation / High-Conviction (concentrated momentum)

### Literature

| Finding | Source | Relevance |
|---|---|---|
| Momentum strategies suffer rare, violent crashes (-88% 1932, -46% 2009) in panic-rebound states; crashes are partly forecastable from volatility | [Daniel & Moskowitz, *Momentum Crashes*, JFE 2016](https://www.sciencedirect.com/science/article/pii/S0304405X16301490) ([SSRN](https://www.ssrn.com/abstract=2486272), [NBER](https://www.nber.org/papers/w20439)) | ⭐⭐⭐⭐⭐ |
| Dynamic (vol-scaled) momentum roughly doubles alpha and Sharpe vs static momentum | [Daniel & Moskowitz 2016](https://www.kentdaniel.net/papers/published/jfe_16.pdf); [Alpha Architect summary](https://alphaarchitect.com/avoiding-momentum-crashes/) | ⭐⭐⭐⭐⭐ |
| Specialized/thematic products launched at theme peaks underperform ~-6%/yr for 5 years post-launch — attention-chasing baskets embed peak valuations | [Ben-David, Franzoni, Kim & Moussawi, *Competition for Attention in the ETF Space*, RFS 2023](https://academic.oup.com/rfs/article-abstract/36/3/987/6655702) ([NBER](https://www.nber.org/papers/w28369)) | ⭐⭐⭐⭐⭐ |

### Verdict on the edge
This is the portfolio's engine and its biggest hazard, and the
literature is unambiguous on both. Our numbers replicate the pattern:
standalone innovation did 163% CAGR (2023-26) but 9.3% CAGR with a
**-74% drawdown** (2010-23), and per-sleeve Monte Carlo says a >25%
sleeve drawdown is a near-certainty in *any* regime. The Ben-David
et al. finding maps directly onto buying quantum/miner names after
vertical runs — the momentum entry criterion partially defends against
it, but conviction-list membership (added *because* a theme is hot) is
exactly the attention-chasing behavior that paper prices at -6%/yr.

### Optimization recommendations (Sleeve 3) — highest priority
1. **Momentum-crash guard (Daniel-Moskowitz dynamic momentum):** scale
   sleeve exposure by inverse realized volatility and cut it after
   market-panic states (VIX spike + market rebound), instead of the
   fixed 35%-cap-times-cycle. This is the single best-documented upgrade
   available (~2x Sharpe on the momentum component in the literature).
2. **Keep the $5 investability floor permanently** (added during the
   backtest) — the raw data showed how shell-era penny names fabricate
   untradeable returns.
3. **Membership discipline:** require a name to be in the list *before*
   its theme trends (layer-cake/bottleneck thesis), not after — and
   time-stamp additions so future backtests can detect hindsight
   membership. This is the direct mitigation for the thematic-peak trap.

---

## Sleeve 4 — Options Overlay (PMCC / LEAPS diagonal)

### Literature

| Finding | Source | Relevance |
|---|---|---|
| Covered-call (BXM) returns ≈ equity returns at lower beta; short-vol adds ~2%/yr at Sharpe ~1, but ~25% of risk is uncompensated equity-timing exposure | [Israelov & Nielsen, *Covered Calls Uncovered* (AQR)](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf) ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2444999); [Quantpedia summary](https://quantpedia.com/covered-calls-uncovered/)) | ⭐⭐⭐⭐⭐ |
| Hedging the residual equity-timing risk lifts covered-call Sharpe 0.37→0.52 | [CXO Advisory on Israelov-Nielsen enhancement](https://www.cxoadvisory.com/equity-options/enhancement-of-index-covered-calls-via-hedging/) | ⭐⭐⭐⭐ |
| PMCC/diagonals: 15-30% of covered-call capital for similar exposure; practitioner backtests show high return-on-capital with ~1/3 beta but -30%+ drawdowns on capital | [Lambda Finance diagonal backtests](https://www.lambdafin.com/articles/diagonal-spread-options-strategy); [BXM index dashboard](https://www.cboe.com/us/indices/dashboard/bxm/) | ⭐⭐⭐ |

### Verdict on the edge
Structurally sound and the *least* controversial sleeve: the capital
efficiency is mechanical fact, and the short-call income is a documented
(small) volatility risk premium. Our simulated sleeve (28.7% CAGR /
-12.9% DD in 2023-26 with zero assumed sell edge) sits inside the
literature's plausible band. Main caveat: everything here is
Black-Scholes-simulated — real chains add slippage, pin risk, and
early-assignment frictions the sim ignores.

### Optimization recommendations (Sleeve 4)
1. Adopt the Israelov-Nielsen finding directly: the strategy's
   *uncompensated* risk is equity timing from the short call's changing
   delta — rolling the short leg on a delta band (e.g. re-strike when
   |Δ| drifts >0.15 from target) rather than the calendar-only 21-DTE
   rule removes risk the market doesn't pay for.
2. Skip the short leg on hyper-momentum names (already the desk's
   validated rule — literature concurs: capping the right tail on
   high-momentum underlyings costs more than premium collects).

---

## Cross-cutting portfolio mechanics

| Finding | Source | Application |
|---|---|---|
| Volatility-managed portfolios (scale exposure ∝ 1/variance) raise Sharpe ~25% and add ~4.9% alpha on the market factor | [Moreira & Muir, *Volatility-Managed Portfolios*, JF 2017](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513) ([NBER](https://www.nber.org/papers/w22208)) | Replace/augment the discrete 4-state matrix with continuous vol-scaling inside each equity sleeve |
| Simple 10-month SMA trend filter cuts drawdowns across asset classes but whipsaws in fast reversals; hysteresis buffers help | [Faber, *A Quantitative Approach to TAA*](https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf); [whipsaw mechanics](https://www.volatilitytradingstrategies.com/blog/article-626-tactical-investing-whipsaw-what-is-it-how-to-reduce-it) | Our trend gate is Faber-style; the -2.8 CAGR whipsaw cost we measured is the known failure mode — add a hysteresis band (e.g. exit 2% below MA, re-enter 2% above) |
| Regime-based allocation adds ~2%/yr when regimes are detected well; hidden-Markov / macro-regime detection outperforms calendar rules | [Tactical allocation with macro regime detection (2026)](https://www.tandfonline.com/doi/full/10.1080/14697688.2026.2659195); [Resonanz Capital review](https://resonanzcapital.com/insights/regime-based-allocation-what-it-actually-delivers) | The VIX/trend/breadth/BTC regime score is defensible; HMM upgrade is a research option, not a need |
| Deflated Sharpe ratio corrects for multi-trial selection bias; without it, backtest winners systematically disappoint | [Bailey & López de Prado, *The Deflated Sharpe Ratio*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) ([PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)) | We ran ~7 variants (1 spec + 6 ablations), not a grid search — selection-bias risk is low but should be tracked as variants accumulate |

---

## Edge validation summary

| Sleeve | Academic support | Still profitable | Theoretical basis | Competition |
|---|---|---|---|---|
| 1 Macro rotation | Yes (industry momentum) | Likely, decaying | Strong (underreaction) | High |
| 2 Income/hedge | Partial (regime-conditional) | As insurance, yes | Strong (flight-to-safety) | N/A (beta) |
| 3 Innovation | Yes with crash caveat | Regime-dependent | Medium (momentum + narrative risk) | High & crowded |
| 4 Options PMCC | Yes (BXM literature) | Yes, modest | Strong (vol risk premium + capital efficiency) | Medium |

### Regime expectations (literature + our two-era backtest)

| Regime | Portfolio expectation |
|---|---|
| Bull/supercycle (2023-26-like) | 30-40% CAGR; innovation sleeve dominates |
| Grind bull (2010s-like) | 9-12% CAGR; roughly SPY-with-lower-DD |
| Fast crash + V-recovery (2020) | Trend gate + momentum both whipsaw — weakest setup |
| Slow bear (2022) | Best relative setup: regime matrix de-risks, gold offsets |
| Stagflation | **Untested worst case** — TLT and equities fall together; gold is the only hedge |

---

## Risks & pitfalls (ranked)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Innovation momentum crash on market rebound | High (episodic) | High | Daniel-Moskowitz dynamic scaling; crash-state de-risk rule |
| Thematic membership added at peak attention | High | Medium-High | Time-stamped membership; require pre-trend thesis |
| Stagflation breaking TLT hedge | Medium | High | Duration ladder + correlation-conditional gold expansion |
| Trend-gate whipsaw in V-recoveries | High | Medium | Hysteresis bands; or replace gate with vol-scaling |
| Options sim vs real chains gap | Certain (some gap) | Medium | Paper-trade sleeve 4 live before sizing to 10% |
| Backtest selection bias as variants accumulate | Low now, grows | Medium | Track trial count; report deflated Sharpe going forward |
| Rebalance timing luck (monthly/quarterly anchor days) | Medium | Low-Medium | Tranche rebalances across the month (overlapping portfolios) |

### Red flags to watch
- [ ] Innovation sleeve >40% portfolio weight after cycle multiplier (leverage-cap bug class)
- [ ] Regime spending >70% of days in RISK-ON while VIX term structure inverts
- [ ] Sleeve-2 correlation to sleeve-1 rising above +0.3 for a quarter (hedge decay)
- [ ] New names entering the innovation list within 3 months of a >100% run

---

## Research conclusions

**Strengths:** every sleeve maps to a documented premium; the realized
cross-sleeve correlations (-0.05 income/macro) beat the note's own
assumptions; the risk architecture (matrix > stop) behaved exactly as
the regime literature predicts.

**Weaknesses:** return targets are calibrated to the best regime in the
sample; the trend gate is provably the weakest department; the income
sleeve's key instrument fails in the one scenario (stagflation) the
sample doesn't contain.

**Priority order for optimization (evidence-weighted):**
1. Sleeve 3: dynamic momentum / crash guard (largest documented gain)
2. Portfolio: hysteresis on the trend gate, or vol-scaling replacement
3. Sleeve 2: duration ladder + correlation-conditional gold
4. Sleeve 4: delta-band rolls (small, clean win)
5. Sleeve 1: rank-based selection at quarterly cadence (already close)

### Updated kill criteria (additions from research)
- Abandon vol-scaling upgrade if it doesn't cut MC P(DD>25%) below 3%
  at equal or better median CAGR
- Abandon the cycle overlay if the next full presidential cycle (through
  2028) shows it *adding* drawdown out-of-sample
- Treat any future backtest > 45% CAGR as suspect until the deflated
  Sharpe (trial-adjusted) is computed

---

## Sources

### Papers
1. [Moskowitz & Grinblatt (1999) — Do Industries Explain Momentum?](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00146)
2. [Daniel & Moskowitz (2016) — Momentum Crashes, JFE](https://www.sciencedirect.com/science/article/pii/S0304405X16301490)
3. [Ben-David, Franzoni, Kim & Moussawi (2023) — Competition for Attention in the ETF Space, RFS](https://academic.oup.com/rfs/article-abstract/36/3/987/6655702)
4. [Israelov & Nielsen — Covered Calls Uncovered, AQR](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf)
5. [Moreira & Muir (2017) — Volatility-Managed Portfolios, JF](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513)
6. [Bailey & López de Prado — The Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
7. [Faber — A Quantitative Approach to Tactical Asset Allocation](https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf)
8. [Sturm — Washington meets Wall Street (presidential cycle)](https://www.sciencedirect.com/science/article/abs/pii/S0261560613001721)
9. [Tactical asset allocation with macroeconomic regime detection (2026)](https://www.tandfonline.com/doi/full/10.1080/14697688.2026.2659195)
10. [MDPI (2026) — Sector Rotation in the TSX 60, out-of-sample validation](https://www.mdpi.com/1911-8074/19/1/70)

### Practitioner / data
11. [Quantpedia — Sector Momentum Rotational System](https://quantpedia.com/strategies/sector-momentum-rotational-system)
12. [Alpha Architect — Avoiding Momentum Crashes](https://alphaarchitect.com/avoiding-momentum-crashes/)
13. [Man Group — Gold: Bugs, Bears and Myths](https://www.man.com/insights/gold-bugs-bears-myths)
14. [QuantifiedStrategies — 60/40 backtests & alternatives](https://www.quantifiedstrategies.com/60-40-portfolio-strategy/)
15. [QuantifiedStrategies — Presidential election cycles](https://www.quantifiedstrategies.com/president-election-cycles/)
16. [Cboe BXM Index Dashboard](https://www.cboe.com/us/indices/dashboard/bxm/)
17. [Lambda Finance — Diagonal spread backtests](https://www.lambdafin.com/articles/diagonal-spread-options-strategy)
18. [CXO Advisory — Enhancement of index covered calls via hedging](https://www.cxoadvisory.com/equity-options/enhancement-of-index-covered-calls-via-hedging/)
19. [Resonanz Capital — Regime-based allocation: what it actually delivers](https://resonanzcapital.com/insights/regime-based-allocation-what-it-actually-delivers)
20. [VolatilityTradingStrategies — Whipsaw mechanics & mitigation](https://www.volatilitytradingstrategies.com/blog/article-626-tactical-investing-whipsaw-what-is-it-how-to-reduce-it)

### In-repo empirical evidence
21. `trading/hedgefund/monte_carlo/SLEEVE_BACKTEST_REPORT.md` — two-era
    backtest, department ablations, 10k-path Monte Carlo (the numbers
    cited throughout this document)

---

*Generated by CBT Framework /cbt:research*
