# hermes_agent — Step 5 Baseline Report

**Date:** 2026-08-27
**Steps built:** 1–5 of 9 (data pipeline, regime engine, exit engine, backtest runner, baseline run)
**Result: THE GATE FAILED. Steps 6–9 were not built.**

BUILD_PLAN.md step 5 set the rule in advance: *"If the baseline fails to beat
both comparison arms, stop and report — steps 6-9 are not worth building on a
core that doesn't work."* It failed. This report is that stop.

---

## Results

| arm | CAGR | max DD | MAR | PF | Sharpe | DSR | fills | final $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **A regime-scaled** (the strategy) | **0.35%** | **−15.41%** | 0.02 | 1.05 | 0.09 | 0.549 | 225 | 80,580 |
| B static 80% (regime engine OFF) | 0.20% | −15.44% | 0.01 | 1.03 | 0.07 | 0.540 | 135 | 80,329 |
| C buy & hold BTC | 9.03% | −53.06% | 0.17 | — | 0.42 | 0.727 | 0 | 95,820 |
| D buy & hold equal-weight | 0.33% | −51.63% | 0.01 | — | 0.23 | 0.628 | 0 | 80,558 |
| A′ **no scale-out** (control arm) | **1.18%** | −19.04% | 0.06 | **1.19** | 0.15 | 0.588 | 899 | 81,978 |

Starting capital $80,000. Window 2024-07-23 → 2026-08-24.

**Gate:** beats static-80% on MAR ✅ · beats buy-and-hold BTC on CAGR ❌ → **FAIL**.

BUILD_PLAN.md says beat *both*. An earlier draft of the gate in `run_baseline.py`
read `beats_static and (beats_btc or beats_ew)`, which would have passed this
run by clearing the weaker buy-and-hold arm. That `or` was wrong and is now an
`and`. Beating an equal-weight basket that itself returned 0.33% is not
evidence of anything, and BTC is the benchmark the stated goal actually names.

---

## What the run establishes

**1. The regime mechanism does exactly what the literature predicts — and that
isn't enough here.** Max drawdown fell from −53.1% (BTC) and −51.6%
(equal-weight) to −15.4%. That is a large, real reduction and it is precisely
the Moreira–Muir (2017) result: volatility management buys *drawdown
reduction*, not return. RESEARCH.md predicted this. But the same mechanism cut
CAGR to 0.35% against BTC's 9.03%. Risk-adjusted, MAR 0.02 vs 0.17 — the
regime arm loses on that too, so this is not a favourable trade being made
invisible by a return-only comparison.

**2. The regime engine beats the static arm — narrowly, and on almost nothing.**
MAR 0.023 vs 0.013 on a 0.35%-vs-0.20% CAGR difference. This clears **R1**'s bar
in direction only. On 54 entries over 1.29 tradeable years the difference is
indistinguishable from noise, and it should not be reported as R1 confirmed.
**R1: not resolved — directionally positive, statistically empty.**

**3. R7 came back NEGATIVE, and that is the most useful thing in this run.**
The hypothesis was that a 50% scale-out at 1R raises profit factor. The control
arm says the opposite on every axis:

| | scale-out ON | scale-out OFF | |
|---|---:|---:|---|
| profit factor | 1.05 | **1.19** | worse with it on |
| CAGR | 0.35% | **1.18%** | worse with it on |
| MAR | 0.02 | **0.06** | worse with it on |

The whole premise of R7 was that the scale-out buys PF at the cost of CAGR —
an exchange rate worth paying. Here it costs *both*. The mechanism is booking
small wins (27 scale-out fills, +$6,033) and then handing the runners back
through breakeven stops (16 fills, −$1,030) before they can develop. That is
the failure mode the `min_move_pct: 3.0` floor was meant to prevent, and the
floor is working as designed on synthetic tests — it just isn't sufficient.
**R7: negative on this data.** One config on a short sample is not a
refutation, but the burden of proof has flipped.

**4. Costs are not the problem.** $1,720 total, 2.15% of initial capital over
2.09 years. The zero-cost arm finishes at $82,271 vs $80,580 — about 2.1pp of
total return. Real, worth minimising, nowhere near the gap to BTC. **R5:
costs at realistic position sizes are survivable; they are not what is
killing this.**

**5. The strategy is 72.5% in cash on average.** RISK_OFF occupies 40.8% of
bars (gross exposure 0), and momentum eligibility is sparse in the rest. You
cannot beat an asset while holding three-quarters cash against it. This is
structural, not a bug — but it means the regime engine as calibrated is the
dominant driver of the return shortfall.

---

## Why the result is weak, in order of how much I distrust it

1. **1.29 tradeable years, 54 entries.** The 200-day moving average in the
   regime engine consumes 200 of 524 bars before the strategy may trade. That
   is 38% of the sample spent flat. Any conclusion drawn from 54 entries is
   fragile, in both directions.
2. **The regime engine runs on proxies, not its specified inputs.**
   `config.strategy_params.regime.source_template` points at
   `macro_sector_dominance`'s `regime_score_model`, which scores VIX, SMH vs
   its DMAs, net liquidity (Fed BS − TGA − RRP), ISM new orders and DXY.
   **None of those five series are in this panel.** `src/regime.py` preserves
   the 0–12 score structure and the four labels exactly, and substitutes SPY
   realized vol for VIX, SPY vs its own DMAs for SMH, TLT trend for net
   liquidity, and BTC vs its DMAs for the ISM/DXY slot. The TLT substitution
   is weak and the ISM/DXY slot is repurposed rather than approximated. A
   failure under proxies is not evidence that regime conditioning fails.
   **This is the first thing to fix, ahead of any new strategy layer.**
3. **The sample window is hostile to long momentum.** Over the panel: ETH
   −28.7%, SOL −42.9%, MSTR −28.8%, TLT −2.3%. Only BTC (+19.8%) and SPY
   (+41.1%) rose. A long-only cross-sectional momentum core on a panel where
   four of eleven names fell hard is being asked to find trends that mostly
   weren't there.
4. **Crypto sits on the NYSE calendar in this panel.** Every row is a weekday;
   BTC/ETH/SOL were downsampled upstream. Weekend moves surface as Monday
   gaps, crypto realized vol is understated, and stops are implicitly
   unactionable Friday→Monday. BUILD_PLAN.md assumed a 5-day/7-day calendar
   join was the main work of step 1; there was none to do.
5. **ATR is a close-to-close proxy** (no intraday H/L), so the 3.0× stop reads
   tighter than a true-range stop would. Exits fill at the *breaching close*,
   not the stop level — conservative, and the only claim this data supports.

---

## Verification performed

Step-by-step, per BUILD_PLAN.md's stated criteria:

- **Step 1** — 524 rows, 2024-07-23 start, matches EDA.md exactly. Zero NaN,
  strictly increasing dates, C-contiguous float64 asserted at load.
- **Step 2** — all four regimes occur (27.7 / 20.8 / 10.7 / 40.8%).
  Truncated-array recompute test passes: the label at bar *t* computed from
  `[0:t+1]` equals the label from the full array, at three probe points. This
  is the check that actually catches a missing `.shift(1)`.
- **Step 3** — seven synthetic-path tests, each asserting the exact exit bar
  and price: initial ATR stop, 1R scale-out, breakeven on the runner,
  trailing stop, `min_move_pct` gate (and that the gate is what suppresses
  it), control-arm-equals-pure-trail, and stop-tested-before-trail ordering.
  All pass (`python3 -m src.test_exits`).
- **Step 4** — four invariants, all passing:
  no trade below the $1,000 position floor (0 of 54);
  deployed capital ≤ regime gross exposure at every bar (0 breaches);
  equity curve finite and positive;
  zero-cost run strictly beats the costed run ($82,271 > $80,580).
- **Step 5** — determinism: re-run reproduces $80,580.31 exactly.

### Three bugs the invariants caught

These were found by the checks, not by reading the code, which is the argument
for writing them:

1. **NaN poisoning the rolling window.** A cumsum-based `rolling_mean` turns
   the entire downstream pipeline to NaN once one NaN enters. One NaN at row 0
   of a shifted return series blanked all 524 regime labels — the first run
   reported 100% RISK_OFF. `rolling_mean` is now NaN-aware.
2. **Gross exposure enforced only at entry.** Deployed capital drifted above
   the cap on 29 bars whenever the regime downgraded, because open positions
   were never trimmed. Without continuous enforcement the regime engine only
   gates *new* entries, which is a materially weaker mechanism than the one
   config.yaml describes — and R1 would have been untestable. Now trimmed
   pro-rata, iterating to convergence (trimming costs money, which lowers the
   cap, which can leave the book marginally over again).
3. **Entry sizing ignored its own cost.** Sizing to the remaining room lands
   just over the cap once the cost is paid. Fixed by solving for the largest
   target that stays inside the cap after cost, and by recomputing the cap
   after each fill on multi-entry bars.

---

## Recommendation

**Do not build steps 6–9 on this core.** The confluence layer, the feature
pipeline and the ML ensemble would all be layered onto a core returning 0.35%,
and RESEARCH.md already rated the confluence layer's diversity precondition as
failing (80 feature pairs >0.9 correlated). Adding layers to a broken core
manufactures overfitting, it does not manufacture edge.

In priority order:

1. **Fix the regime inputs before anything else.** Wire the real series — VIX,
   SMH, FRED net liquidity, ISM, DXY. This is the largest known defect and it
   sits under every result above. Until it is fixed, "regime conditioning
   doesn't work here" is not a supported conclusion.
2. **Extend the price history.** 1.29 tradeable years cannot settle anything,
   and the stated goal is explicitly about 4-year returns. Fetching a longer
   panel is cheap relative to its value.
3. **Re-test R7 (the scale-out) on the fixed setup.** It is currently negative
   on both PF and CAGR. If it stays negative, the exit design should drop the
   scale-out and keep the trailing stop, which the control arm says is the
   better mechanism.
4. **Revisit the RISK_OFF calibration.** 40.8% of bars at zero exposure is the
   proximate cause of the return shortfall. That may be correct behaviour
   under proper inputs, or it may be the proxy being trigger-happy.

Nothing here says the mechanism is dead. It says this build cannot yet tell,
and the honest move is to fix the inputs rather than to keep stacking layers.
