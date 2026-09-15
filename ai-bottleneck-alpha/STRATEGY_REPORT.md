# AI bottleneck stocks — optimal long and short strategy

**Universe:** 61 US-listed names at physical chokepoints in the AI buildout, across
12 layers (compute silicon, foundry, semicap, memory/HBM, optics, power &
electrical, power generation, EDA, materials, systems, packaging, data-centre REITs).

**Data:** daily prices 2021-06 → 2026-08 (Yahoo, keyless); point-in-time
fundamentals from SEC EDGAR XBRL, where every fact carries its own filing date.

**Study window:** 2022-01-01 → 2026-08-26. SPY +69%. Equal-weight universe **+403%**.

---

## 1. The headline

| | Long book | Short book | Market-neutral |
|---|---|---|---|
| Signals | eps growth + operating-margin expansion + 12m momentum | distance from 200DMA + momentum/vol | both legs, 50% each |
| Positions | top 5 | bottom 5 | 5 long / 5 short |
| Rebalance | every 2 months | every 2 months | every 2 months |
| **Hit rate (OOS)** | **62.2%** | **73.3%** | — |
| **Profit factor (OOS)** | **3.70** | **3.42** | — |
| CAGR (full) | +132.7% | −23.7% | **+39.0%** |
| Sharpe (full) | 1.76 | −0.56 | 1.13 |
| Max drawdown (full) | −29.8% | −75.4% | **−19.8%** |
| vs SPY (full) | — | — | **+225pp** |

Hit rate = share of picks beating the **equal-weight universe** over the holding
period, not beating zero. Measured against zero a long book scores ~80% here and
means nothing.

**The short book has a higher hit rate than the long book and still loses money
outright.** In a universe that rose 403%, shorting loses regardless of skill. Its
value is relative: the bottom decile lagged the universe by 332 percentage points
over the full period, at a 69.6% hit rate. That makes it a hedge and a funding
leg, never a standalone directional bet.

---

## 2. What actually predicted the winners

Measured as information coefficient — rank the cross-section each month using
only data filed by that date, then wait. 53 monthly cross-sections, 3-month horizon.

| Signal | IC | t | Years positive |
|---|---:|---:|---|
| **eps_yoy** — EPS growth YoY | **+0.125** | 4.9 | **5/5** |
| **backlog_yoy** — RPO backlog growth | **+0.109** | 3.4 | 4/5 |
| **om_delta** — operating margin *expansion* | **+0.104** | 3.6 | 4/5 |
| gm_delta — gross margin *expansion* | +0.102 | 3.4 | 3/5 |
| **dist_200dma** — distance above 200-day MA | **+0.102** | 3.4 | **5/5** |
| **mom_12m** — 12-month momentum | **+0.100** | 3.2 | **5/5** |
| rev_yoy — revenue growth | +0.060 | 2.0 | 4/5 |
| backlog_cover — backlog / TTM revenue *level* | +0.026 | 0.6 | 2/5 |
| rev_accel — revenue **acceleration** | +0.009 | 0.4 | 4/5 |
| op_margin — operating margin *level* | −0.004 | −0.2 | 3/5 |
| gross_margin — gross margin *level* | −0.010 | −0.3 | 3/5 |

At a 6-month horizon `dist_200dma` reaches IC +0.172 (t=7.1) and `backlog_yoy`
+0.149 (t=4.4).

### The central finding: levels don't predict, changes do

The same structure appears in two unrelated signal families, which is what makes
it credible rather than a fluke:

```
gross margin LEVEL   IC −0.010          gross margin CHANGE   IC +0.102
backlog LEVEL        IC +0.026          backlog GROWTH        IC +0.109
```

A high-margin company is not a buy — a company whose margin is *widening* is.
The market has already priced the level; it is repricing the direction. Any
screen built on "high margin, high backlog" is screening on the half that
carries no information.

### What failed, including part of the brief

**Revenue acceleration was the explicit "earnings momentum" candidate and it does
not work here** — IC +0.009, t=0.4, indistinguishable from noise. The second
derivative of revenue is too noisy at quarterly frequency to survive. EPS growth,
a first derivative, is the strongest fundamental in the study. That is a real
result and it is reported rather than quietly replaced.

R&D intensity: nothing (IC −0.003). Backlog *coverage ratio*: nothing.

### Backlog is real and it is available

35 of 61 names disclose `RevenueRemainingPerformanceObligation` under ASC 606 —
this is genuine contracted backlog, not a proxy. Its growth rate is the
second-strongest fundamental signal in the study. Your instinct on backlog was
correct; the qualification is that only its *growth* works.

---

## 3. Which names actually won — and why the answer matters

| Top | | Bottom | |
|---|---:|---|---:|
| POWL | +1975% | IPGP | −57% |
| CRDO | +1844% | GFS | −31% |
| MOD | +1692% | ATKR | −11% |
| VRT | +987% | SMR | −7% |
| MU | +903% | QCOM | −3% |
| NVDA | *+598% (12th)* | SNPS | +14% |

The best performer was a switchgear manufacturer. Third was a maker of vehicle
thermal-management systems. **NVDA came 12th.** The AI trade's largest returns
were in the electrical and thermal layer, not in compute silicon — which is
precisely why the universe had to be defined by function rather than by fame.

---

## 4. The tests that could have killed this

### Random-portfolio null — the decisive one

Concentrating 61 names into 10 raises returns on its own when the return
distribution is this skewed. So the benchmark is not the index; it is the
distribution of **2,000 random 10-name books under identical rules** — same
rebalance dates, same costs, same tradeability mask.

| Window | Strategy | Random median | Random p95 | Percentile |
|---|---:|---:|---:|---:|
| FULL 2022-2026 | +1942% | +317% | +544% | **100.0** |
| IS 2022-2024 | +300% | +82% | +150% | **100.0** |
| OOS 2025-2026 | +419% | +139% | +227% | **100.0** |

A random 10-name book beat the equal-weight universe **32–42%** of the time — so
"beat the index" was never evidence of anything, and the strategy's margin sits
far outside the null.

### Universe hindsight — the most dangerous assumption

The universe was written in 2026. Calling NVDA or ASML an AI bottleneck was
possible in January 2022; calling POWL (switchgear) or MOD (vehicle thermal) one
was not — that thesis became consensus around 2024, and those two names returned
+1975% and +1692%.

Restricting to the 41 names identifiable as AI infrastructure in early 2022
removes the 1st, 3rd and 4th best performers:

| Universe | Return | Its own EW benchmark | Excess |
|---|---:|---:|---:|
| Full 61 names | +1942% | +403% | +1539pp |
| **Early-thesis 41 names** | **+964%** | +327% | **+637pp** |

The edge survives. This is a signal result, not a universe-selection result.

### Everything else

| Stress | Result |
|---|---|
| Fill next day instead of signal close | +1942% → +1924% |
| Fill two days later | → +1761% |
| Costs 10 → 100 bps per side | +1942% → +1501% |
| Position count 5 → 30 | +4437% → +681%, monotonic, Sharpe 1.80 → 1.39 |
| Holding period 1 → 6 months | +1942% → +1652%, CAGR 89–99% throughout |
| Neighbourhood (12 settings, OOS) | long hit 54.4–63.9%, PF 1.82–4.52 |
| Neighbourhood (12 settings, OOS) | short hit 63.2–73.3%, PF 1.20–3.85 |

Nothing here depends on a single parameter choice.

---

## 5. Options

**No historical option quotes were available, so implied volatility is modelled,
not observed.** That assumption drives the entire answer, so instead of picking
one number the IV premium is swept from 0.9× to 1.5× trailing realised vol.

Full period, 2-month expiry, 20% of capital in premium:

| Structure | Hit% | PF | Total return across the IV sweep |
|---|---:|---:|---|
| Stock (baseline) | 58.5% | 3.12 | +4470% |
| ATM call | 44.4–56.3% | 2.39–5.13 | **+968% … +42,943%** |
| 10% OTM call | 37.8–43.0% | 2.16–6.33 | **+879% … +547,503%** |
| **ATM / +20% call spread** | **60.0–60.7%** | **2.54–3.01** | **+1200% … +2621%** |

**Read the spread of that last column, not the headline.** The ATM call's result
varies 44-fold and the 10% OTM's varies 600-fold across plausible IV assumptions
— those are not findings, they are restatements of an assumption I could not
verify. The call spread varies about 2-fold, because buying one option and
selling another cancels most of the vega.

**Recommendation: the ATM / +20% call spread**, on two grounds. It is the only
structure whose conclusion survives not knowing real IV, and on the objective you
set — hit rate and profit factor — it wins outright (71.1% hit / PF 4.45 out of
sample, versus 60.0% / 3.70 for the ATM call). The 10% OTM call is the trap: its
enormous modelled returns come with a **sub-coin-flip 37.8% hit rate** at
realistic premiums.

---

## 6. The strategy

**Long book**
```
Signals    EPS growth YoY + operating-margin expansion YoY + 12-month momentum
           (equal-weighted z-scores, cross-sectionally winsorized at 5/95)
Universe   61 AI bottleneck names; a name must score on ≥2 of the 3 signals
Positions  top 5, equal weight
Rebalance  every 2 months
Data rule  fundamentals enter only on their SEC filing date
```

**Short book** — as a hedge or funding leg, never standalone
```
Signals    distance below 200-day MA + momentum/volatility
Positions  bottom 5, equal weight
Rebalance  every 2 months
```

**Options expression** — ATM / +20% call spread, ~2-month expiry, ≤20% of capital
in premium.

---

## 7. Limitations, ordered by how much they should reduce confidence

1. **One regime.** 2022–2026 contains a single, historic AI capex cycle. Every
   number here describes a period in which the universe tripled. The signals are
   pro-cyclical; none has been tested through an AI capex bust.
2. **OOS is better than IS everywhere** (62.2% vs 56.5% hit, 304% vs 74% CAGR).
   That is not the strategy improving — 2025-26 was a stronger tape. Expect the
   in-sample figures to be the more representative ones.
3. **Universe hindsight is reduced, not eliminated.** The early-thesis test
   handles layer selection, but every name in the study exists in 2026. Companies
   acquired mid-period (e.g. Xilinx, Ansys) are absent, and so is anything that
   failed outright.
4. **Multiple testing.** 18 signals × 3 horizons in the EDA, then 627
   configurations in the sweep. The guards were stability screening, an
   out-of-sample split, equal weights rather than fitted ones, and a
   neighbourhood check — but no Deflated Sharpe Ratio was computed.
5. **Options IV is modelled.** See §5. Verify against real quotes before trading.
6. **Fundamental coverage is uneven.** Gross margin exists for 40/61 names,
   backlog for 32/61. ASML, TSM, UMC, CCJ and GFS are foreign filers with thin or
   absent us-gaap tagging, so they are effectively price-only names.
7. **Original filings, not restatements.** Deliberate — it is what the market saw
   — but it means the panel contains figures later revised.
8. **The market-neutral OOS max drawdown of 0.0%** reflects only 10 two-month
   periods with no losing one. Do not read it as a risk estimate.

---

## 8. Reproducing

```
python3 fetch_prices.py         # Yahoo daily, listing dates enforced
python3 fetch_fundamentals.py   # SEC EDGAR companyfacts
python3 build_panel.py          # point-in-time daily panel
python3 validate_panel.py       # 4 leak tests — must pass before anything else
python3 eda_signals.py          # information coefficients, IC by year
python3 backtest.py             # cross-sectional long/short
python3 null_test.py            # 2,000 random books
python3 robustness.py           # universe hindsight, lag, N, hold, costs
python3 optimize.py             # 627 configs ranked on hit rate and PF
python3 options_overlay.py      # IV sweep across three structures
python3 final.py                # recommended config + neighbourhood
```

Pure NumPy plus the standard library. Full run ≈ 8 minutes, dominated by fetching.
