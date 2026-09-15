# Build Plan: hermes_agent

**Date:** 2026-08-27
**Complexity:** Complex
**Engine:** fast (Polars → NumPy → Numba)
**Project Type:** hybrid (rule-based confluence + an unvalidated ML component)
**Steps:** 9

---

## Overview

Builds the regime-scaled trend/exit core **first**, as a fully-costed mechanical
baseline, then makes every later layer earn its place by beating that baseline.
This inverts DISCOVERY.md's original 8-step plan, which built the confluence
score before the regime engine — RESEARCH.md recommendation #1 reversed it,
because regime conditioning is the mechanism with actual evidential support and
the confluence layer's diversity precondition is known to fail on this feature
set (EDA.md: 80 feature pairs >0.9 correlated, several exactly 1.0).

The practical consequence: **the baseline run is step 5, not step 9.** Steps 6-9
are conditional on it, and any of them can end in "no edge found" — which
DISCOVERY.md already licensed as a valid outcome.

## Dependencies

```
1 Data pipeline
      │
      ├──→ 2 Regime engine ──┐
      │                      ├──→ 4 Backtest runner ──→ 5 BASELINE RUN ◀── the bar
      └──→ 3 Exit engine ────┘                                │
                                                              ▼
                                        6 Feature pipeline + dedup
                                                              │
                                                              ▼
                                        7 Confluence layer (must beat step 5)
                                                              │
                                                              ▼
                                        8 Ablation + walk-forward (Deflated Sharpe)
                                                              │
                                                              ▼
                                        9 BTC ML ensemble ── CONDITIONAL, may be dropped
```

---

## Step 1: Data Pipeline (Polars)

**File:** `src/data_loader.py`
**Depends on:** None
**Complexity:** Medium
**Checkpoint:** Yes — cache assembled panel to `Data/panel.parquet`

### What it does
Loads the daily price panel into Polars lazy frames, normalizes the mixed
equity (5d/wk) + crypto (7d/wk) calendar, and exposes contiguous float64 NumPy
arrays for the downstream Numba path.

### Key implementation details
- `pl.scan_csv("Data/btc_historical_data.csv", try_parse_dates=True)`, filter
  to `config.time.start_date` (2024-07-23) **before** collecting so the filter
  pushes into the scan.
- **Calendar join is the real work here.** The panel mixes BTC/ETH/SOL (7 days)
  with SPY/TLT/MSTR/ETFs (5 days). EDA found 13 calendar gaps >3 days, all
  ~4-day — weekends plus holidays, expected, not corruption. Decide one policy
  and apply it everywhere: forward-fill equities across crypto-only days, and
  **never** back-fill (that is lookahead).
- Convert with `np.ascontiguousarray(arr, dtype=np.float64)` — Numba will
  silently fall back to object mode on non-contiguous input.
- Universe is currently the 11-symbol panel. The ~60 uncached tickers from the
  real accounts (DISCOVERY.md universe table) are **out of scope for this
  build** — fetching them is separate work, and the baseline is measurable
  without them.

### Inputs
- `Data/btc_historical_data.csv` (524 rows × 11 symbols, 2024-07-23 → 2026-08-24)

### Outputs
- `Data/panel.parquet`, `load_panel() -> dict[str, np.ndarray]`

### Verification
- Row count and date range match EDA.md exactly (524 rows, 2024-07-23 start)
- Zero NaN after the calendar join; assert no back-fill occurred by checking
  that every forward-filled equity value equals the *prior* observed value
- `arr.flags['C_CONTIGUOUS']` is True for every emitted array

---

## Step 2: Regime Engine (NumPy)

**File:** `src/regime.py`
**Depends on:** Step 1
**Complexity:** Medium
**Checkpoint:** Yes — regime labels are reused by steps 3, 4, 7

### What it does
Classifies each bar into RISK_ON / MIXED / CAUTION / RISK_OFF and emits the
gross-exposure multiplier that drives both position sizing and trail width.

### Key implementation details
- **Start from `strategies/macro_sector_dominance`'s `regime_score_model`**, do
  not reinvent — `config.strategy_params.regime.source_template` points at it.
  Its `gross_exposure_pct` (80/50/25/0) is already mirrored into
  `config.regime_gross_exposure`.
- Use a **dynamic percentile** vol threshold, not a fixed cutoff:
  `vol_percentile: 0.75` over `vol_lookback_days: 30`. EDA confirmed real vol
  clustering (13.8% of days above 1.5× median 30d vol), which is what makes
  this mechanism worth building at all.
- **Every rolling statistic gets `.shift(1)`.** The regime label at bar *t* must
  be computable from bars < *t*. This is the single highest-risk lookahead
  surface in the build.
- Cash is the residual of gross exposure — do not add a separate cash rule.

### Inputs
- Step 1 arrays; FRED macro series if wired (optional for baseline)

### Outputs
- `regime_labels: np.ndarray[int8]`, `gross_exposure: np.ndarray[float64]`

### Verification
- All four regime states occur in the sample; print occupancy percentages and
  sanity-check against four_sleeve's realized 22-24% average cash
- Shift the entire input series forward one bar and confirm labels shift
  identically — a label that *doesn't* move is reading the future
- Regime at bar *t* recomputed from a truncated array `[0:t]` matches the
  full-array value at *t*

---

## Step 3: Exit Engine (NumPy → Numba)

**File:** `src/exits.py`
**Depends on:** Steps 1, 2
**Complexity:** High
**Checkpoint:** No

### What it does
Implements the full two-stage exit: 3.0×ATR initial stop → 50% scale-out at 1R
with stop to breakeven → runner on the regime-scaled trailing stop.

### Key implementation details
- ATR is a **close-to-close proxy** (no intraday H/L in this panel) — same
  documented limitation as the rest of this repo. Stops will read slightly
  tighter than true-range ATR. Note it in output, don't silently absorb it.
- 1R distances measured in `/cbt:config`: BTC +6.0%, ETH +9.3%, SOL +10.6%,
  **SPY +1.82%**. The `min_move_pct: 3.0` floor exists specifically to stop SPY
  scaling out on sub-2% noise — implement it as a hard gate on the scale-out
  trigger, not a size adjustment.
- Trail width is regime-scaled: 20 / 18 / 16 / 15% across RISK_ON → RISK_OFF.
  **Never tighten below 15%** without new evidence (Dai et al. 2021).
- The no-scale-out control arm (`first_tranche_pct: 0`) must be a supported
  code path from day one, not bolted on later — step 8 needs it.

### Inputs
- Step 1 price arrays, Step 2 regime labels, `config.risk.*`

### Outputs
- `apply_exits(...) -> (exit_idx, exit_price, exit_reason, tranche_fraction)`

### Verification
- Hand-construct a synthetic price path that hits each exit in isolation: ATR
  stop, 1R scale-out, breakeven stop on the runner, trailing stop. Assert the
  exact bar and price for each.
- Assert scale-out **never** fires when the move is below `min_move_pct`, using
  a synthetic SPY-like series with a +2% move
- Assert `first_tranche_pct: 0` produces identical results to a pure
  trailing-stop path

---

## Step 4: Backtest Runner (Numba JIT)

**File:** `backtest.py`
**Depends on:** Steps 1, 2, 3
**Complexity:** High
**Checkpoint:** Yes — writes `experiments/`

### What it does
The event loop: position sizing under the regime exposure cap, the capacity
floor, venue-aware costs, and equity-curve accounting.

### Key implementation details
- **`min_position_value_usd: 1000` is a SKIP, never a scale-down.** If a signal
  would size below the floor, the trade does not happen. Scaling it down to fit
  reintroduces exactly the ~$143-position cost structure the floor exists to
  prevent (Barber-Odean, 6.5pp/yr drag).
- **Venue-aware per-trade dollar costs**, not percentage-of-portfolio. Use
  `config.strategy_params.venue_costs`: equities $0 commission + 5bps slippage;
  Coinbase spot 0.60% taker + 10bps; Hyperliquid perps 0.035% + 5bps. The
  top-level `fees` block is an explicit placeholder — do not use it in the hot
  path.
- Gross exposure is capped by `regime_gross_exposure[t]`, so max deployed
  varies 80% → 0% by regime. `percent_per_trade × max_positions` (8 × 10 = 80)
  equals the RISK_ON cap by construction; assert that invariant at load.
- Numba: no Python objects in the loop, preallocate all output arrays, decorate
  `@njit(cache=True)`.

### Inputs
- Steps 1-3 outputs, full `config.yaml`

### Outputs
- Trade ledger, equity curve, `experiments/{run_id}/`

### Verification
- Reproduce a hand-computed 3-trade scenario to the cent, including costs
- Assert no trade in the ledger is below the position floor
- Assert deployed capital never exceeds `regime_gross_exposure[t]`
- Zero-cost run must produce strictly better results than the costed run — if
  not, the cost model is wired backwards

---

## Step 5: BASELINE RUN ◀ the bar every later step must clear

**File:** `experiments/baseline/`
**Depends on:** Step 4
**Complexity:** Low
**Checkpoint:** Yes — this becomes `ablation_baseline`

### What it does
Runs the mechanical core end-to-end and records the reference metrics. **No
confluence score, no features, no LLM, no ML.** Pure regime + trend + exit.

### Key implementation details
- Report the full `optimizer_objective.report_always` set: profit factor, CAGR,
  max drawdown, MAR, Deflated Sharpe, expectancy, turnover.
- Also run the two comparison arms RESEARCH.md requires: **buy-and-hold** and a
  **static (non-regime-scaled) allocation**. Beating buy-and-hold alone is not
  the test — four_sleeve found its regime matrix *added* drawdown versus a
  static allocation, so the static arm is the one that can embarrass us.
- Resolves **R1** (regime core beats B&H on MAR) and starts **R5** (costs at
  real position sizes).

### Inputs
- Everything above

### Outputs
- `experiments/baseline/metrics.json` — frozen reference

### Verification
- Deflated Sharpe computed with the honest trial count (1 at this stage)
- Metrics reproduce exactly on a re-run (seed/determinism check)
- If the baseline fails to beat *both* comparison arms, **stop and report** —
  steps 6-9 are not worth building on a core that doesn't work

---

## Step 6: Feature Pipeline + Deduplication (NumPy)

**File:** `src/features.py`
**Depends on:** Step 5
**Complexity:** Medium
**Checkpoint:** Yes

### What it does
Loads the 42-column feature set and collapses the known-collinear groups before
anything scores on them.

### Key implementation details
- **Dedup is mandatory, not optional.** EDA found `IBIT_return_1d ==
  FBTC_return_1d == ARKB_return_1d == BITB_return_1d` at correlation exactly
  1.0, plus the same for the `_vol` and `_flow_proxy` families. The 42 columns
  are ~10-15 independent signals. Collapse per
  `config.strategy_params.feature_dedup.collapse_groups`.
- **Feature history is shorter than price history**: features start 2025-05-08
  (325 rows) vs the panel's 2024-07-23 (524 rows). Either regenerate features
  back to 2024-07-23, or explicitly restrict steps 7-9 to the shorter window
  and say so in every result. Do not silently mix.
- 22 of 42 features showed significant train/test drift (KS p<0.01). Carry that
  list forward — step 8 needs to watch it.

### Inputs
- `Data/btc_ml_features.csv`, Step 1 panel

### Outputs
- Deduplicated feature matrix, drift-flagged column list

### Verification
- Post-dedup, **no** remaining feature pair exceeds |corr| 0.9 — assert it
- Feature count drops from 42 to roughly 10-15
- Resolves **R2** setup (dedup must not destroy the confluence edge — if it
  does, the edge was redundancy)

---

## Step 7: Confluence Scoring Layer

**File:** `src/confluence.py`
**Depends on:** Step 6
**Complexity:** High
**Checkpoint:** Yes

### What it does
Extracts the live bus's F/T/S/M scoring into replayable code and applies the
entry gate.

### Key implementation details
- The F/T/S/M formula currently exists **only as live JSON output**, not as
  backtestable logic (`Data/bus_snapshots/trade_setups.json` shows the outputs:
  COIN F8/T9/S9/M8, conf 8.5). Reverse-engineering it from snapshots is real
  work — if the formula can't be recovered faithfully, say so rather than
  inventing one and calling it Hermes.
- `entry_gate.composite_threshold` is deliberately **null**. Do not pick a
  number here; step 8's grid resolves it across `[6.5, 7.0, 7.5, 8.0]`.
- Three candidate gate forms to support: composite threshold, all-subscores
  floor, regime-gated bar.

### Inputs
- Step 6 features, Step 2 regime labels, bus snapshots as reference

### Outputs
- `confluence_score: np.ndarray`, `entry_signal: np.ndarray[bool]`

### Verification
- Replay the score against the dated bus snapshots and compare to the recorded
  F/T/S/M values — a faithful extraction should approximately reproduce them
- Signal count is sane (not zero, not every bar)

---

## Step 8: Ablation + Walk-Forward (Deflated Sharpe)

**File:** `src/validate.py`
**Depends on:** Steps 5, 7
**Complexity:** High
**Checkpoint:** Yes

### What it does
The step that decides whether hermes_agent has an edge. Runs the pre-registered
grids, ablates each layer, and reports Deflated Sharpe with the true trial count.

### Key implementation details
- **Objective:** maximize profit factor, subject to Deflated Sharpe significant
  at p<0.05 and MAR ≥ the step-5 baseline. CAGR always reported — the PF/CAGR
  conflict is real (this repo's own scale-in test: PF 1.74→3.65 while CAGR fell
  30.5%→19.3%), and suppressing CAGR would hide the price being paid.
- **Count every trial.** The pre-registered grids multiply out fast:
  trailing (3) × scale-out trigger (3) × tranche (4) × min_move (3) ×
  threshold (4) × max_positions (4) ≈ 1,700+ configs. Deflated Sharpe with
  n=1,700 is a very different bar than n=1. Bailey & López de Prado: the max
  Sharpe is inflated even if every candidate is pure noise.
- Resolves **R2, R3, R4, R7, R8, R9** — each pending observation gets an
  explicit verdict, including the ones that come back negative.
- Watch the 22 drift-flagged features from step 6 in the OOS window specifically.

### Inputs
- Steps 5, 6, 7

### Outputs
- `experiments/ablation/`, verdict per observation R1-R9

### Verification
- Every layer ablated independently (regime off, confluence off, scale-out off)
- Trial count stated explicitly in the report
- **"No edge found" is an acceptable and expected-possible verdict** — RESEARCH
  rated overall confidence Low-to-Medium and named this a live possibility

---

## Step 9: BTC ML Ensemble — CONDITIONAL

**File:** `src/model.py`
**Depends on:** Step 8
**Complexity:** Medium
**Checkpoint:** Yes

### What it does
Only built if step 8 shows the mechanical layers leave signal on the table.

### Key implementation details
- **Currently `enabled: false`, status `drop_candidate_pending_ablation`.** Its
  own report: 0.48 directional accuracy / 0.46 AUC. EDA: max |feature-target
  correlation| across all 42 columns is 0.13 (`spy_return`).
- Build this **only** if step 8 identifies a residual a non-linear model could
  plausibly capture. Otherwise the honest action is to delete it from scope and
  record why — that resolves RESEARCH open question #3.
- Label generation must shift labels correctly for use (train on
  `close.shift(-5) > close`, but never *trade* on an unshifted label).

### Inputs
- Step 6 features, Step 8 residuals

### Outputs
- Either a validated model, or a written decision to drop it

### Verification
- Must beat step 5 baseline **and** step 7 confluence on Deflated Sharpe
- Purged/embargoed walk-forward splits — no leakage across the boundary

---

## Explicitly out of scope for this build

- **The LLM agent layer.** Quarantined to forward paper validation only
  (`metrics_policy.llm_layer: forward_paper_only`). The leakage lives in the
  model weights — a 2026 audit of 77 LLM-trading studies found agent alpha
  "largely dissolves once look-ahead bias is controlled," and no amount of
  careful data plumbing fixes a training cutoff. It cannot be backtested here.
- **The ~60 uncached tickers** from the real accounts. Separate fetch work; the
  baseline is measurable without them.
- **The perps/margin sleeve.** `leverage.enabled: false` for the baseline.

## Open input, not blocking

`initial_capital` is $80,000 from four reconciled accounts, but the author has
flagged that **their figures were miscalculated** — the correct total is
pending. This does not block steps 1-9: it changes absolute dollar outcomes and
where the `min_position_value_usd` floor binds, but not the step order, the
logic, or any relative comparison between arms. Re-run step 5 onward once the
corrected number lands.

---

## Final Checklist

Before the baseline run (step 5):
- [ ] All source files import correctly
- [ ] **No lookahead**: every rolling stat `.shift(1)`; truncated-array recompute matches
- [ ] `config.yaml` wired — especially the position floor and venue costs
- [ ] Data loads with zero NaN and no back-fill
- [ ] Polars lazy frames collected only after filters push down
- [ ] NumPy arrays C-contiguous float64
- [ ] Numba functions compile without object-mode fallback warnings
- [ ] `percent_per_trade × max_positions == regime_gross_exposure.RISK_ON`
- [ ] Both comparison arms (buy-and-hold, static allocation) implemented

Before any grid search (step 8):
- [ ] Trial count tracked and reported
- [ ] Deflated Sharpe implemented and unit-tested against a known case
- [ ] Control arms present: no-scale-out, no-regime, no-confluence

---

*Generated by CBT Framework /cbt:plan*
