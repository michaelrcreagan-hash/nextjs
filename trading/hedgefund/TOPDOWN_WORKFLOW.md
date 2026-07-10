# The Top-Down Workflow — from macro read to placed trade

*One document tying together everything in `trading/` and `strategies/`:
the research, the backtests, the optimized parameters, and the live
pipeline. The runnable version of this document is
`python -m hedgefund.run topdown` (daily automated via
`.github/workflows/hedgefund-daily.yml`; output lands in
`trading/hedgefund/reports/topdown-YYYY-MM-DD.md` and
`state/topdown.json`).*

---

## The cascade

```
L1 MACRO ──> L2 ALLOCATION ──> L3 THEMES ──> L4 STOCKS ──> L5 SPOT SETUP
                                                     └────> L6 OPTIONS
L7 HEDGES & EXITS wrap around everything
```

Decision order is never reversed (golden rule #1). Each layer can only
narrow what the layer above allowed.

---

## L1 — Macro Desk (`regime.py`, `cycles.py`)

**Inputs:** VIX level/trend, SMH vs 50/200-DMA, universe breadth
(% above 200-DMA), BTC trend (liquidity proxy).
**Outputs:** RISK_ON / MIXED / CAUTION / RISK_OFF + gross-exposure
multiplier + two kill switches (VIX>30 → RISK_OFF 48h;
SMH<200DMA → no new longs).

Overlaid with the deterministic cycle model (4-yr presidential ×
16.8-yr secular × quarterly seasonal). **Validated role:** risk
reducer — cut max drawdown 3.5-3.7pp in both backtest eras at ~zero
CAGR cost (SLEEVE_BACKTEST_REPORT §2.2). It scales exposure; it never
adds leverage.

*Evidence:* regime ablation in `monte_carlo/sleeve_analysis.py`;
presidential-cycle literature in
`strategies/four_sleeve_portfolio/RESEARCH.md` §Sleeve-1.

## L2 — Allocation (`sleeves.py`, optimized parameters)

The four-sleeve matrix (from `notes/four_sleeve_portfolio_architecture.md`
Part 10) maps the regime state to sleeve weights, then the cycle
multiplier scales the equity sleeves (cash absorbs the rest — never
leverage). The **adopted optimized configuration**
(`strategies/four_sleeve_portfolio/config.yaml`, OPTIMIZATION_REPORT.md):

| Knob | Value | Why |
|---|---|---|
| Macro sleeve trend gate | OFF | gate whipsawed (-2.8 CAGR 2023-26); inverse-vol across all members is rank-stable IS and OOS |
| Income variant | "both" | halve TLT below its 200DMA; shift half of TLT→GLD when 126d stock-bond corr > 0 (defends 2022-style shocks) |
| Innovation selection | 63d momentum, top 4 | best OOS in every comparison |
| Innovation crash guard | 0.35 vol target | Daniel-Moskowitz dynamic momentum; ~equal MAR, 9pts less vol |

**Validated result:** 41.3% CAGR / -9.5% maxDD (2023-26) and
9.8% / -17.4% (2010-23) — better than baseline on both axes in both eras.

## L3 — Theme Desk (`themes.py`)

13 secular themes scored 0-100 (relative strength 40% / breadth 30% /
trend quality 30%) → INCREASE (≥90) / MAINTAIN (≥80) / WATCH (≥70) /
REDUCE. **Funnel rule:** REDUCE themes block new entries; WATCH themes
demand Gold+ conviction; INCREASE/MAINTAIN allow Silver+.

## L4 — Stock Desk (`signals.py` + `confluence.py` + `revision_velocity.py`)

Three lenses on every candidate:
1. **Conviction score (0-100)** — walk-forward-validated composite
   (RS vs SMH+SPY, trend gate, EMA stack, RSI band, MACD, RVOL,
   52w-high proximity) with Platinum/Gold/Silver/Bronze tiers, plus the
   asymmetric-setup flag (vol squeeze + intact trend + near highs).
2. **Technical confluence (0-100)** — the Pine "IAE" indicator ported
   (close-only approximations; <40 hard-blocks).
3. **Analyst revision velocity** — decay-weighted upgrade/downgrade
   flow (`/revisions` page; needs FMP key or Yahoo reachability —
   degrades to "—" offline).

The LLM agent layer (`trading/tradingagents/`, Omega strategy context,
knowledge-brain orchestrator, 100-pt Institutional Alpha Score with the
fundamental gate) is the deep-dive on top of this mechanical screen —
run via `python -m hedgefund.run daily --deep-dive`.

## L5 — Spot Trade Setup (validated rules from `backtest.py`/REPORT.md)

For every funnel-qualified name the live update prints a complete plan:
- **Entry:** at market on breakout/asymmetric names near 52w highs;
  otherwise a pullback zone of EMA21 ± 0.5×ATR.
- **Stop:** entry − 2.5×ATR (walk-forward validated).
- **Target:** 2R (entry + 5×ATR), then a 25% trailing stop.
- **Size:** risk 1% of equity × regime multiplier; **quarter-size
  starter**, full only on follow-through; 12% single-name cap.

## L6 — Options Desk (`iv_rank.py`, `options_sim.py`)

- **Core:** SMH PMCC / LEAPS diagonal (0.75-0.80Δ LEAPS 12-24m; short
  30-45 DTE at 0.22Δ — the grid-search optimum, broad and stable).
  Regime break (SMH<200DMA) closes the book. Skip the short leg on
  hyper-momentum single names.
- **Satellites per candidate:** HV-rank decision tree — >60% sell a
  credit spread (short 1.5×ATR / long 2.0×ATR); 30-60% debit spread
  (long 1.0×ATR / short 2.0×ATR); <30% avoid selling. Defined risk
  only; close by 14 DTE; 2% max risk per spread.

## L7 — Hedge Desk & Exits (`sleeves.py` income variant, `sell_composite.py`)

- **Macro hedges:** the income sleeve IS the hedge book — TLT (duration,
  halved when TLT<200DMA), GLD (expands when stock-bond correlation
  flips positive), PFF (carry), GDXJ (in MIXED). Regime state sets its
  size (15% RISK_ON → 50% RISK_OFF).
- **Portfolio stop:** -20% from peak → equity sleeves to ~30%, release
  at -10% (backtests show the regime matrix usually de-risks first —
  the stop bound zero times in 16 years; it's tail insurance).
- **Position exits:** 88% Sell Composite (3 measurable triggers: RSI>80
  w/ declining volume, RVOL failure near highs, OpEx-week RSI>72) —
  3+ → scale out 50%, 4+ → full exit; plus the secular invalidation
  check (SPY >20% below 200DMA).

---

## Where everything lives

| Layer | Mechanical module | Research / validation |
|---|---|---|
| Macro | `hedgefund/regime.py`, `cycles.py` | REPORT.md, SLEEVE_BACKTEST_REPORT §2.1-2.2 |
| Allocation | `hedgefund/sleeves.py` | OPTIMIZATION_REPORT.md, sleeve_optimize_results.json |
| Themes | `hedgefund/themes.py` | notes/sector_rotation_engine.md, RESEARCH.md §S1 |
| Stocks | `hedgefund/signals.py`, `confluence.py`, `revision_velocity.py` | REPORT.md walk-forward, pine/, /revisions page |
| LLM deep dive | `tradingagents/` (Omega context, knowledge brain, analysts) | strategies/*/DISCOVERY.md |
| Spot rules | `hedgefund/backtest.py`, `ledger.py` | REPORT.md (MAR 1.44 validated) |
| Options | `hedgefund/iv_rank.py`, `options_sim.py` | REPORT.md options desk, RESEARCH.md §S4 |
| Hedges/exits | `hedgefund/sell_composite.py`, sleeves income variant | RESEARCH.md §S2, OPTIMIZATION_REPORT |
| Live funnel | **`hedgefund/topdown.py`** | this document |

## Getting the live update

- **On demand:** `cd trading && python -m hedgefund.run topdown`
- **In Claude Code:** the `/topdown` skill (`.claude/skills/topdown/`)
- **Automated:** every market morning via the daily GitHub Action;
  report committed to `trading/hedgefund/reports/topdown-*.md`,
  snapshot at `state/topdown.json` (dashboard-ready).

## Known gaps (honest)

- Fundamental gate / PEAD / earnings quality: LLM-prompt layer only —
  no historical fundamentals feed for mechanical validation yet.
- Revision velocity requires network (FMP key or Yahoo) — sandboxed
  runs show "—".
- Options structures are model-derived (no live chains in the repo);
  strikes are ATR guides, verify against the real chain before entry.
- Sleeve-3 optimization parameters are provisional pending the 2026
  year-end re-validation (flagged in OPTIMIZATION_REPORT).
