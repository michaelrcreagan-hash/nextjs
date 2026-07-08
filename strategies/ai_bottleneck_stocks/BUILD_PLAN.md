# Build Plan: ai_bottleneck_stocks

**Date:** 2026-07-06
**Complexity:** Medium (feature-based composite, no ML model)
**Engine:** pandas
**Project Type:** indicator (hybrid fundamental + technical composite)
**Estimated Steps:** 6

---

## Overview

Builds the Four-Factor Model, Phase Score, and Sell Composite from `DISCOVERY.md` against the ~52-ticker universe in `Data/universe.csv`, using FMP for OHLCV/technicals (confirmed reachable) and Tipranks for options-flow/hedge-fund/sentiment (confirmed reachable, throttled to top-3-by-Phase-Score/weekly per `config.yaml`'s `api_scan_policy`). No `/cbt:research` or `/cbt:eda` pass was run before this plan — `DISCOVERY.md` is the sole source; feature engineering below flags which sub-factors are real-data-backed vs. manual placeholder so the gap is never hidden inside a number.

## Dependencies

```
Step 1 (data_loader) ─→ Step 2 (features) ─→ Step 3 (signals) ─→ Step 4 (strategy) ─→ Step 5 (backtest) ─→ Step 6 (baseline run)
```

---

## Step 1: Data Pipeline

**File:** `src/data_loader.py`
**Depends on:** None
**Complexity:** Low
**Checkpoint:** Yes — cache pulled OHLCV to `Data/daily_ohlcv.parquet`

### What it does
Loads `Data/universe.csv` (52 tickers, 9 layers), pulls daily OHLCV via FMP for each ticker, pulls SMH (Tipranks, since FMP ETF-quote is plan-gated) for the RS-vs-SMH factor, and caches everything locally so later steps don't re-hit rate-limited APIs.

### Key implementation details
- FMP confirmed reachable for individual stock quotes/history this session (NVDA test) — no quota issue observed
- SMH price must come from Tipranks (`get_stock_quotes`), not FMP — FMP's ETF-quote endpoint hit a plan-tier 403 this session
- Cache aggressively: Tipranks is capped at 10 calls/month total, don't re-fetch SMH more than once per run

### Inputs
- `Data/universe.csv`

### Outputs
- `Data/daily_ohlcv.parquet` (per-ticker daily bars, all 52 tickers + SMH)

### Verification
- Row count matches expected trading days × 52 tickers, no all-null columns
- SMH series present and non-empty

---

## Step 2: Feature Engineering

**File:** `src/features.py`
**Depends on:** Step 1
**Complexity:** High — this is where the resolved-vs-placeholder distinction from `DISCOVERY.md` has to be encoded honestly
**Checkpoint:** Yes

### What it does
Computes the three composite scores. Each sub-factor is tagged `live` or `placeholder` in the output so the composite score's provenance is never ambiguous downstream.

**Four-Factor Model (0-25):**
| Sub-factor | Status | Implementation |
|---|---|---|
| Relative Strength vs SMH & SPX | `live` | 20/65-day RS computed from Step 1's cached OHLCV |
| Technicals | `live` | EMA(8/21/50/200) stack, RSI(14), MACD, RVOL from FMP `technicalIndicators` |
| Earnings Revision Momentum | `placeholder` | No connected feed (Zacks/Visible Alpha not available; AlphaVantage `EARNINGS_ESTIMATES` exists but 25-req/day cap makes it impractical across 52 names) — defaults to neutral (2.5/10) until a real feed is wired in |
| Scarcity/Moat Durability | `placeholder` | Qualitative, no connected data source — defaults to neutral (2.5/5) until manually scored per name |

**Phase Score (0-50):**
| Sub-factor | Status | Implementation |
|---|---|---|
| Momentum | `live` | Price vs SPX, 1M+3M RS from Step 1 |
| Capex Velocity | `placeholder` | Needs hyperscaler earnings-transcript parsing — not built here |
| Supply Tightness | `placeholder` | Needs supply-chain tracker (TrendForce/Everstream) — not connected |
| EPS Revision | `placeholder` | Same gap as Four-Factor's earnings-revision sub-factor |
| Analyst Upgrades | `placeholder` | No connected feed |

**Sell Composite (5 components):**
| Component | Status | Implementation |
|---|---|---|
| RVOL failure | `live` | From Step 1 volume data |
| RSI exhaustion | `live` | From Step 1 technicals |
| OpEx calendar timing | `live` | Computable from expiry calendar (3rd-Friday rule), no external data needed |
| Options flow | `live, throttled` | Tipranks `get_options_unusual_trades` — top-3-by-Phase-Score only, weekly, per `api_scan_policy` |
| Hyperscaler capex signal | `placeholder` | Same capex-transcript gap as Phase Score |

### Inputs
- `Data/daily_ohlcv.parquet`

### Outputs
- `Data/features.parquet` — per-ticker, per-day: all sub-factor values + a `provenance` column (`live`/`placeholder`) per sub-factor

### Verification
- No lookahead: every rolling/RS calculation uses `.shift(1)` before being used as a same-day signal input
- Placeholder columns are constant (2.5/10 or 2.5/5) and clearly labeled, not silently blended into a number that looks fully live

---

## Step 3: Signal Generation

**File:** `src/signals.py`
**Depends on:** Step 2
**Complexity:** Medium
**Checkpoint:** Yes

### What it does
Combines Step 2's features into the composite scores and entry/exit booleans exactly as specified in `DISCOVERY.md`:

```
four_factor_score = 10*earnings_revision + 6.25*rs_score + 5*moat_score + 3.75*technicals_score  # scaled 0-1 sub-scores
phase_score = sum(5 factors, each 0-10)
entry = (four_factor_score >= four_factor_threshold=16)
        and (phase_score >= phase_score_threshold=40)
        and ema8 > ema21 > ema50 > ema200
        and (50 <= rsi <= 65)
        and (1.5 <= rvol <= 2.0)
sell_composite_active_count = sum of the 5 boolean triggers from DISCOVERY.md
exit = sell_composite_active_count >= 3  # or trailing-stop / days_post_earnings=60
```

### Key implementation details
- Thresholds pulled from `config.yaml` `strategy_params`, not hardcoded, so `/cbt:optimize` can sweep them later
- Because two of the Four-Factor sub-factors and four of the five Phase Score sub-factors are `placeholder` this build, the composite scores will be systematically lower/flatter than a fully-live version — this is expected and must be called out in the baseline run's output, not presented as a real edge signal yet

### Inputs
- `Data/features.parquet`

### Outputs
- `Data/signals.parquet` — per-ticker, per-day entry/exit booleans + composite score values

### Verification
- Spot-check 3-5 known bullish-stack tickers (e.g., NVDA during a confirmed uptrend) produce `entry=True` when technicals align, regardless of placeholder drag

---

## Step 4: Strategy Integration

**File:** `strategy.py`
**Depends on:** Step 3
**Complexity:** Low
**Checkpoint:** No

### What it does
Wires signals into position sizing (6% max per name from `config.yaml`), the trailing-stop-by-phase logic, and the 60-day post-earnings exit.

### Inputs
- `Data/signals.parquet`, `config.yaml`

### Outputs
- `strategy.py` (importable position-sizing + exit logic module)

### Verification
- Unit-test the trailing-stop and days-post-earnings exit against a handful of synthetic price paths

---

## Step 5: Backtest Runner

**File:** `src/backtest.py`
**Depends on:** Step 4
**Complexity:** Medium
**Checkpoint:** Yes

### What it does
Event-driven backtest over the full universe/date range, applying fees/slippage from `config.yaml`, producing a trade log and equity curve.

### Inputs
- `strategy.py`, `Data/signals.parquet`

### Outputs
- `experiments/baseline/trades.csv`, `experiments/baseline/equity_curve.csv`

### Verification
- No negative cash balance, no trades sized above the 6% cap, trade count is sane for the date range (not zero, not one per bar)

---

## Step 6: Baseline Run

**Depends on:** Step 5
**Complexity:** Low
**Checkpoint:** Yes — this is the actual first real (partial-data) result

### What it does
Runs the backtest once, reports Sharpe/win-rate/max-drawdown **with the placeholder-sub-factor caveat attached to the output**, not as a clean number. Per the user's own Fund-of-Agents doc: a credible deployable Sharpe is 1.0-1.5 — anything wildly above that on this partial-data build is a red flag to investigate, not celebrate.

### Verification
- Result includes a visible "N of M sub-factors are placeholders" note
- Sharpe/drawdown are sanity-checked against the 1.0-1.5 / 18-25% honest range before treating the run as meaningful

---

## Final Checklist

Before running baseline:
- [ ] All source files created and import correctly
- [ ] No lookahead bias in features (all use `.shift(1)`)
- [ ] `config.yaml` parameters wired correctly, not hardcoded
- [ ] Data loads without errors for all 52 tickers + SMH
- [ ] Signals generate for full dataset
- [ ] Placeholder sub-factors are clearly labeled in output, not silently blended in as if live

---

*Generated by CBT Framework /cbt:plan*
