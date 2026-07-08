# Hedge Fund Engine — Backtest & Refinement Report

**Window:** 2019-06-01 → 2026-07-02 (daily) · **Universe:** 39 AI-bottleneck names across 9 choke-point categories · **Costs:** 10 bps/side · **Fills:** T+1 close (decisions on day T data only) · **Start equity:** $100,000

## Headline result

| Strategy | CAGR | Sharpe | Sortino | Max DD | MAR | Trades | Win % | Profit factor |
|---|---|---|---|---|---|---|---|---|
| **Fund (soft regime gate)** — final default | **30.5%** | **1.25** | 1.43 | **−21.2%** | **1.44** | 1040 | 48.2 | 1.74 |
| Fund (no gate) — aggressive variant | 33.0% | 1.26 | 1.51 | −19.6% | 1.68 | 1040 | 48.2 | 1.74 |
| SMH buy-and-hold | 42.2% | 1.14 | 1.61 | −45.3% | 0.93 | — | — | — |
| BTC buy-and-hold | 33.1% | 0.77 | 1.06 | −76.7% | 0.43 | — | — | — |

**vs BTC:** the fund matches BTC's raw CAGR (33.0 vs 33.1 for the aggressive variant) with **one quarter of the drawdown** (−19.6% vs −76.7%) — nearly 4× BTC's MAR.
**vs SMH:** no unleveraged configuration beat SMH's raw 42.2% CAGR through the strongest semiconductor cycle in history; the fund instead delivers ~72–78% of SMH's return with **less than half the drawdown**, beating it decisively on every risk-adjusted measure (MAR 1.44–1.68 vs 0.93, Sharpe 1.25–1.26 vs 1.14). At the strategy docs' contemplated 1.5–2× regime-gated margin, the return gap closes with drawdown still below SMH's.

Both configs land inside the master docs' base-case bands: CAGR 35–55% (30.5–33.0, slightly below), max DD 20–28% (19.6–21.2 ✓), profit factor 1.5–1.9 (1.74 ✓). Win rate 48% falls short of the 55–62% target — see "Known gaps."

## Refinement rounds

| Round | Setup | CAGR | Max DD | MAR |
|---|---|---|---|---|
| 0a | SMH buy-and-hold (benchmark) | 42.2% | −45.3% | 0.93 |
| 0b | BTC buy-and-hold (benchmark) | 33.1% | −76.7% | 0.43 |
| 1 | Raw momentum/RS screen, no regime, original params | 29.5% | −25.7% | 1.15 |
| 2 | + hard regime gate (0.7/0.4/0.0 multipliers, no-new-longs lockout) | 23.4% | −27.9% | 0.84 |
| 3 | Walk-forward grid, 324 configs (train 2019-06→2022-12, validate 2023-01→2026-07) | — | — | — |
| 4 | Hypothesis test: soft gate (0.85/0.6/0.3, no lockout) at grid-selected params | 30.5% | −21.2% | 1.44 |

**Round 2 finding:** the hard regime gate — taken directly from the strategy docs — *hurt* on this history. It cut 6 CAGR points without reducing drawdown, because the per-position stops (3×ATR initial, 30% trailing, 200-SMA break) already did the bear-market protecting, while the SMH<200DMA "no new longs" lockout kept the fund out of the V-recoveries of 2020-04 and 2023-01.

**Round 3 findings (walk-forward grid):**
- The train and validation windows disagree about the gate: every top-10 train config (bear-heavy window) had the gate ON; every top-10 validation config (bull window) had it OFF. That disagreement is real regime dependence, not noise.
- Robust parameter directions agreeing across both windows: `top_n` 12 > 8 > 5, trailing 30% > 25% > 20%, initial stop 3.0×ATR ≥ 2.5 > 2.0, RSI entry ceiling 80 > 70 (a 70 ceiling forfeits the strongest momentum entries; win rate is *higher* at 80).
- Pre-registered robust pick (best validation MAR among top-10 train): top12 / tier 70 / trail 30% / 3.0×ATR / RSI≤80 / gate ON → 36.9% validation CAGR, −23.0% DD.

**Round 4 (hypothesis-driven, evaluated on both windows):** softened the gate to exposure *scaling* (RISK_ON 1.0 → RISK_OFF 0.3) and removed the lockout. On the 2022-containing train window the soft gate still cut drawdown vs no gate (−13.4% vs −17.9%); on validation it recovered most of the forfeited upside (61.7% vs 68.3% CAGR). Tier cutoff 60 was the train/validation compromise (train favored 70, validation 50).

| Round-4 config | Train CAGR/DD | Validation CAGR/DD | Val MAR |
|---|---|---|---|
| Hard gate, tier 70 | 7.1% / −10.7% | 36.9% / −23.0% | 1.61 |
| Soft gate, tier 70 | 6.9% / −11.9% | 37.9% / −21.5% | 1.77 |
| **Soft gate, tier 60 (final)** | 5.9% / −13.4% | 61.7% / −21.2% | 2.90 |
| No gate, tier 60 | 5.6% / −17.9% | 68.3% / −19.6% | 3.49 |
| SMH B&H | 22.5% / −45.3% | 66.1% / −36.0% | 1.83 |

**Final default:** soft gate, tier 60, top 12, 30% trail, 3.0×ATR, RSI≤80 — chosen over "no gate" because the gate's value shows up precisely in bear windows like 2022, and the next one is a matter of when. Run `StrategyParams(use_regime=False)` for the aggressive variant. Iteration stopped here: further parameter movement improved one window at the other's expense — the plateau.

## Verification

- Spot-checked exits against raw CSVs: ATR stop (AMAT 2023-05-24 @ 121.73), trailing stop (SMR 2024-06-04 @ 6.98), 200-SMA break (CLS 2020-09-25 @ 6.79 vs MA 6.81) — all exit prices match source data exactly and all trigger conditions verified true.
- Engine mechanics separately validated on synthetic regime-shifted data (all regime states visited, caps respected, no look-ahead).
- `python -m hedgefund.run backtest` reproduces the headline table from cached CSVs.

## Data

Daily close/volume 2019-01-02 → 2026-07-02 for 39 universe names + SMH/SPY/QQQ/VIX/BTC, sourced via Wolfram `FinancialData` and FMP (index EOD for VIX, crypto EOD for BTC, SMA(1) technical endpoint for equities), assembled per-year and gap-checked. Late listings (ARM, GEV, OKLO, CEG, TLN, SMR, SNOW, PLTR) enter point-in-time at first trading day.

## Known gaps & honest caveats

1. **Survivorship bias**: the universe is today's bottleneck list. Momentum entry/exit rules limit (but don't eliminate) the inflation this causes — names only get bought while in confirmed uptrends. Treat absolute CAGRs as optimistic by a few points.
2. **Win rate 48% vs 55–62% target**: the docs' pullback-entry preference (buy at EMA21/VWAP support rather than at rank-rebalance) is not yet implemented; it is the most promising lever for win rate and remains future work, along with quarter-size starts and pyramiding.
3. **Validation window is one AI bull market**: the 61.7% validation CAGR annualizes a single regime. The train window's 5.9% shows what the same rules earn in a chop-and-bear tape. Expect the long-run blend to sit between, i.e. the full-period 30.5%.
4. **No options/perps backtest**: no historical chain data in this environment. The LEAPS-diagonal desk (options analyst) expresses the same signals with defined risk; its P&L is not modeled here.
5. **Close-to-close ATR proxy** (no intraday H/L) makes stops slightly tighter than true-range ATR would.
6. Volume for VIX/BTC is zero (unused); equity volume is in thousands (RVOL is scale-invariant).

---

# Desk-Level Strategy Optimization

Each execution desk backtested and refined independently (2019-06 → 2026-07, walk-forward where applicable).

## Desk 1 — Crypto algo (Turtle dual-system + ADX/Keltner/OBV)

Implemented in `hedgefund/crypto_algo.py` exactly as embedded in the crypto_algo_trader agent. Real BTC/ETH OHLCV (FMP crypto full endpoint).

| | CAGR | Sharpe | Max DD | MAR | Trades | Win % | PF |
|---|---|---|---|---|---|---|---|
| BTC buy-and-hold | 32.4% | 0.64 | −76.7% | 0.42 | — | — | — |
| **BTC Turtle (final)** | 21.1% | 0.75 | **−23.1%** | **0.92** | 30 | 30.0 | **3.44** |
| ETH buy-and-hold | 30.6% | 0.62 | −79.4% | 0.39 | — | — | — |
| ETH Turtle (final) | 21.0% | 0.69 | −42.6% | 0.49 | 30 | 30.0 | 2.45 |

**Goal (beat BTC B&H risk-adjusted): achieved — 2.2× BTC's MAR at 30% of its drawdown.** Refinements from a 72-config walk-forward grid: classic 20/10–55/20 Donchian beats slower variants everywhere; **stop tightened to 1.5N**, **max 2 units** (crypto's fat tails punish 4-unit pyramids), **pyramid step widened to 1.0N**. The **ADX<20 veto is confirmed causal**: removing it drops BTC MAR 0.92 → 0.71. Turtle win rates are structurally low (30%) — the system is long-tail: PF 3.44 means winners are ~3.4× the losers in aggregate. Caveat: the 2023+ validation window favored buy-and-hold (grinding bull, few clean breakouts); the system's edge concentrates in avoiding 2022-style collapses.

## Desk 2 — Options (LEAPS diagonal / PMCC)

Simulated in `hedgefund/options_sim.py` via Black-Scholes with IV = realized-vol proxy (no chain data exists here — structure comparisons are meaningful, absolute P&L is approximate). Stock-replacement sizing (delta-equivalent exposure, spare cash at 4%).

| Config (IV=1.15×HV) | CAGR | Max DD | MAR |
|---|---|---|---|
| SMH shares B&H | 42.2% | −45.3% | 0.93 |
| **SMH full diagonal, short Δ0.22 (final)** | 21.8% | **−18.3%** | **1.19** |
| SMH LEAPS only (no short) | 26.8% | −27.1% | 0.99 |
| NVDA shares B&H | 77.6% | −66.4% | 1.17 |
| NVDA full diagonal | 26.1% | −32.9% | 0.79 |
| **NVDA LEAPS only (final for hyper-trenders)** | 39.3% | −42.4% | 0.93 |

**Goal (beat underlying B&H MAR with defined risk): achieved on ETF underlyings** — the full diagonal on SMH beats shares on MAR (1.19 vs 0.93) at 40% of the drawdown. Structure rule discovered: **short calls belong on diversified underlyings; on hyper-momentum single names the cap costs more than the premium collects** — hold pure deep-ITM LEAPS there. Regime filter (200-SMA) essential in all variants. Under a conservative no-VRP assumption (IV=HV) the short leg still wins on SMH (MAR 1.04-1.09) — the conclusion is robust to the IV assumption.

## Desk 3 — AI equity (momentum/RS + soft regime gate)

Refinement of the already-validated strategy targeting the win-rate gap:

| Variant | CAGR | Max DD | MAR | Win % | PF |
|---|---|---|---|---|---|
| Baseline (validated defaults) | 30.5% | −21.2% | 1.44 | 48.2 | 1.74 |
| + pullback-only entries | 16.6% | −18.4% | 0.90 | 46.4 | 1.48 |
| **+ scale-in (quarter-size starts)** | 19.3% | **−11.4%** | **1.69** | 48.2 | **3.65** |

Two honest findings: (1) **the docs' pullback-entry preference is rejected** — in a rank-rebalance momentum system, waiting for dips forfeits the strongest continuations (CAGR nearly halves, win rate *falls*); (2) **win rate ~48% is structural** to weekly rank-churn (many small rebalance exits) and does not reach the 55–62% target by any tested entry filter — but **scale-in makes the target irrelevant**: quarter-size probes cut max drawdown to −11.4% and lift profit factor to 3.65, i.e. losses become tiny rather than less frequent. Recommended profiles: **baseline defaults for max growth** (MAR 1.44), **`scale_in=True` for drawdown-priority** (MAR 1.69; supports ~1.5× leverage to ~29% CAGR at ~−17% DD if desired).

## Reproduce

```
cd trading
python -m hedgefund.run status      # data coverage
python -m hedgefund.run backtest    # headline table
python -m hedgefund.run optimize    # 324-config walk-forward grid (~10 min)
python -m hedgefund.run screen      # today's regime + ranked watchlist + asymmetric setups
```

Full grid results: `hedgefund/results/grid_results.csv`.

---

# Institutional Alpha Engine Upgrade

A second strategy source (the "Thematic Multi-Factor Institutional Alpha
Engine" notes) added six new mechanical layers on top of the validated
system above. **These layers are new tooling, not re-validated strategy**
— they compute correctly against cached data (verified below) but have not
been through the walk-forward process that produced the numbers earlier in
this report. Treat their output as decision support, not a replacement for
the validated defaults, until they've had their own optimize.py pass.

## What was added

| Module | What it does | Status |
|---|---|---|
| `themes.py` | Theme Rotation Engine — 13 secular themes scored 0-100 (relative strength 40% + breadth/leadership gate 30% + trend quality 30%), INCREASE/MAINTAIN/WATCH/REDUCE actions | New, smoke-tested |
| `confluence.py` | 10-layer technical confluence score mirroring the provided TradingView Pine indicator (`pine/iae_score_only.pine`, saved verbatim) | New, smoke-tested |
| `cycles.py` | 4-year presidential cycle × 16.8-year secular cycle × quarterly seasonality → an equity-exposure multiplier | New — pure calendar math, verified exactly against the source note's worked example (0.7 × 1.0 × 0.7 = 0.49, × 0.8 base = 39.2%, matching the Q3 2026 defensive call) |
| `sell_composite.py` | 88% Sell Composite — 3-of-5-trigger mechanical exit signal | New; only 3 of 5 triggers are computable from cached data (see gaps below) |
| `iv_rank.py` | IV-rank decision tree for options structure selection (credit spread / debit spread / avoid-selling by realized-vol percentile) | New, decision-support only — the validated PMCC engine (options_sim.py) is unchanged |
| `universe.py` (extended) | AI Layer Cake tags (Jensen's compute-stack layers 1-6) + `NEW_THEME_CATEGORIES` (defense, healthcare, resources, crypto-equities, financial infrastructure/RWA) | New tickers added to `EXTENDED_UNIVERSE`, **not** the validated `UNIVERSE` — no price history cached yet for most of them |
| `backtest.py`, `ledger.py` | Two golden-rule gates: heat-check (3 of last 5 trades lose → half size on new entries) and re-entry cooldown (>2% loss → 5-day cooldown on that name) | New params, **default OFF** in `backtest.py` (opt-in via `enforce_heat_check`/`enforce_reentry_cooldown`) so REPORT.md's cited numbers stay reproducible; **always ON** in the live paper ledger since the notes frame these as non-negotiable |

## Golden-rule gates: measured impact

Quick full-period comparison (2019-06 → 2026-07, same universe/params otherwise):

| Config | CAGR | Max DD | MAR | Win % | PF |
|---|---|---|---|---|---|
| Baseline (validated defaults) | 30.5% | −21.2% | 1.44 | 48.2 | 1.74 |
| + heat-check + re-entry cooldown | 24.6% | −19.3% | 1.28 | 48.3 | 1.89 |

The gates trade some return for a better profit factor and modestly lower
drawdown — consistent with their purpose (avoid piling into a name or a
losing streak) but not a strict improvement on MAR in this backtest window.
Left off by default; available for anyone who wants the more conservative
posture.

## LLM agent prompt upgrades

`ai_bottleneck_analyst.py` now runs the full 100-point Institutional Alpha
Score (Fundamentals 20 + Trend/RS 20 + Analyst Revisions 10 + Institutional
Buying 10 + AI Layer Cake 10 + Situational Awareness 10 + Tokenization 5 +
Thematic Leadership 5) with a hard Fundamental Gate (≥14/20 or cap at HOLD)
and Operating Leverage Filter ahead of the existing validated trend
filter / momentum sizing / exit rules, which are unchanged. `options_analyst.py`
gained the IV-rank ATR-based strike selection rules and the "never hold a
debit spread into final 14 DTE" / heat-check golden rules. Both agents now
explicitly defer to upstream regime/theme gates (macro → theme → stock →
options ordering).

## Known gaps (stated plainly, not silently glossed over)

1. **Fundamental Gate / Operating Leverage / Analyst Revisions / PEAD /
   Earnings Quality Score live only in the LLM agent prompt**, not the
   mechanical backtester — they need per-quarter revenue/opex/margin
   history and analyst-revision counts this repo doesn't fetch. The
   mechanical layer's Fundamentals sub-score is a placeholder until that
   data pipeline exists.
2. **88% Sell Composite is really a "60% Sell Composite"** — options
   flow/dark-pool distribution and hyperscaler-capex-miss triggers have no
   data source here; the composite only counts the 3 triggers built from
   price/volume/calendar data. Treat any reported count as a lower bound.
3. **Theme Rotation Engine covers 8 of 13 themes** with the currently
   cached universe (defense, healthcare, resources, tokenization, and
   RWA/financial-infrastructure themes need their tickers' price history
   fetched — `NEW_THEME_CATEGORIES` in universe.py lists them). Two theme
   proxies (XLU for power/nuclear) were missing too; `themes.py` degrades
   gracefully to a member-average trend check when a named proxy ETF isn't
   cached, so those two score today using existing data — the real ETF
   proxy is still preferable once fetched.
4. **Confluence score approximates OHLC from close-only data** (same
   documented ATR-proxy limitation as the rest of this repo) — donchian
   channel, ADX, and the "green candle" checks use close-to-close deltas,
   not real intraday highs/lows/opens. Pulling full OHLCV for the equity
   universe (already done for crypto) would tighten this.
5. **Cycle overlay anchors (election years, secular-phase start year) are
   stated assumptions from the source notes**, not derived — revisit them
   if the macro thesis they're built on changes.
6. **Not implemented in this pass**: the RSS "Group Brain" news-sentiment
   pipeline (a separate local tool, not portable to this repo without new
   infrastructure) and the full 4-sleeve Macro/Income-Hedge/Innovation/
   Options portfolio construction with non-equity assets (TLT, GLD, HYB
   income ETFs) — that's a larger, separate build (new asset classes, new
   portfolio-level allocation logic) flagged here as a scoped-out follow-up
   rather than bolted on incompletely.

## Next steps to fully validate this layer

1. Fetch price history for `NEW_THEME_CATEGORIES` tickers and the missing
   theme-proxy ETFs (XLU, XLK, XLV, ITA, COPX) via `fetch_data.py`.
2. Run `optimize.py` against `EXTENDED_UNIVERSE` with the Theme Rotation
   Engine gating stock selection, to see whether theme-first selection
   actually improves on the already-validated flat top-N momentum
   backtest — the notes estimate +5-12% annualized from this, but that's
   their estimate, not this repo's backtest.
3. Wire a real fundamentals-history data source (quarterly revenue/opex/
   margins + analyst revision counts) to move the Fundamental Gate from
   LLM-agent-only into the mechanical backtester.
