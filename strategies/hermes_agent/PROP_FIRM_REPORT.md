# Prop-Firm Strategies — goal asks #5 and #6

**Date:** 2026-08-27
**Ask #5:** Breakout prop firm, bull + bear crypto — **BUILT AND TESTED. Every arm failed.**
**Ask #6:** US futures prop firm — **BLOCKED on data. Not built.**
**Target:** $70k/yr; 4%+/month on each $100k account
**Reproduce:** `python3 run_crypto_prop.py`

---

## Ask #5 — Breakout crypto prop: 0 of 8 arms survived

Bull/bear breakout on the 5.01-year, 25-name Coinbase panel. Regime from BTC's
50/200-day MAs: **bull 33.6%, bear 29.3%, neutral 37.1%** of bars. Perp-style
costs (0.035% taker + 5bps), from `config.yaml`'s Hyperliquid figures.

| arm | CAGR | max DD | PF | trades | **t/mo** | win% | med month | halted |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| bull+bear risk 0.5% | 1.07% | −10.99% | 1.12 | 106 | 1.8 | 36.8% | 0.00% | max DD 2023-08-29 |
| bull+bear risk 0.75% | 1.14% | −10.46% | 1.35 | 30 | 0.5 | 43.3% | 0.00% | max DD 2022-09-09 |
| bull+bear risk 1.0% | −0.76% | −9.39% | 0.70 | 13 | 0.2 | 30.8% | 0.00% | daily loss 2022-05-04 |
| bull+bear risk 2.0% | −1.44% | −11.51% | 0.00 | 3 | 0.0 | 0.0% | 0.00% | max DD 2022-03-19 |
| BULL ONLY risk 0.75% | 1.02% | −7.29% | **1.49** | 16 | 0.3 | 43.8% | 0.00% | daily loss 2023-02-09 |
| bull+bear 10d breakout | 1.22% | −10.04% | 1.39 | 29 | 0.5 | 44.8% | 0.00% | max DD 2022-08-07 |
| bull+bear 40d breakout | 0.91% | −11.10% | 1.23 | 34 | 0.6 | 41.2% | 0.00% | max DD 2022-09-03 |
| bull+bear R:R 3.0 | **4.87%** | −10.89% | 1.42 | 79 | 1.3 | 34.2% | 0.00% | max DD 2024-03-19 |

**Every arm breached. The longest survivor lasted to March 2024 — two and a
half years into a five-year window.**

### Why it failed — frequency, not edge

`GOAL_RECONCILIATION.md`'s Monte Carlo established what 4%/month needs:
**PF 1.8–2.0 at 15–20+ trades/month, 0.5–1.0% risk per trade.** Measured:

| | required | achieved | gap |
|---|---:|---:|---|
| profit factor | 1.8–2.0 | 0.70 – **1.49** | short |
| **trades / month** | **15–20+** | **0.0 – 1.8** | **10–50× short** |
| median monthly return | ≥ 4.0% | **0.00%** | — |

The profit-factor gap is real but modest — 1.49 against a 1.8 bar. **The
frequency gap is two orders of magnitude**, and it is the binding one. A median
monthly return of exactly 0.00% across every arm means *most months contain no
trades at all*. You cannot compound 4% a month in months where you do not trade.

The root cause is structural, not a tuning problem: **a 20-day breakout on
daily bars across 25 names, gated by a regime that is neutral 37% of the time,
cannot mechanically produce 15–20 trades a month.** Widening the breakout
(10d vs 40d) barely moved the count — 0.5 vs 0.6/month. Cutting risk to 0.5%
raised trades to 1.8/month but dropped PF to 1.12 and still breached.

### What would actually be needed

1. **Intraday data — hourly or 15-minute.** This is the single blocking
   requirement. Daily bars cannot generate prop-account trade frequency at any
   parameter setting. Everything else is secondary until this is fixed.
2. Once intraday: re-test the same bull/bear structure. The PF of 1.49 on the
   bull-only arm is not far off the 1.8 bar and might clear it with more
   samples and a tighter regime filter.
3. **The trailing drawdown is what kills these accounts, not the losses.**
   Six of eight arms died on max drawdown rather than daily loss. Under a
   trailing-from-high-water-mark rule, every new equity high raises the floor,
   so a strategy that grinds up and then gives back 10% is dead even while
   profitable overall. The R:R 3.0 arm made 4.87% CAGR and *still* breached.

### One caveat that cuts the other way

Prop rules here are **assumed, not confirmed** — I modelled the harder variant
(10% trailing from high-water mark). If Breakout measures drawdown from the
**initial balance** instead, the floor stops rising as the account grows and
survival improves materially. That would not fix the frequency problem, but it
would change which arms died and when. **This is the fourth time I've flagged
needing Breakout's actual rule set** — it is now the cheapest unblock available.

---

## Ask #6 — US futures prop firm: BLOCKED, not built

Requested: futures, indices and commodities for a second $100k prop account at
a US futures firm.

**No futures data is reachable from this environment.** Attempts made:

| source | result |
|---|---|
| Binance public API | HTTP **451** — geo-blocked |
| Stooq CSV (`es.f`, `gc.f`, `nq.f`, `cl.f`) | returns **HTML**, not CSV — blocked/rate-limited |
| CoinGecko free tier historical | **401** beyond trial window |
| Coinbase Exchange | works, but **crypto only** |

The repo contains no futures, index or commodity price history either. Building
this ask would mean fabricating a backtest, which I won't do.

**To unblock, one of:**
- an AlphaVantage / FMP / Databento key with futures coverage (the MCP
  connectors for these exist in this session but were cycling and unreliable);
- a CSV export of continuous futures contracts (ES, NQ, CL, GC, ZN) from any
  broker or data vendor;
- accepting liquid ETF proxies (SPY, QQQ, GLD, USO, TLT) instead of true
  futures — a real approximation, since it drops the contract roll, the margin
  structure, and the near-24-hour session that a futures prop strategy depends
  on. Worth saying plainly: an ETF-proxy backtest would not be a futures
  strategy, and I'd label it as such.

**The frequency finding from ask #5 applies here in advance.** Whatever data
arrives, if it is daily bars the same 15–20 trades/month wall will be hit.
Futures prop accounts are traded intraday for exactly this reason. **Request
intraday data (1m–15m) for both prop asks, not daily.**

---

## Where the two prop asks stand against $70k/year

The $70k target itself remains arithmetically sound — 4%/month compounds to
60.1%/year, $120k gross across two accounts, comfortably inside an 80/20 split.
Nothing is wrong with the goal's own math.

What the testing establishes is the distance to it:

- **Crypto prop (ask #5): built, tested, does not work on daily bars.** The
  edge gap is modest (PF 1.49 vs 1.8); the frequency gap is 10–50×. Needs
  intraday data before it can be honestly re-tested.
- **Futures prop (ask #6): cannot be started without data.**

Neither is close today. Both are blocked on the same thing — **intraday price
history** — which makes that the single highest-value unblock for this half of
the goal, ahead of any further parameter work.
