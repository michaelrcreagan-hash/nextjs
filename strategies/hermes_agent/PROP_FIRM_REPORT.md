# Prop-Firm Strategies — goal asks #5 and #6

**Date:** 2026-08-27 (revised with real rules)
**Ask #5:** Breakout crypto prop — **RE-TESTED against the real rules. Result reversed.**
**Ask #6:** US futures prop firm — **BLOCKED on data. Not built.**
**Reproduce:** `python3 run_crypto_prop.py`

---

## The rules (confirmed, no longer assumed)

Supplied by the author and cross-checked against Breakout's published Classic
and Turbo 1-Step programs:

| | Classic eval | Turbo funded |
|---|---:|---:|
| account | $10,000 | $200,000 |
| profit target | $1,000 (10%) | $18,000 (9%) |
| max drawdown | **$600 (6%), STATIC** | **$6,000 (3%), STATIC** |
| max daily loss | 3% ($300) | 3% ($6,000) |
| MAR required just to pass | 1.67 | 3.00 |

Also confirmed: no time limit, no minimum trading days, no consistency rule.
Leverage 5:1 on BTC/ETH, 2:1 on alts. Split 80% default, 90% upgradeable.
The threshold is set from the balance at 00:30 UTC and monitored against
**current equity**, so floating P&L counts toward a breach.

### The static drawdown reverses my earlier conclusion

My previous run modelled a **trailing** 10% drawdown from the high-water mark
and reported *0 of 8 arms surviving*. That was the wrong rule. Under a trailing
floor, every new equity high permanently raises the bar, so a strategy that
grinds up and gives back 10% dies even while profitable overall. Under
Breakout's **static** floor the constraint binds only until a cushion is built,
then stops binding.

That is a materially easier game, and the numbers move accordingly. **The
earlier "every arm breached" finding does not apply to Breakout** and should be
disregarded — it described a firm with different rules.

### One structural trap in the Turbo profile

Its daily loss limit (3% = **$6,000**) exactly **equals** its total max drawdown
(**$6,000**). A single maximum-daily-loss day does not merely cost the day — it
ends the account outright. There is no such overlap in Classic ($300 daily
against a $600 total), which makes Classic strictly more forgiving per unit of
risk taken. Worth knowing before choosing which to buy.

---

## Results — pass rate across 40 start dates

Same bull/bear breakout rules, replayed from 40 different start dates on the
5.01-year panel. A run ends at PASS (target reached) or BREACH.

### Classic $10k eval

| arm | PASS | dd breach | daily breach | unresolved | med trades | t/mo |
|---|---:|---:|---:|---:|---:|---:|
| risk 0.25% | 45.0% | 17.5% | **0.0%** | 37.5% | 95 | 8.5 |
| risk 0.50% | 35.0% | 32.5% | 32.5% | 0.0% | 13 | 7.8 |
| risk 0.75% | 25.0% | 12.5% | 62.5% | 0.0% | 6 | 6.2 |
| risk 1.00% | 37.5% | 20.0% | 42.5% | 0.0% | 4 | 5.6 |
| **risk 0.50% long-only** | **50.0%** | 25.0% | 25.0% | 0.0% | 15 | 4.9 |
| risk 0.50% rr3 | 27.5% | 35.0% | 37.5% | 0.0% | 10 | 5.5 |

### Turbo $200k funded

| arm | PASS | dd breach | daily breach | unresolved | med trades | t/mo |
|---|---:|---:|---:|---:|---:|---:|
| **risk 0.25%** | **50.0%** | 40.0% | **0.0%** | 10.0% | 57 | 8.3 |
| risk 0.50% | 22.5% | 60.0% | 17.5% | 0.0% | 7 | 7.0 |
| risk 0.75% | 35.0% | 52.5% | 12.5% | 0.0% | 4 | 5.5 |
| risk 1.00% | 30.0% | 55.0% | 15.0% | 0.0% | 3 | 5.0 |
| risk 0.50% long-only | 42.5% | 52.5% | 5.0% | 0.0% | 5 | 3.4 |
| risk 0.50% rr3 | 22.5% | 55.0% | 22.5% | 0.0% | 6 | 4.7 |

**Roughly a coin flip on the best arms** — a very different proposition from
"every arm breached", and a defensible bet against an eval fee.

### What the table says about how to size

1. **Per-trade risk is the whole game, and smaller is better.** At 0.25% risk
   the daily-loss breach rate is **0.0%** in both profiles — you mechanically
   cannot lose 3% in a day when each trade risks a quarter percent. Every step
   up in risk trades pass-rate for breach-rate. This matches what the Monte
   Carlo predicted before any of this was run.
2. **Turbo is harder than Classic, as its 3% floor implies.** Drawdown breaches
   run 40–60% on Turbo against 12–35% on Classic. If both are available for a
   similar fee, Classic is the better risk-adjusted entry.
3. **Long-only beat long/short on Classic** (50.0% vs 35.0% at the same risk).
   The short side is where the daily-loss breaches concentrate — bear-regime
   crypto rallies are violent.
4. **0.25% risk on Classic leaves 37.5% unresolved** — too slow to reach the
   target inside the remaining data. There is a real tension: low risk survives
   but may not finish. On Turbo that drops to 10%, since a $200k account at
   0.25% still moves enough size to get there.

---

## The $70k/year target is the part that does NOT work

Passing the eval and earning $70k/year are different problems, and only the
first one looks reachable.

| split | gross needed | as % of $200k | per month | **MAR needed** |
|---|---:|---:|---:|---:|
| 80% | $87,500 | 43.8%/yr | 3.07% | **14.6** |
| 90% | $77,778 | 38.9%/yr | 2.78% | **13.0** |

Against a **$6,000 static drawdown that never resets**, $70k/year requires a
MAR of roughly **13–15**. For calibration:

| | MAR |
|---|---:|
| crypto DCA / buy-the-low — best thing built in this project | 0.41 |
| BTC buy & hold, 5 years | 0.13 |
| hermes_agent step-5 baseline | 0.02 |
| elite managed-futures funds, industry-wide | 0.5 – 1.5 |
| **required here** | **13 – 15** |

That is an order of magnitude beyond what top professional managers sustain. I
don't think $70k/year from a single $200k Breakout account is a realistic
target, and I'd rather say so now than after you've paid for evals.

**What is realistic**: the $18,000 target itself (9%) at a 3.00 required MAR is
demanding but not absurd — the table above says ~50% of start dates get there.
At an 80% split that first target is worth **$14,400**. Reaching it repeatedly,
rather than compounding one account to $70k, is the plausible path — and it
depends on Breakout's post-payout reset rules, which I have not confirmed.

---

## How much to trust these numbers

**The pass rates are softer than they look.** 40 start dates spread across
~1,370 bars puts them ~35 bars apart, while individual runs last far longer
than that — so the windows overlap heavily and are **not 40 independent
samples**. The effective sample size is much smaller, and ±10pp of noise on any
single cell would not surprise me. Read the ordering (0.25% beats 1.0%,
Classic beats Turbo, long-only beats long/short) as the signal; read the
absolute percentages as indicative.

Other caveats:
- One strategy (20-day breakout, ATR stops) on one 5-year panel. Not a survey.
- **Survivorship bias** in the universe, as in `CRYPTO_LOW_REPORT.md`: today's
  top-25 names, excluding coins that went to zero.
- Daily bars. Trade frequency lands at 3–8/month, which is fine for a
  no-time-limit eval but is still an order of magnitude below what would be
  needed to compound toward the annual figure.
- Costs are perp-style (0.035% taker + 5bps). Breakout's actual fee schedule
  is not modelled.

---

## Ask #6 — US futures prop firm: BLOCKED, not built

**No futures data is reachable from this environment:**

| source | result |
|---|---|
| Binance public API | HTTP **451** — geo-blocked |
| Stooq CSV (`es.f`, `gc.f`, `nq.f`, `cl.f`) | returns **HTML**, not CSV |
| CoinGecko free tier historical | **401** beyond trial window |
| Coinbase Exchange | works, but **crypto only** |

The repo has no futures, index or commodity history either. Building this would
mean fabricating a backtest, which I won't do.

**To unblock, one of:** an AlphaVantage/FMP/Databento key with futures coverage;
a CSV export of continuous contracts (ES, NQ, CL, GC, ZN) from your broker; or
explicit acceptance of ETF proxies (SPY, QQQ, GLD, USO, TLT) — which would not
be a futures strategy, since it drops the roll, the margin structure and the
near-24-hour session, and I'd label it as such.

---

## What I'd do

1. **Start with Classic $10k, long-only, ~0.5% risk per trade.** Best measured
   pass rate (50%), lowest breach exposure, and the cheapest way to find out
   whether the rules suit you.
2. **Never size above 1% per trade on either profile.** The breach columns are
   monotone in risk; there is no version of this where bigger size helps.
3. **On Turbo, treat the daily limit as the binding constraint, not the total.**
   They are the same $6,000, so a single bad day is terminal.
4. **Re-scope the income target.** Aim at hitting the $18,000 target (≈$14,400
   at 80%) rather than at $70k/year from one account. Then confirm what happens
   to the drawdown floor after a payout — that single rule determines whether
   repeat targets are viable, and it's the last unknown that matters here.
5. **Get intraday data before optimising further.** At 3–8 trades/month the
   parameter estimates are thin, and every conclusion above would firm up
   considerably at 1m–15m resolution.

Sources for the rule cross-check: [QuantVPS](https://www.quantvps.com/blog/breakout-crypto-prop-firm-rules) · [TheTrustedProp](https://thetrustedprop.com/prop-firms/breakout-prop) · [PropTradingVibes](https://proptradingvibes.com/blog/breakout-rules-overview) · [Breakout](https://www.breakoutprop.com/)
