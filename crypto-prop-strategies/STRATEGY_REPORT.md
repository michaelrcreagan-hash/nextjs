# Optimal Breakout prop strategies — BTC and altcoins, long and short

**Panel:** 8 Coinbase spot series resampled 1h → 4H. 6,567 bars × 8 symbols,
2023‑08‑28 → 2026‑08‑27 (3.00 years). BTC, ETH, SOL, XRP, DOGE, LINK, AVAX, LTC.

**Account rules modelled** (Breakout, as supplied): classic eval $10,000 /
$1,000 target / **$600 static drawdown** / 3% daily. Turbo funded $200,000 /
$18,000 target / **$6,000 static drawdown** / 3% daily. The floor is measured
from the starting balance and **does not reset after a payout**, so a funded
account holds a fixed number of dollars of loss permanently. It is a finite
resource, not a compounding vehicle, and the objective is P(reach target before
breach), with expected payouts before ruin equal to `p/(1−p)`.

---

## The answer

| Book | Verdict |
|---|---|
| **Altcoin long + short, $10k classic** | **Fund it.** The only configuration that survives every robustness test. |
| BTC long + short, $10k classic | Higher headline (83.3%) but fails two stress tests. Trade smaller or not at all. |
| Long‑only, either cohort | **Not viable.** Cannot pass an evaluation at any parameter setting. |
| Short‑only, either cohort | Passes, but each winner is a spike in parameter space. |
| Anything on the $200k turbo | **Nothing clears.** Best is 56.7% and fragile. |

### The recommended strategy — altcoin combined, $10k classic

```
Universe    ETH, SOL, XRP, DOGE, LINK, AVAX, LTC     (BTC used for context only)
Timeframe   4H bars
Risk        0.50% of equity per trade
Stop        2.0 × ATR(14)
Target      1.25R              (take profit at 1.25 × the stop distance)
Concurrent  3 positions max
Daily halt  flatten and stand down for the day at −1.5% from the day's open equity
```

**Entry — long** (all must hold, every input lagged one bar):
prior close > Keltner upper (EMA16 + 1.75×ATR14) · EMA21 > EMA50 ·
Efficiency Ratio(20) ≥ 0.30 · ADX(14) ≥ 25 and rising · volatility regime is
normal or expansion.

**Entry — short:** the same, mirrored — prior close < Keltner lower ·
EMA21 < EMA50 · same quality and regime gates.

**Measured performance** (worst of the bull and bear windows, out of sample):

| | bull window | bear window | worst |
|---|---|---|---|
| Pass rate | 100.0% | 66.7% | **66.7%** (bootstrap lower bound 56.7%) |
| Breach rate | 0.0% | 10.0% | **10.0%** |
| Profit factor | 1.84 | 1.43 | **1.43** |
| Trades / month | 16.8 | 16.9 | ~17 |
| Months to pass | 3.6 | — | ~3–4 |

At a 66.7% pass rate, `p/(1−p)` = **2.0 expected payouts before ruin.**

---

## How it was reached, and what broke along the way

Six stages. Each one overturned something the previous stage believed, which is
the only reason the final number is worth anything.

### Stage 1 — raw edge, before any account rules

All four cohorts showed positive expectancy. BTC long looked outstanding: profit
factor **4.51**. That number is in the repository as `experiments/stage1_edge.json`
and it is meaningless, for the reason stage 2 gives.

### Stage 2 — significance and out-of-sample survival

BTC long's 4.51 rested on **26 trades in three years**. Bootstrapping the trade
level R multiples and splitting in/out of sample killed most of the board:

- **BTC short lost 8 of its 9 gates.** Its best stage 1 gate (PF 2.59) had an
  in‑sample bootstrap lower bound of **−0.386** — statistically indistinguishable
  from no edge at all.
- Alt cohorts carried broadly, on 136–184 trade samples rather than 26.

The lesson is not that BTC is untradeable. It is that a profit factor quoted
without its sample size and its confidence interval carries no information, and
that picking the best of nine gates and reporting its point estimate reports the
maximum of nine noisy draws.

### Stage 3 — the prop sweep, and two defects of my own

The first version of this stage was wrong twice.

1. **The in/out‑of‑sample split was fake.** The simulator runs from its start bar
   to the end of whatever panel it is given, so varying only the start bar does
   not confine a run to the in‑sample region — an "in‑sample" run beginning at
   bar 1300 traded straight through the out‑of‑sample data it was later judged
   on. Each window now gets a genuinely truncated panel.

2. **Ranking on breach rate selected for doing nothing.** Breach‑first ranking
   handed the shortlist to the smallest risk setting on the grid, which never
   breaches for the same reason it never passes. 80–100% of its runs ended
   unresolved and were being scored as safe.

Both were fixed with a hard **six‑month horizon**, so pass / breach / timeout are
mutually exclusive and exhaustive and "ran out of time" is a visible failure
rather than a hiding place.

With the leak closed, the honest picture appeared: **BTC fires 0.4–2.2 trades a
month and times out on 83–97% of evaluations.** Not a losing strategy — an idle
one. Eight trades cannot add up to a 10% target however good each one is.

### Stage 3b — the selection criterion was also wrong

Stage 2 ranked gates on average R **per trade**, which rewards rarity: the
strictest gate posts the best per‑trade number precisely because it only fires on
the clearest setups. A prop evaluation is a race against a deadline, so the
criterion has to be **R per month = avg R × trades per month**. Reranking on that
promoted the looser gates that per‑trade ranking had discarded.

### Stage 4 — the confound that would have invalidated the whole report

Stage 3b concluded shorts pass and longs fail. Checking the calendar showed why
that could not be trusted:

```
IS  2024-04-01 → 2025-06-15   BTC +51.1%, XRP +254%
OOS 2025-06-15 → 2026-08-27   BTC −23.5%, every alt negative, AVAX −60%, DOGE −49%
```

**The out‑of‑sample window is a bear market.** A short book winning there is close
to a tautology. Worse, the long books were selected in a bull window and judged in
a bear one — the least favourable arrangement possible. Two tests followed.

**Reversing the split** (select on bear, judge on bull) did *not* flip the result:
alt shorts still passed 80% with no breaches. So the short edge is real and not
purely a bear‑market artifact — **with one caveat that must travel with the
result: six of the eight assets fell in *both* windows.** "Bull" describes BTC and
XRP, not the alt basket. This panel does not contain a genuine altcoin bull
market, so the short book has never been tested against one.

**Running both directions together** fixed BTC. The two engines are mutually
exclusive by construction (a long needs EMA21 > EMA50, a short needs the
opposite; measured overlap: **0 bars**), so the market decides which side is live
and no regime forecast is needed. BTC went from 0.7–2.2 trades a month to 3.5–5.0,
and from timing out to passing. **BTC's constraint was never edge quality, it was
trade supply.**

### Stage 5 — final selection by minimax

Every earlier stage still left the final choice fitted to whichever window did the
picking — and the best alt configuration selected on the bull window (stop 1.25,
RR 2.0) is *not* the one selected on the bear window (stop 2.0, RR 1.25).
Reporting either alone reports a regime. So every configuration was scored in both
windows independently and ranked on the **worse** of the two, which is also the
number quoted. This deliberately gives up peak performance; what it buys is an
account that is still alive when the regime turns.

### Stage 6 — stress, which disqualified almost everything

| Configuration | Boundary | Neighbourhood | Costs ×2 | |
|---|---|---|---|---|
| **ALT combined classic** | — | median 45.0% vs base 56.7% | −20.0pp, survives | **passes all** |
| BTC combined classic | plateau at 2.0% ✓ | a neighbour breaches 56.7% | −16.6pp but breach 10%→33% | fails |
| BTC short classic | plateau at 1.5% ✓ | median 47% of base | −36.7pp | fails |
| ALT short classic | — | median 39% of base | −26.7pp | fails |
| ALT short turbo | — | median 54% of base | −13.4pp | fails |
| BTC combined turbo | — | median 0% of base | **dies** | fails |

The boundary test mattered: BTC's winner sat at the top of the risk grid (2.0%),
which is truncation rather than optimization until proven otherwise. Extending the
grid showed a genuine plateau — performance peaks at 2.0% and collapses past it
(breach 10% → 30% at 2.5% risk). So that parameter was not an artifact, but the
configuration failed the other two tests anyway.

---

## What this says about the account rules

**Under a non‑resetting floor, smaller targets beat bigger winners.** Every
surviving configuration lands on RR between 1.0 and 1.5, never 2.0+. A 2R target
wins more per trade but loses more often, and each loss permanently consumes a
budget that can never be earned back. This confirms the same finding from the
earlier repository, arrived at independently here.

**Risk sizing is set by trade supply, not by conviction.** The alt book runs 0.5%
because it gets ~17 trades a month; BTC needs 2.0% because it gets ~4. That is
also precisely why BTC is fragile — it has to size up to finish in time, which
leaves it three losses from a breach.

**The $200k turbo is a materially harder product** and nothing here clears it. Its
target‑to‑drawdown ratio is 3:1 ($18,000 against $6,000) versus the classic's
1.67:1 ($1,000 against $600). The classic is not a smaller version of the turbo;
it is a different and much more winnable game.

---

## Limitations — read before funding anything

1. **Three years, one asset class, one market cycle.** Six of eight assets fell in
   both halves. The short engine has never met an altcoin bull market.
2. **30 start dates per window.** A 66.7% pass rate has a bootstrap lower bound of
   56.7%; the true value could reasonably be either.
3. **Survivorship bias.** The universe is today's list of surviving large caps, so
   the alt basket excludes everything that died in the period.
4. **Fills are optimistic in one specific way and pessimistic in another.** Entries
   fill at the bar open with 0.035% taker plus 5bps slippage; exits fill exactly at
   the stop or target. When a bar's range spans both, the stop is assumed to fill
   first. Real stops gap in fast markets, which is exactly when this strategy
   trades. The ×2 and ×3 cost runs are the guard against this and should be read
   as the realistic case, not the pessimistic one.
5. **No funding‑rate model for perpetuals.** Holding costs on multi‑day positions
   are not charged.
6. **The daily‑halt rule assumes it is actually followed.** The −1.5% stand‑down
   is doing real work in the breach numbers, and an operator who overrides it once
   is trading a different and worse strategy.

---

## Reproducing

```
python3 stage1_edge.py       # raw expectancy per cohort per direction
python3 stage2_robust.py     # bootstrap significance + IS/OOS survival
python3 stage3_prop.py       # prop sweep, disjoint panels, 6-month horizon
python3 stage3b_freq.py      # gates reselected on R per month
python3 stage4_regime.py     # reversed split + combined long/short book
python3 stage5_final.py      # minimax selection across both regimes
python3 stage6_stress.py     # boundary, neighbourhood and cost stress
```

Results land in `experiments/*.json` with the console logs beside them.
