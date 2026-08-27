# Crypto "Buy the 4-Year Low" — goal asks #2, #3, #4

**Date:** 2026-08-27
**Data:** `Data/crypto_panel_5y.csv` — **1,831 daily bars, 25 names, 2021-08-23 → 2026-08-27 (5.01 years)**, Coinbase Exchange
**Reproduce:** `python3 fetch_crypto_panel.py && python3 run_crypto_low.py`
**Costs:** Coinbase spot, 0.60% taker + 10bps slippage — the author's actual venue

The 4-year-window blocker is gone. The old panel was 2.09 years of weekday-only
data with no altcoins; this one is 5.01 years of true 7-day crypto bars across
the top 25 tradeable names, so ask #2's rule and ask #4's benchmark are both
testable for the first time.

---

## Results

| arm | CAGR | total | max DD | MAR | Sharpe | buys | final $ |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC buy & hold | 9.86% | 60.1% | −76.67% | 0.13 | 0.44 | — | 160,148 |
| equal-weight 25, lump sum | **−5.34%** | −24.0% | −77.08% | −0.07 | 0.28 | — | 75,965 |
| **DCA control (no signal)** | **22.48%** | — | −56.16% | 0.40 | — | 70 | — |
| **best low-buying arm** (365d low, within 20%) | **23.40%** | 186.8% | −56.95% | 0.41 | 0.69 | 70 | 286,796 |

Full 16-arm grid in `experiments/crypto_low/results.json`.

---

## Finding 1 — the "buy the low" signal is worth ≈ nothing

This is the result that matters, and it only shows up because the control was run.

| | CAGR | max DD | MAR | buys |
|---|---:|---:|---:|---:|
| best low-buying arm | 23.40% | −56.95% | 0.41 | 70 |
| **DCA control — same universe, same 80/20 split, same costs, no signal** | 22.48% | −56.16% | 0.40 | 70 |
| **edge from the signal** | **+0.92pp** | −0.79pp | +0.01 | — |

**+0.92pp of CAGR, from the best of 16 trials, on a single 5-year sample.**
That is inside the noise. The drawdown is slightly *worse* and the MAR is
identical. The honest reading: what produced the 23% CAGR is **the universe and
the staged deployment schedule** — not buying the 4-year low.

Corroborating evidence inside the grid: at 20% proximity, all four lookback
windows (365d/730d/1095d/1460d) return **identical** results — 70 buys,
23.40% CAGR, same final dollar. When the lookback stops mattering, the signal
has stopped binding, and the arm has quietly become dollar-cost averaging with
extra steps. That the *best* arm is the one where the signal does the least is
the tell.

---

## Finding 2 — staged deployment, not stock-picking, did the work

The three crypto arms differ only in *when* capital entered:

| | CAGR |
|---|---:|
| equal-weight 25, **lump sum** on day 1 | −5.34% |
| same 25 names, **deployed in tranches** | +22.48% |

A 28-point spread from timing alone, on an identical basket. The mechanism is
cash drag working in reverse: the panel starts 2021-08-23, near a cycle top, so
anything holding cash through the 2022 drawdown bought lower and won.

**This is real but it is start-date dependent, and I would not extrapolate it.**
A panel starting at the 2022 bottom would likely reverse the ranking — lump sum
would win and DCA would lag. What the test actually establishes is that *lump-sum
entry into crypto at a cycle top is punishing*, which is not a tradeable edge so
much as a warning about deployment timing. One 5-year window cannot separate
"staged entry is better" from "this particular window started at a top."

---

## Finding 3 — the 3:1 gate depends entirely on which reading you meant

| reading | calculation | result | vs 3.0× |
|---|---|---:|---|
| **terminal wealth** | $286,796 / $160,148 | **1.79×** | ❌ FAIL |
| **total return** | 186.8% / 60.1% | **3.11×** | ✅ PASS |

These are both defensible readings of *"outperform btc by a more than 3 to 1
multiple"* and they give opposite verdicts. The difference is whether the
starting capital is counted in the multiple.

I would use the **total-return reading** — "made 3× the profit BTC made" is the
more natural sense of outperforming by 3:1, and it's the one the strategy
clears at 3.11×. But that should be your call rather than mine, because it
decides whether ask #4 is already satisfied or still open. **Say which you meant
and I'll hold the target to it.**

Note also that the earlier projection in `GOAL_RECONCILIATION.md` — that 3:1
over four years implies a 60–68% CAGR — assumed BTC compounding at its
historical 30–35%. Over this actual 5-year window BTC returned **9.86% CAGR**,
so the bar landed far lower than the projection. The benchmark is not
scale-free, exactly as flagged: it was easy here because BTC was weak.

---

## Finding 4 — "top 25 by market cap" literally includes 8 stablecoins

Live top-30 by market cap includes USDT, USDC, USDS, DAI, USD1, USDE, USDG
(stablecoins) plus WBT and LEO (exchange tokens). A stablecoin has no trend to
be at a 4-year low against; including them would park roughly a third of the
sleeve in cash while reporting it as an allocation.

`fetch_crypto_panel.py` filters them and takes the top 25 *tradeable* names
instead. That is an interpretation of the ask, stated rather than buried.

---

## The caveat that outranks every number above

**Survivorship bias, and it bites this strategy hardest.**

The universe is the top names **as of today**. That excludes every coin that was
top-25 in 2021 and then collapsed — LUNA, FTT, and others that went to
approximately zero. "Buy the multi-year low and hold spot" is *precisely* the
rule that would have bought those all the way down and never sold.

So the +23.4% is an **optimistic upper bound, not an estimate**, and the bias is
concentrated in exactly the mechanism under test. Fixing it requires a
point-in-time market-cap universe — a paid data product, and the single highest-
value data purchase available to this project.

Secondary caveats:
- **16 trials.** Any Sharpe here must be deflated against n=16, not n=1.
- **Ask #3 is implemented as a 20% capital split, not leverage.** `config.yaml`
  sets `leverage.enabled: false`, and levering a survivorship-biased buy-the-low
  rule would compound the bias rather than test it. Micro-caps are not in the
  panel at all — Coinbase does not list them — so the satellite sleeve is
  currently "smaller top-25 names", not true micro-caps.
- **No exits.** This is spot accumulation, as the ask specifies. The −57%
  drawdown is fully worn.

---

## What I'd conclude

1. **Drop "buy the 4-year low" as a signal.** It does not beat scheduled
   accumulation into the same basket. Keep the basket and the staged entry,
   which is where the return came from, and stop paying attention to the low.
2. **The strategy does beat BTC** — 23.4% vs 9.86% CAGR, −57% vs −77% drawdown,
   MAR 0.41 vs 0.13. That holds on both the signal arm and the control, so it
   survives the finding above. It is the one place in this project where
   something clearly outperforms the benchmark.
3. **Buy a point-in-time universe before trusting any of it.** Everything here
   is an upper bound until the dead coins are back in the sample.
4. **Tell me which 3:1 reading you meant** — it is the difference between ask #4
   being met (3.11×) and missed (1.79×).
