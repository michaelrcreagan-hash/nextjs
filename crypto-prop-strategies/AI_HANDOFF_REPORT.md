# Full technical report — optimal Breakout prop strategies for BTC and altcoins

**Written for an AI system with no access to the originating repository.**
Everything needed to reproduce, audit, or extend the work is contained here:
the problem, the data, the exact strategy specification, every result, the four
errors found and corrected during the work, and the open questions. Where a
claim is uncertain this document says so rather than rounding it into confidence.

---

## 1. The problem

A trader wants strategies for **Breakout** (a crypto prop firm) on two account
types. The firm's rules, as supplied by the trader and used throughout:

| | Classic evaluation | Turbo funded |
|---|---|---|
| Account size | $10,000 | $200,000 |
| Profit target | $1,000 (10%) | $18,000 (9%) |
| Max drawdown | **$600 static (6%)** | **$6,000 static (3%)** |
| Daily loss limit | 3% | 3% |

**The single most important rule: the drawdown is STATIC, measured from the
starting balance, and does not reset after a payout.** The trader confirmed this
explicitly. Every design decision below follows from it.

### Why the static floor changes the objective

A trailing drawdown replenishes as equity rises, so the account behaves like a
compounding vehicle and the right objective is expected growth. A static
non-resetting floor does not replenish. The account holds a **fixed number of
dollars of permanent loss capacity**, and once spent it cannot be earned back.
It is a finite resource being consumed, not capital being compounded.

Two consequences drive everything:

1. **The objective is P(reach target before breach)**, not expected return.
   Expected payouts before ruin is `p / (1 − p)` where `p` is the per-evaluation
   pass probability. At p = 0.5 you expect 1 payout. At p = 0.667 you expect 2.
   At p = 0.9 you expect 9. The function is convex, so marginal improvements in
   pass rate near the top are worth enormously more than near the bottom.

2. **Smaller targets beat bigger winners.** A 2R target wins more per trade but
   loses more often, and each loss permanently consumes budget. Under a fixed
   loss budget the reward-to-risk ratio maximizing *expectancy* is not the one
   maximizing *survival*. Every configuration that survived this study landed on
   RR between 1.0 and 1.5. None chose 2.0 or above. This was found
   independently here and in prior work by the same trader.

### The task as given

> "Create the optimal prop trading strategy for BTC and a separate one for
> altcoins — identify the optimal long strategy and short strategy."

Four strategies, optimized independently: **BTC-long, BTC-short, ALT-long,
ALT-short.** They were kept separate on the prior reasoning that BTC carries
10:1 leverage on this venue versus 2–5:1 for alts, that BTC expresses market
beta while alts express a view against it, and that crypto's up and down moves
have different shapes — downside is faster and more violent, so a short's stop
and target should not automatically mirror a long's.

**That framing turned out to be half right.** The directions do want different
gates. But the *unit of deployment* is not a single direction — see §6.

---

## 2. Data

| | |
|---|---|
| Source | Coinbase spot, 1-hour candles, resampled to 4H |
| Symbols | BTC, ETH, SOL, XRP, DOGE, LINK, AVAX, LTC (8) |
| Span | 2023-08-28 → 2026-08-27 (3.00 years) |
| Bars | 6,567 per symbol, aligned on a common timestamp grid |
| Bar convention | stamped at OPEN time; aggregates `[t, t+4h)` |

**Provenance note.** Several conventional sources were unusable from the build
environment and this constrained the study: Binance returns HTTP 451
(geo-blocked), CoinGecko's `market_chart` returns 401, Stooq returns HTML rather
than CSV, and FRED's `fredgraph.csv` and `data/*.txt` endpoints both time out.
Coinbase's public candles endpoint and Yahoo's chart endpoint work without keys.
An extending study should not assume the same constraints apply elsewhere.

### Market regimes in the panel — critical context

The panel was split 60/40 for validation. The two halves are **different market
regimes**, and this fact invalidated an intermediate conclusion (§6):

```
Window A ("bull")  2024-04-01 → 2025-06-15   bars 1300–3940
Window B ("bear")  2025-06-15 → 2026-08-27   bars 3940–6567
```

| Symbol | Window A return | Window B return |
|---|---:|---:|
| BTC | **+51.1%** | −23.5% |
| ETH | −28.9% | +0.2% |
| SOL | −25.0% | −26.8% |
| XRP | **+254.2%** | −32.1% |
| DOGE | −15.3% | −49.1% |
| LINK | −28.8% | −8.7% |
| AVAX | −63.8% | −60.4% |
| LTC | −18.1% | −41.2% |

**Read this table carefully before trusting any short-side result.** "Bull"
describes BTC and XRP only. **Six of the eight assets fell in both windows.**
The panel contains no altcoin bull market. Any short-side conclusion here is
untested against one.

---

## 3. Strategy specification (exact and complete)

### Indicators

All computed per symbol on 4H closes, then **shifted forward one bar**, so the
decision at bar `t` uses only data through `t−1`.

| Indicator | Definition |
|---|---|
| `ATR` | Wilder-style: `EMA(TrueRange, 14)` |
| `Keltner upper` | `EMA(close, 16) + 1.75 × ATR` |
| `Keltner lower` | `EMA(close, 16) − 1.75 × ATR` |
| `EMA21`, `EMA50`, `EMA200` | exponential MAs of close |
| `ER` | Kaufman Efficiency Ratio over 20 bars: `|C_t − C_{t−20}| / Σ|ΔC|` |
| `ADX` | Wilder ADX, period 14 |
| `ADX slope` | `ADX_t − ADX_{t−14}` |
| `r70` | `ATR / EMA(ATR, 70)` — short-horizon volatility ratio |
| `r1y` | `ATR / EMA(ATR, 2190)` — 2190 bars = 1 year of 4H bars |

`EMA` uses `alpha = 2/(span+1)` seeded with the first observation.

### Volatility regime

Evaluated in this order, later assignments overriding earlier:

```
regime = NORMAL (1)                            # default
if r70 < 0.85:                regime = COMPRESSION (0)
if r70 > 1.15 and r1y > 1.0:  regime = EXPANSION (2)
if r1y > 1.6:                 regime = EXTREME (3)
if r70 is NaN:                regime = NORMAL (1)
```

Panel distribution: BTC 27.7 / 43.2 / 10.8 / 18.3 %; alts 28.2 / 45.2 / 7.0 / 19.6 %
(compression / normal / expansion / extreme).

### Signal gates

Common quality filter for **both** directions:
`ER ≥ 0.30` **and** `ADX ≥ 25` **and** `ADX slope > 0`.

| Book | Direction | Breakout condition | Trend stack | Eligible regimes |
|---|---|---|---|---|
| BTC | long | `prev_close > Keltner upper` | `EMA21 > EMA50` | normal, expansion |
| BTC | short | `prev_close < Keltner lower` | `EMA21 < EMA50 < EMA200` | **all four** |
| ALT | long | `prev_close > Keltner upper` | `EMA21 > EMA50` | normal, expansion |
| ALT | short | `prev_close < Keltner lower` | `EMA21 < EMA50` | normal, expansion |

**Note the asymmetry — it is a finding, not an oversight.** BTC-short is the only
book requiring the 200-EMA stack, and the only one trading all four volatility
regimes. Both were selected empirically. Removing the 200-EMA requirement
collapsed BTC-short's raw profit factor from 2.59 to 1.50, while BTC-long barely
noticed the same change (4.51 → 4.31).

### Execution and accounting

| | |
|---|---|
| Entry fill | market at the **open** of the signal bar |
| Stop | `entry − direction × atr_stop × ATR` |
| Target | `entry + direction × atr_stop × rr × ATR` |
| Position size | `(equity × risk_pct) ÷ (atr_stop × ATR)` units |
| Notional cap | `equity × leverage ÷ max_concurrent` per position |
| Leverage | BTC 10×; ETH/SOL/XRP 5×; DOGE/LINK/AVAX/LTC 3× |
| Costs | 0.035% taker + 5 bps slippage, charged on **both** entry and exit |
| Time stop | market-on-close after 90 bars (15 days) |
| Ambiguous bar | if one bar's range spans both stop and target, **the stop fills** |
| Internal daily halt | at `−X%` from the day's opening marked equity, flatten everything and take no new entries until the next day |
| Breach checks | run on **marked-to-market** equity (open positions included), not realised |

The last two lines matter. The internal daily halt is a strategy parameter set
*tighter* than the firm's 3% hard limit; it is doing measurable work in the
breach statistics. And an earlier version of this simulator compared realised
equity against marked equity, firing the daily-loss rule spuriously — see §7.

---

## 4. Method

Six stages. The design principle throughout: **each stage tries to falsify the
previous stage's conclusion.** Four of the six succeeded in doing so.

| Stage | Question | Outcome |
|---|---|---|
| 1 | Does each cohort/direction have positive raw expectancy? | All four positive |
| 2 | Is that expectancy statistically real, and does it survive out of sample? | **BTC-short mostly fails** |
| 3 | Under real prop rules, what is P(pass)? | **Two defects found in my own code** |
| 3b | Were the gates selected on the right criterion? | **No — per-trade, should be per-month** |
| 4 | Is the result an artifact of the test window's regime? | **Partly — and the fix reframes the product** |
| 5 | Which configuration is best across *both* regimes? | Minimax selection |
| 6 | Does the winner survive boundary, neighbourhood and cost stress? | **Only one of six does** |

### Validation protocol

- **Disjoint truncated panels.** Each evaluation run receives a panel sliced to
  its own window. A run cannot see a single bar outside it.
- **Hard 6-month horizon** (1,080 bars). Every run resolves as pass, breach, or
  timeout — mutually exclusive and exhaustive.
- **30 evaluation starts per window**, evenly spaced. Each start is an
  independent account: fresh equity, fresh floor, fresh clock. This models what
  a trader actually faces — an evaluation begun on an arbitrary day.
- **Bootstrap confidence intervals** (2,000–4,000 resamples), reported as the
  10th percentile. Ranking is always on the **lower bound**, never the point
  estimate.

---

## 5. Results

### 5.1 Raw expectancy, before account rules (stage 1)

Best gate per cohort, full panel, fixed 0.5% risk / 1.5 ATR stop / 1.25R:

| Cohort | Best gate | Trades | Win% | PF | Avg R |
|---|---|---:|---:|---:|---:|
| BTC long | ema200 + expansion | 26 | 80.8 | **4.51** | 0.734 |
| BTC short | ema200 + expansion | 23 | 69.6 | **2.59** | 0.506 |
| ALT long | ema200 + expansion + BTC agrees | 94 | 62.8 | 1.92 | 0.370 |
| ALT short | ema200 + normal/expansion | 275 | 56.0 | 1.43 | 0.212 |

**Every one of these numbers is misleading, and the two largest most of all.**
BTC's profit factors rest on 23–26 trades across three years. Stage 2 exists
because of this table.

### 5.2 Significance and out-of-sample survival (stage 2)

Carry rule: in-sample bootstrap 10th-percentile average R > 0 **and**
out-of-sample average R > 0.

| Cohort | Gates carried | Notable |
|---|---|---|
| BTC long | 6 of 9 | best IS lower bound 0.467 |
| BTC short | **1 of 9** | its stage-1 champion had IS lower bound **−0.386** |
| ALT long | 12 of 12 | samples of 41–256 trades |
| ALT short | 9 of 12 | samples of 56–217 trades |

**BTC-short's headline profit factor of 2.59 was noise.** Its bootstrap interval
on average R spanned −0.386 to +0.510 — it cannot be distinguished from zero
edge at that sample size. Selecting the best of nine gates and quoting its point
estimate reports the maximum of nine noisy draws, not an estimate of anything.

### 5.3 Prop sweep with the horizon enforced (stage 3)

Once the split leak and the ranking defect were fixed (§7), the honest result:

| Cohort | Trades/month | Timeout rate | OOS pass |
|---|---:|---:|---:|
| BTC long | 0.4 – 2.2 | **83 – 97%** | 3.3% |
| ALT long | 1.3 – 2.4 | 83 – 90% | 16.7% |
| ALT short | 9 – 13 | 13 – 30% | 63 – 70% |

**The long books were not losing. They were idle.** At 1.3 trades/month a
six-month evaluation gets ~8 trades, and 8 trades at 0.75% risk cannot sum to a
10% target however good each one is. This is a *trade supply* failure, and it is
qualitatively different from a losing edge — the fix is different too.

### 5.4 Reversing the split (stage 4, test 1)

Selecting on the bear window and judging on the bull window, ALT-short still
passed **80.0% with 0% breaches, PF 2.46**. The short edge did not flip with the
split orientation, so it is not purely a bear-market artifact.

**But see §2.** Six of eight assets fell in both windows. The correct statement
is: *the short edge is robust across the two regimes present in this panel, and
an altcoin bull market is not one of them.*

### 5.5 Running both directions together (stage 4, test 2)

The two engines are **mutually exclusive by construction** — a long requires
`EMA21 > EMA50`, a short requires the opposite. Measured overlap across the full
panel: **0 bars**. A combined book is therefore a genuine single strategy, not a
blend of overlapping bets, and the market decides which engine is live without
anyone forecasting the regime.

| Book | Trades/month alone | Trades/month combined | Effect |
|---|---:|---:|---|
| BTC | 0.4 – 2.2 | **3.5 – 5.0** | timeout → pass |
| ALT | 9 – 14 | **16.8 – 19.6** | pass rate improves |

**This is the study's most useful structural finding.** BTC's constraint was
never edge quality — it was trade supply, and a second engine supplies it. The
task asked for a long strategy and a short strategy as separate deliverables;
the honest answer is that on BTC neither is deployable alone and the pair is.

### 5.6 Minimax selection across both regimes (stage 5)

Every configuration was scored in both windows independently and ranked on the
**worse** of the two, which is also the figure reported. This was necessary
because the best ALT configuration selected on the bull window (stop 1.25, RR
2.0) is *not* the one selected on the bear window (stop 2.0, RR 1.25) —
reporting either alone reports a regime.

Search grid: risk ∈ {0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0}%; ATR stop ∈ {1.25,
1.5, 2.0}; RR ∈ {1.0, 1.25, 1.5, 2.0}; internal daily halt ∈ {1.0, 1.5}%.

| Book | Risk | Stop | RR | Daily | Bull pass | Bear pass | Worst | Breach | E[payouts] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **ALT combined, classic** | 0.50 | 2.0 | 1.25 | 1.5 | 100.0% | 66.7% | **66.7%** | 10.0% | **2.0** |
| BTC combined, classic | 2.00 | 1.5 | 1.25 | 1.5 | 96.7% | 83.3% | 83.3% | 10.0% | 5.0 |
| ALT short, classic | 0.50 | 1.25 | 2.0 | 1.5 | 76.7% | 70.0% | 70.0% | 10.0% | 2.3 |
| BTC short, classic | 1.50 | 1.25 | 1.5 | 1.5 | 70.0% | 66.7% | 66.7% | 10.0% | 2.0 |
| ALT short, turbo | 0.50 | 2.0 | 1.5 | 1.0 | 76.7% | 56.7% | 56.7% | 13.3% | 1.3 |
| BTC combined, turbo | 0.75 | 1.5 | 1.5 | 1.5 | 46.7% | 26.7% | 26.7% | 13.3% | 0.4 |
| ALT combined, turbo | 0.25 | 2.0 | 1.25 | 1.5 | 30.0% | 16.7% | 16.7% | 10.0% | 0.2 |
| ALT long, turbo | 0.75 | 2.0 | 1.0 | 1.5 | 80.0% | 43.3% | 43.3% | **53.3%** | 0.8 |
| **BTC long, any** | — | — | — | — | 0.0% | 0.0% | **0.0%** | 0.0% | 0 |
| **ALT long, classic** | — | — | — | — | 0.0% | 10.0% | **0.0%** | 0.0% | 0 |

Long-only books could not pass at **any** point on the grid.

### 5.7 Stress tests (stage 6) — where five of six finalists died

Three tests, each capable of disqualifying a configuration that looked fine above.

**Boundary.** BTC's winner sat at the top of the risk grid (2.0%), which is
truncation rather than optimization until proven otherwise. Extending to 4.0%
showed a genuine plateau — worst-case pass peaks at 2.0% and collapses beyond
(breach 10% → 30% at 2.5% risk, → 46.7% at 3.0%). BTC-short likewise peaked at
its chosen 1.5%. **Both passed this test.**

**Neighbourhood.** Move each parameter one grid step either way and compare the
*median* neighbour against the base. A base far above its neighbourhood is a
spike fitted to the sample, not a strategy.

| Configuration | Base | Neighbour median | Ratio | Verdict |
|---|---:|---:|---:|---|
| **ALT combined, classic** | 56.7% | 45.0% | **79%** | robust |
| BTC combined, classic | 73.3% | 66.7% | 91% | *a neighbour breaches 56.7%* — fail |
| ALT short, classic | 60.0% | 23.3% | 39% | spike — fail |
| BTC short, classic | 56.7% | 26.6% | 47% | spike — fail |
| ALT short, turbo | 46.7% | 25.0% | 54% | spike — fail |
| BTC combined, turbo | 16.7% | 0.0% | 0% | collapses — fail |

**Costs.** Rerun at 2× and 3× fees and slippage.

| Configuration | ×1 worst lower bound | ×2 | Breach ×1 → ×2 | Verdict |
|---|---:|---:|---:|---|
| **ALT combined, classic** | 56.7% | 36.7% | 10% → 16.7% | survives |
| ALT short, turbo | 46.7% | 33.3% | 13.3% → 20.0% | survives |
| BTC combined, classic | 73.3% | 56.7% | **10% → 33.3%** | breach unacceptable |
| ALT short, classic | 60.0% | 33.3% | 10% → 20.0% | survives |
| BTC short, classic | 56.7% | 20.0% | 10% → 13.3% | −36.7pp, marginal |
| BTC combined, turbo | 16.7% | **0.0%** | 13.3% → 20.0% | **dies** |

**Only ALT combined on the classic account passes all three.**

---

## 6. Conclusions

1. **Deploy the altcoin long+short book on the $10,000 classic.** 0.50% risk,
   2.0 ATR stop, 1.25R target, 3 concurrent, −1.5% internal daily halt.
   Worst-regime pass 66.7% (bootstrap lower bound 56.7%), breach 10%, PF
   1.43–1.84, ~17 trades/month, 3–4 months to pass, ~2.0 expected payouts.

2. **Long-only is not deployable in either cohort.** Not because it loses — its
   raw profit factors are 1.1–1.9 — but because it cannot generate enough trades
   to finish an evaluation. Diagnosis matters: the fix for an idle strategy is
   more signal, not better signal.

3. **The unit of deployment is the direction pair, not the direction.** This
   revises the premise the task was set with. On BTC especially, neither
   direction is deployable alone and the combination is — because they are
   mutually exclusive, so combining them costs nothing in position conflict
   while roughly doubling trade supply.

4. **The $200k turbo is a materially harder product and nothing here clears it.**
   Target:drawdown is 3:1 versus the classic's 1.67:1. The classic is not a
   smaller turbo; it is a different game. A trader should pass the classic
   repeatedly rather than treat it as a stepping stone.

5. **Under a non-resetting floor, smaller targets beat bigger winners.** Every
   surviving configuration chose RR 1.0–1.5. This is a structural property of
   the account rules, not of crypto.

6. **Risk sizing is set by trade supply, not conviction.** The alt book runs 0.5%
   because it gets ~17 trades/month; BTC needs 2.0% because it gets ~4 — which is
   precisely why BTC is fragile, sitting three losses from a breach.

---

## 7. Errors found and corrected during this work

Recorded because an extending system should know which results were revised and
why, and because three of these are easy to repeat.

**1. The in/out-of-sample split was fake.** The simulator runs from its start bar
to the end of whatever panel it is handed. Varying only the start bar therefore
does *not* confine a run to the in-sample region — an "in-sample" run beginning
at bar 1300 traded straight through the out-of-sample data it was later judged
on. **Fix:** each window receives a genuinely truncated panel. *All stage-3
results before this fix were invalid.*

**2. Ranking on breach rate selected for doing nothing.** Breach-first ranking
handed the shortlist to the smallest risk on the grid, which never breaches for
the same reason it never passes: 80–100% of its runs ended unresolved and were
scored as safe. **Fix:** a hard 6-month horizon making pass/breach/timeout
exhaustive, and ranking on the pass rate's bootstrap lower bound subject to a
breach ceiling.

**3. Gate selection used the wrong criterion.** Gates were carried on average R
*per trade*, which rewards rarity — the strictest gate posts the best per-trade
number precisely because it only fires on the clearest setups. A prop evaluation
is a race against a deadline. **Fix:** rank on `avg R × trades per month`.

**4. The fragility label was too lenient.** The first neighbourhood test flagged
a configuration only if some neighbour hit zero, which passed configurations
whose every neighbour halved. **Fix:** compare the *median* neighbour against the
base, and disqualify on any neighbour breaching above 25%.

From prior related work by the same author, worth carrying forward: a
mark-to-market accounting bug that compared realised equity against marked equity
and fired the daily-loss rule spuriously; a gross-exposure cap enforced only at
entry, requiring an iterating de-risk loop because trimming costs money which
lowers the cap; and an initial assumption of *trailing* drawdown which reversed
that study's conclusions once corrected to static.

---

## 8. Limitations

Ordered by how much they should reduce confidence.

1. **No altcoin bull market in the sample.** Six of eight assets fell in both
   windows. The short engine is untested against a sustained alt uptrend, which
   is the single most likely way this strategy fails in deployment.
2. **Three years, one market cycle, one asset class.** The regime split is 60/40
   of a single cycle, not independent cycles.
3. **30 start dates per window.** A 66.7% pass rate carries a bootstrap lower
   bound of 56.7%; the true value could reasonably be either.
4. **Survivorship bias.** The universe is today's surviving large caps. Every
   asset that died during the period is absent, so alt-long results are biased
   optimistic and alt-short results biased pessimistic.
5. **Exit fills are optimistic in a specific way.** Stops and targets fill
   exactly at price. Real stops gap in fast markets — exactly when this strategy
   trades. The ×2 and ×3 cost runs are the guard, and should be read as the
   realistic case rather than the pessimistic one.
6. **No funding-rate model.** Perpetual holding costs on multi-day positions are
   not charged. With a 90-bar (15-day) time stop this is a real omission.
7. **Compliance with the internal daily halt is assumed.** It materially affects
   the breach numbers.
8. **No account-level correlation control.** Three concurrent alt positions in a
   correlated selloff are closer to one position than three, and the 3% daily
   limit is the only thing bounding that.

---

## 9. Open questions for an extending system

Ordered by expected value.

1. **Find or construct an altcoin bull sample** (2020-06 → 2021-05, or
   2016-2017) and re-run the short engine against it. This is the highest-value
   test available and it addresses limitation #1 directly.
2. **Build a point-in-time universe** with delisted assets included, to quantify
   the survivorship bias in #4 rather than merely acknowledging it.
3. **Model funding rates** on perpetuals and re-run. The 15-day time stop makes
   this potentially material.
4. **Test whether the direction pair generalizes** to other cohorts — does
   combining directions rescue trade supply anywhere else, or is it specific to
   BTC's low signal frequency?
5. **Test position-level correlation caps** (e.g. max 2 concurrent positions with
   >0.8 trailing correlation) against the observed 10% breach rate.
6. **Walk-forward with rolling re-selection** rather than a single 60/40 split,
   which would give a distribution of out-of-sample results instead of one.
7. **Deflated Sharpe Ratio** across the full configuration search, to quantify
   selection bias from the ~500 configurations examined. This study controlled
   for it procedurally (lower-bound ranking, minimax, stress tests) but never
   computed it.

---

## 10. Reproduction

```
stage1_edge.py       raw expectancy per cohort per direction, no account rules
stage2_robust.py     bootstrap significance + IS/OOS survival
stage3_prop.py       prop sweep, disjoint panels, 6-month horizon
stage3b_freq.py      gates reselected on R per month
stage4_regime.py     reversed split + combined long/short book
stage5_final.py      minimax selection across both regimes
stage6_stress.py     boundary, neighbourhood and cost stress
```

Run in order; each reads the previous stage's JSON output. Results are written to
`experiments/*.json` with console logs beside them. Core engine — indicators,
signals, and the account simulator — is in `src/engine.py`. Pure NumPy, no
dependencies beyond the standard library plus NumPy. Full run time is
approximately 10 minutes.
