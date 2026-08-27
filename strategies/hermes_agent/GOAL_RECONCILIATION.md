# Goal Reconciliation — the `/cbt:build /goal` scope

**Date:** 2026-08-27
**Status:** scope mapped, not yet built. hermes_agent stopped at its step-5 gate
(see BASELINE_REPORT.md); this document says what the new goal changes.

The `/goal` argument passed to `/cbt:build` expands the work well past what
BUILD_PLAN.md and config.yaml cover. It contains **six distinct asks**, three
of which are new strategies rather than changes to hermes_agent. This maps each
one, and states plainly where the arithmetic or the data does not support it.

---

## The six asks

| # | Ask | Where it belongs | Blocked on |
|---|---|---|---|
| 1 | Fidelity: high-beta, yield/income, options, macro hedge | **new strategy** (4 sleeves) | Fidelity balance unknown; no options chain data; no panel for these names |
| 2 | Crypto spot: BTC + ETH + top-25 alts bought at the 4-year low | hermes_agent extension | top-25 alts absent from panel; panel is 2.09y, cannot see a 4-year low |
| 3 | 20% of crypto to leverage / micro-cap satellites | hermes_agent extension | `leverage.enabled: false` by prior decision; no micro-cap data |
| 4 | Iterate to ">3:1 vs BTC over 4 years" | benchmark change | **see the arithmetic below** |
| 5 | Breakout prop firm: bull + bear crypto strategies | **new strategy** | firm's actual rules unconfirmed |
| 6 | US futures prop firm: futures, indices, commodities | **new strategy** | no futures data in repo |

---

## Ask 4: the ">3:1 vs BTC" benchmark — the arithmetic

This needs the same treatment the $1.5M target got at the start of this
project, because the answer depends entirely on which window it is measured
over, and the two answers are very far apart.

**Measured over this panel's actual window (2024-07-23 → 2026-08-24, 2.09y):**
BTC returned **+19.8% total** (9.03% CAGR). Three times that total return is
+59.4% over 2.09 years = **25.4% CAGR**. That is demanding but not absurd.

**Measured over a true 4-year window at BTC's historical rate:** BTC at a
30–35% CAGR compounds to 1.86×–2.32× over four years. Three times *that* total
return is 5.57×–6.96×, which requires:

| BTC 4y CAGR | BTC 4y total | 3× that | required CAGR |
|---:|---:|---:|---:|
| 30% | 1.86× | 5.57× | **60.1%** |
| 32% | 2.04× | 6.11× | **63.3%** |
| 35% | 2.32× | 6.96× | **68.0%** |

So "3:1 versus BTC over 4 years" means **a sustained 60–68% CAGR** — the same
order of magnitude as the ~101.5% target already agreed to lower, and roughly
double the 40–65% band settled on as the honest ceiling for this project.

**Two things follow, and I'd rather say them now than after building toward it:**

- The benchmark is not scale-free. "3:1 vs BTC" is an easy target in a flat
  BTC window and a near-impossible one in a bull window. Ratcheting a target to
  an asset's realised return means the target is hardest exactly when the asset
  did well — which is when a 3:1 multiple is least likely.
- **The data cannot test it at all.** `Data/btc_historical_data.csv` starts
  2024-07-23. There is no 4-year window in this repo, and after the regime
  engine's 200-day warm-up the tradeable sample is **1.29 years**. Any "4-year
  return" reported from this panel today would be fabricated.

**Recommendation:** keep the 3:1 ratio as the *stated ambition*, but fix the
comparison window and state it — "3× BTC's total return measured over the same
backtest window" is a testable claim; "3× BTC over 4 years" is not, until
there are four years of data. Fetching a longer panel is the cheapest
high-value item on the whole list and it unblocks asks 2 and 4 together.

---

## Asks 5 & 6: the prop-firm targets — the arithmetic

Target: **$70k/year**, from **4%+/month on a $100k crypto prop account** and
**4%+/month on a $100k futures prop account**.

**The $70k and the 4%/month are consistent with each other.** 4%/month
compounded is **60.1%/year**, so $60k gross per account, $120k across two. At a
typical 80/20 prop split that nets ~$96k; $70k/yr is comfortably inside it.
Nothing wrong with the target's internal arithmetic.

**What it actually requires.** Monthly return ≈ trades × expectancy(R) ×
risk-per-trade. Solving for the edge needed to make 4%/month:

| trades/mo | risk/trade | required expectancy | ≈ PF at 2:1 R:R | implied win rate |
|---:|---:|---:|---:|---:|
| 5 | 1.0% | 0.80 R | 3.00 | 60.0% |
| 10 | 1.0% | 0.40 R | 1.75 | 46.7% |
| 20 | 1.0% | 0.20 R | 1.33 | 40.0% |
| 40 | 1.0% | 0.10 R | 1.16 | 36.7% |
| 5 | 0.5% | 1.60 R | 13.00 | 86.7% ← impossible in practice |

So 4%/month is reachable at a **PF of roughly 1.3–1.8, provided the frequency
is 20–40 trades/month**. At low frequency it requires an edge nobody has.

**But the drawdown limit, not the edge, is what ends prop accounts.** Monte
Carlo over 12 months, 20,000 paths, 10% trailing drawdown from high-water mark
(the harder and common variant — confirm Breakout's exact rule before relying
on this):

| risk/trade | win% | R:R | trades/mo | PF | survive 12mo | survive **and** clear +60% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5% | 50% | 2.0 | 20 | 2.00 | **99.8%** | 86.4% |
| 1.0% | 50% | 2.0 | 10 | 2.00 | 91.7% | 70.8% |
| 1.0% | 45% | 2.5 | 12 | 2.05 | 80.5% | 78.0% |
| 1.0% | 55% | 1.5 | 15 | 1.83 | 89.2% | 80.5% |
| **2.0%** | 50% | 2.0 | 10 | 2.00 | **25.0%** | 25.0% |
| 1.0% | 40% | 2.0 | 10 | 1.33 | 51.3% | 5.3% |

Two readings that matter:

- **Per-trade risk is the dominant variable, not the edge.** Holding PF at 2.0
  and moving risk from 1% to 2% collapses 12-month survival from 91.7% to
  **25%**. The viable configuration is *small risk, high frequency* — 0.5–1%
  per trade, 15–20+ trades/month.
- **The binding constraint is a sustained PF near 1.8–2.0.** At PF 1.33 only
  5.3% of paths both survive and hit the target. **hermes_agent's measured
  baseline PF is 1.05.** The gap between what exists and what these targets
  need is roughly a doubling of edge — and that gap, not risk sizing, is the
  real work.

**Recommendation:** the prop targets are arithmetically sound and not
fantastical, unlike the 4-year 3:1 benchmark. They are gated on demonstrating a
PF ~1.8 strategy first. Building the prop *harness* is cheap — the CBT backtest
template already implements breach tracking (max drawdown from initial, daily
loss from previous-day equity, phase targets, breach → halt), and
`config.yaml` already carries a `prop_firm` block. Building the *edge* is the
project.

---

## Scope decisions

**These belong in hermes_agent** (asks 2, 3 — after the step-5 gate is cleared):
buying BTC/ETH/top-25 at multi-year lows is a mean-reversion entry, which is the
opposite of the momentum entry the current baseline uses. It is a genuinely
different signal and worth testing — but it is a *step 6+ layer*, and step 5
says do not add layers yet. The 20% leverage/micro-cap sleeve also reverses
`leverage.enabled: false`, which was set deliberately because the evidenced
benefit of this strategy's core mechanism is drawdown reduction; that reversal
should be an explicit decision, not a side effect.

**These are new `/cbt:new` projects** (asks 1, 5, 6). Each needs its own
discovery, data and config:
- `fidelity_sleeves` — four sub-strategies with different mechanics
  (high-beta ≠ yield/income ≠ options ≠ macro hedge). Options in particular
  need chain data the repo does not have.
- `breakout_crypto_prop` — bull and bear regimes, `prop_firm.enabled: true`.
- `futures_prop` — futures/indices/commodities; no futures data in the repo yet.

Note `strategies/crypto_algo_trading` already has `prop_firm.enabled: true` and
DISCOVERY.md explicitly scoped the prop pool *out* of hermes_agent. Whatever
gets built for ask 5 should start from that, not from scratch.

---

## What I need from you

1. **The corrected capital figure.** state.yaml has carried
   `status: pending_correction` since you flagged the account totals were
   miscalculated. It does not block the build — it changes absolute dollar
   outcomes and where `min_position_value_usd` binds, not step order or any
   relative comparison — but every dollar figure in BASELINE_REPORT.md is
   built on $80,000 and will need re-running.
2. **The Fidelity balance.** Still unquantified; only per-position P&L was
   provided. Ask 1 cannot be sized without it.
3. **A decision on the benchmark window** (see ask 4). I would fix it to the
   backtest window and fetch a longer panel.
4. **Confirmation of Breakout's actual rules** — max drawdown %, whether it
   trails from high-water mark or initial balance, daily loss %, profit split.
   The Monte Carlo above assumes the harder variant; the numbers move a lot if
   it is measured from initial balance instead.
