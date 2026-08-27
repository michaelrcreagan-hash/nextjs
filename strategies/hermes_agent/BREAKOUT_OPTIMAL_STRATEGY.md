# Breakout Prop — Optimal Strategies

**Date:** 2026-08-27
**Data:** 6,567 4-hour OHLCV bars × 8 symbols, 3.00 years (2023-08 → 2026-08), Coinbase
**Reproduce:** `fetch_4h_panel.py` → `optimize_prop.py` → `optimize_stage2.py` → `optimize_stage3.py` → `optimize_stage4.py`
**Rules:** real Breakout Classic + Turbo, **static floor that does not reset after payout**

---

## The two recommended configurations

Both are the same engine — a 4H Keltner expansion breakout, long and short — differing only in risk and target.

### Classic $10,000 evaluation

| parameter | value |
|---|---|
| engine | 4H Keltner breakout, long **and** short |
| risk per trade | **0.75%** ($75) |
| stop | **1.5 × ATR(14)** |
| target | **1.5R** |
| max concurrent | 3 |
| internal daily stop | **1.0%** (firm's limit is 3% — never go near it) |

| | out-of-sample | full panel |
|---|---:|---:|
| **pass rate** | **100.0%** [100–100] | 98.3% [96.7–100] |
| breaches | **0.0%** | 1.7% |
| trade win rate | 58.3% | 56.5% |
| profit factor | 2.26 | 2.12 |
| trades/month | — | 6.8 |
| median time to target | — | **4.6 months** |

### Turbo $200,000 funded

| parameter | value |
|---|---|
| risk per trade | **0.50%** ($1,000) |
| stop | **1.5 × ATR(14)** |
| target | **1.25R** |
| max concurrent | 3 |
| internal daily stop | 1.0% |

| | out-of-sample | full panel |
|---|---:|---:|
| **pass rate** | **92.5%** [87.5–97.5] | 86.7% [80.0–91.7] |
| breaches | 2.5% | 10.0% |
| **trade win rate** | **65.6%** | 64.2% |
| profit factor | 2.37 | 2.24 |
| trades/month | — | 7.8 |
| median time to target | — | **5.2 months** |
| **E[payouts before ruin]** | **12.3** | — |

Turbo uses **less** risk and a **smaller** target than Classic despite being the larger account. Its floor is 3% versus Classic's 6% — half the buffer — so it must be traded more conservatively, not less.

---

## Why this works when the daily-bar version didn't

My earlier daily-bar test produced 3–8 trades/month against the 15–20 the target math seemed to need, and I concluded the frequency wall was structural. **That was half right.** Moving to 4H bars roughly doubled frequency (6.8–7.8/month), but the decisive change was different: the frequency requirement itself was wrong, because it assumed compounding toward an annual income figure. Under a floor that never resets, the goal is one target hit, not twelve. **7 trades/month at PF 2.2 clears a 10% target in under 5 months with a >90% success rate**, and no amount of extra frequency improves on that — it only adds breach exposure.

Three things the 4H data bought that daily could not:
1. **Real Keltner channels and true-range ATR** — daily close-only data forced a close-to-close ATR proxy. Keltner is defined on high/low.
2. **Intrabar stop fills** — stops now fill at the stop price when the bar's range covers it, with the conservative tie-break (if a bar spans both stop and target, the stop fills first).
3. **The expansion regime is only 7% of bars.** On daily data that gate was invisible. It is the single most important filter in the system.

---

## The finding that changed the design: lower targets beat bigger winners

Under a fixed, non-resetting loss budget, a smaller target is strictly better:

| target | Classic OOS pass | Turbo OOS pass | trade win rate |
|---|---:|---:|---:|
| 1.25R | 95.0% | **92.5%** | **65.6%** |
| 1.5R | **100.0%** | 92.5% | 58–64% |
| 2.0R | 90.0% | 67.5% | 55.0% |

Going from a 2.0R to a 1.25R target on Turbo raised the pass rate from 67.5% to 92.5% and cut drawdown breaches from 32.5% to 2.5%. Larger targets leave trades open longer, and open trades carry floating losses that count against both the daily limit and the floor. Converting risk into closed profit quickly is worth more than occasionally winning bigger. This is the opposite of the usual "let winners run" advice, and it is specific to the prop constraint.

**This is also why the two objectives you asked about coincide here.** Highest trade win rate (65.6%) and highest funded pass rate (92.5%) land on the *same* configuration. That is not guaranteed in general — a 90%-win-rate rule risking 5R to make 0.2R passes nothing — but on this engine the shorter target improves both at once.

---

## What the ChatGPT report got right, and what it didn't

**Validated:**
- The **4H Keltner + MACD + ER/ADX + volatility gate** architecture is the champion. It beat the alternatives decisively.
- **"Leverage is an exposure ceiling, not the source of edge."** Correct, and implemented that way — size comes from stop distance, leverage only caps notional.
- **An internal daily stop well inside the firm's limit.** Set at 1.0% against Breakout's 3%. In every configuration tested, daily-loss breaches were essentially eliminated.
- **Retiring naked 30m/1H breakouts.** Not re-tested here, but the all-filters-off arm (75% pass, 6.7% breaches vs 100%/0%) supports the principle.
- **The report's own honesty about 4%/month.** It declined to promise it. That was correct — see below.

**Did not survive testing:**
- **The EMA21/50 pullback engine, ranked #2 in the report, has negative expectancy on this data**: 0% pass rate, PF 0.48, avg −0.43R. It should be dropped, not demoted. Buying pullbacks in normal-volatility regimes is a losing rule on this panel.
- **The specific ER ≥ 0.30 and ADX ≥ 25 thresholds do no work.** ER at 0.20, 0.30 and 0.40 all produce identical 81.7% pass rates; ADX at 20, 25 and 30 likewise. The **volatility-expansion gate** is doing all the filtering. The trend-quality thresholds are not harmful, but they are not the edge, and tuning them is wasted effort.
- **Donchian as a "robust benchmark"** — 53% pass with 41.7% drawdown breaches. Far riskier than the report's framing implies.

---

## The $70k/year target, restated against the real rules

Still not reachable from one account, and the confirmation that **the floor never resets** makes this firmer, not softer. A $200k account holds exactly $6,000 of loss, permanently. It is a finite resource.

What the numbers support instead:

- Each Turbo target is **$18,000 gross ≈ $14,400 at an 80% split**.
- OOS pass rate 92.5% → **E[payouts before ruin] = p/(1−p) ≈ 12**.
- Median 5.2 months per cycle → roughly **2.3 cycles/year ≈ $33,000/year** from one account, with an expected account lifetime of about 5 years.

To approach $70k/year you would run **two to three funded accounts in parallel**, not push one harder. Pushing one harder is precisely what the risk sweep shows destroys it: Turbo at 0.75% risk breaches 17.5% of the time versus 2.5% at 0.50%.

---

## How much to trust this

**The 100% figures are the weakest numbers here, and I stress-tested them specifically because of that.**

On the full panel the first champion (risk 0.75%, stop 1.5, RR 2.0) passed 100% of 60 windows with zero breaches. Split into halves it produced **85% pass / 0% breaches in-sample against 80% pass / 20% breaches out-of-sample**. The pass rate barely moved while the breach rate went from nothing to one run in five — and on a non-resetting floor, breach rate is the number that matters. The full-panel 100% was hiding it, because runs starting early get a long runway the holdout does not grant. That config was discarded, and Stage 4 re-ranked everything on **OOS breach rate first**.

Other checks that were run:
- **Cost stress:** 100% → 95.0% → 91.7% at 1×/2×/3× fees and slippage. Degrades gracefully.
- **Start-date density:** 30 / 60 / 120 / 240 windows all give the same answer. Not an artifact of window spacing.
- **Bootstrap CIs** over start dates are reported on every row, and configs were ranked by the CI lower bound rather than the point estimate.

Remaining caveats, in order of how much they should worry you:

1. **Overlapping windows are not independent samples.** 40–60 start dates on runs lasting months means heavy overlap. The CIs understate true uncertainty. Trust the *orderings* (1.25R beats 2.0R, 0.5% beats 0.75% on Turbo, Keltner beats pullback) far more than the absolute percentages.
2. **Three years, one market cycle.** 2023-08 → 2026-08 contains one major bull phase and one drawdown. A 2018-style multi-year grind is not in this sample.
3. **Survivorship bias** in the 8-symbol universe — today's liquid names.
4. **No slippage modelling around news or weekends**, which the report correctly flags as where crypto slippage actually lives.
5. **4H bars still hide intrabar path.** Stop-first tie-breaking is the conservative assumption, but a bar that spikes through a stop and recovers is modelled as a loss when live execution might differ either way.

---

## What I would do

1. **Buy the Classic $10k eval and run configuration A** (0.75% risk, 1.5 ATR stop, 1.5R target, 3 concurrent, 1% internal daily stop). It is the highest-confidence result: 100% OOS pass, 0% breaches, ~4.6 months.
2. **On the funded Turbo account, switch to configuration F** — drop risk to 0.50% and the target to 1.25R. Do not carry Classic's settings across; the 3% floor is half the buffer.
3. **Hold the internal 1.0% daily stop as inviolable.** It is why daily-loss breaches are ~0% everywhere in these results.
4. **Do not trade the pullback engine.** Negative expectancy here.
5. **Plan for parallel accounts, not a harder-pushed single account,** if $70k/year remains the goal.
6. **Paper-trade one full regime transition before sizing up**, as the report itself insists. Nothing above substitutes for that.
