# Strategy Discovery: crypto_algo_trading

**Date:** 2026-07-05 (edited 2026-07-23: wallet-positioning removed, TTM Squeeze + ADX added)
**Phase:** Discovery Complete
**Engine:** pandas
**Project Type:** hybrid (composite quant signals + technical confirmation)

---

## Core Hypothesis

Crypto derivatives positioning (OI-weighted funding) and spot/futures order-flow imbalance (CVD) together carry more signal than either alone. When both align, and a squeeze-release + trend-strength filter confirms momentum is actually building (not chop), the strategy takes a directional position; a macro regime filter (BTC 20-week SMA) and event-driven leverage throttling manage tail risk around known volatility catalysts.

### Market Behavior Exploited
Crowded, overleveraged positioning (visible via funding + OI) combined with order-flow divergence from spot vs. futures CVD signals short-term dislocations. A TTM Squeeze release confirms the market is exiting a low-volatility compression into a directional move, and ADX confirms that move has real trend strength rather than being noise — both filter out low-conviction setups the raw derivatives signal alone would take.

### Theoretical Basis
- **OI-weighted funding:** extreme funding + rising OI indicates crowded leveraged positioning prone to unwind/squeeze.
- **Spot vs. futures CVD divergence:** structural — futures-led moves without spot participation tend to be less durable (or vice versa, signal building spot accumulation).
- **TTM Squeeze:** Bollinger Bands contracting inside Keltner Channels marks a volatility compression ("squeeze on"); the release (BB expands back outside KC) with histogram momentum in the trade direction has documented use as a breakout-timing filter.
- **ADX:** measures trend strength independent of direction; gating entries on ADX above a threshold avoids taking the funding/CVD signal during choppy, non-trending conditions where it's more likely to whipsaw.

---

## Entry Conditions

| Condition | Description | Data Required |
|-----------|-------------|---------------|
| Funding/OI extreme | OI-weighted funding rate crosses a defined extreme threshold (crowded long/short) | Funding rate, open interest (per exchange/perp) |
| CVD alignment | Spot CVD and futures CVD both trend in the entry direction (or show a defined divergence pattern) | Spot trade tape, futures trade tape → cumulative volume delta |
| Regime filter (macro) | BTC weekly close above 20-week SMA (long bias) / below (short bias or flat) | BTC weekly OHLCV |
| Momentum filter | RSI(14) between `rsi_min` and `rsi_max`, and price above `ma_short` which is above `ma_long` (direction-aligned crossover) | Symbol OHLCV close, RSI(14), MA(`ma_short`), MA(`ma_long`) |
| TTM Squeeze (added) | Squeeze was "on" (BB(20,2.0) inside KC(20,1.5×ATR)) and has fired/released with histogram momentum aligned to `direction` | OHLCV close, BB(20,2.0), KC(20,1.5×ATR), momentum histogram |
| ADX trend strength (added) | ADX(14) ≥ `adx_threshold` — confirms a genuine trending regime, not chop | OHLCV high/low/close → ADX(14) |

**Removed:** the Hyperliquid top-wallet-cohort "smart-money confirmation" condition — dropped per user request. This also removes the Hyperliquid wallet-leaderboard data dependency entirely (see Data Requirements).

Merged per `Edge_config.yaml` / `Parameters_ranges.yaml`: the RSI/MA layer is an additional confirmation filter on top of the funding+CVD+regime composite, not a replacement. TTM Squeeze and ADX are further additional filters layered on top of that. Tunable ranges (from `Parameters_ranges.yaml`): `funding_rate` in [-0.1, -0.01, 0.01, 0.1], `rsi_min` in [40, 50, 60], `rsi_max` in [60, 70, 80], `ma_short` in [10, 20, 30], `ma_long` in [50, 100, 200], `leverage` in [1, 2, 3, 4, 5]. Default point estimate (from `Edge_config.yaml`): `funding_rate: -0.05`, `rsi_min: 50`, `rsi_max: 70`, `ma_short: 20`, `ma_long: 50`. TTM Squeeze/ADX parameters are new — see `config.yaml` for defaults and optimize ranges (no source-doc precedent, standard textbook settings used as the starting point).

### Entry Signal Logic
```
if oi_weighted_funding is at extreme(direction)
   and spot_cvd_trend == direction
   and futures_cvd_trend == direction
   and btc_weekly_close vs 20w_SMA supports direction
   and rsi_min <= RSI(14) <= rsi_max
   and MA(ma_short) vs MA(ma_long) supports direction
   and ttm_squeeze_fired_in(direction)
   and ADX(14) >= adx_threshold:
        enter(direction, size=base_size * leverage_overlay)
```
`leverage_overlay` = 0.5x around CME OpEx / CPI / FOMO windows, else 1x (needs an economic-calendar/event-date feed).

---

## Exit Conditions

### Take Profit
No single fixed target — optimize empirically for whatever maximizes overall realized return during backtesting/iteration (candidates to test: fixed R:R, trailing, scale-out). Baseline mechanic to start from: **scale out 50% at first target, trail remainder with a 20-day low stop** — treat the exact target/trail parameters as tunable in `/cbt:optimize`, not fixed here.

### Stop Loss
**Signal invalidation** — exit when the entry thesis breaks: funding/OI normalizes or flips, CVD alignment reverses, or ADX drops back below `adx_threshold` (trend strength gone). Not a fixed %/ATR stop.

Concrete invalidation triggers merged from `Edge_config.yaml`: `funding_rate` reaching `0.1` (crowded-opposite extreme) or BTC closing below its 200-period MA — both treated as instances of the signal-invalidation exit above, not a separate fixed stop.

### Risk Caps
`leverage_max: 5`, `position_max: 0.1` (10% of capital per position) — hard ceilings from `Edge_config.yaml`, applied regardless of the `leverage_overlay` event throttle above.

### Other Exit Conditions
- **Macro kill-switch:** if BTC closes below its 20-week SMA for 2 consecutive weeks, flatten/avoid new longs (regime filter, not per-trade stop).
- **Event risk overlay:** reduce leverage 50% around CME options expiry, CPI, and FOMO/FOMC windows — risk management layer, applies regardless of open positions.

---

## Data Requirements

| Dataset | Resolution | Source | Size Estimate | Status |
|---------|------------|--------|---------------|--------|
| Funding rate + OI (per perp) | Intraday (per funding interval) | Hyperliquid's official public `info` endpoint (`fundingHistory` request type) — free, keyless, documented at hyperliquid.gitbook.io. **Confirmed blocked from this sandbox**: a direct `curl -X POST https://api.hyperliquid.xyz/info` was rejected by this environment's network egress gateway (403, "policy denial"), same as the Fear&Greed/CoinGecko hosts elsewhere in this project — not an API-side failure | Unknown | ⚠️ API is free/open; this environment's network policy blocks it |
| Spot trade tape → CVD | Intraday (tick or 1m aggregated) | No packaged CVD data point found anywhere — would need raw trade-tape aggregation from an exchange API (buildable in code, nothing off-the-shelf) | Unknown | ❌ Not reachable as a ready dataset |
| Futures trade tape → CVD | Intraday (tick or 1m aggregated) | Same as spot CVD above | Unknown | ❌ Not reachable as a ready dataset |
| BTC/crypto spot price + OHLCV (for TTM Squeeze, ADX, RSI, MA, regime filter) | Daily/weekly | FMP `crypto` — confirmed reachable, verified live ($62,762) | Small | ✅ Reachable |
| Macro event calendar (CME OpEx, CPI, FOMC dates) | Event dates | Tipranks `get_economic_calendar` — confirmed reachable (Fed meeting, CPI, PPI, jobs reports all present in a real pull); CME OpEx specifically not confirmed | Small | ✅ Mostly reachable |

Removing the wallet-leaderboard condition cuts this strategy's blocked-data surface from 2 data points to 1 (funding/OI only) — CVD remains separately blocked as a build-it-yourself aggregation problem, not a network-policy issue. TTM Squeeze and ADX add no new data requirement; both compute from the OHLCV already reachable via FMP.

### Data Scale
- **Estimated rows:** unknown — not yet sourced
- **Engine:** pandas (default; revisit at `/cbt:eda` once real data volumes are known — tick-level CVD data across two markets could push this into "fast engine" territory)
- **Rationale:** don't switch engines speculatively; decide once actual row counts from funding/CVD feeds are known

### Data Validation Checklist
- [ ] No gaps in timestamps across the funding/OI and CVD feeds
- [ ] Funding/OI and CVD series aligned to a common bar interval
- [ ] Sufficient history for a full macro cycle (ideally 2+ years, spans multiple funding regimes)

---

## Build Plan

**Complexity Level:** Medium (multi-signal composite; no ML model training, so not full ML pipeline, but too much feature composition to call "simple")

| Step | Description | Output |
|------|-------------|--------|
| 1 | Source funding/OI, spot CVD, futures CVD, BTC weekly OHLCV, macro event dates | `Data/*.csv` or `.parquet` |
| 2 | Build OI-weighted funding extreme detector | `src/features/funding.py` |
| 3 | Build spot/futures CVD trend + alignment detector | `src/features/cvd.py` |
| 4 | Build BTC 20-week SMA regime filter | `src/features/regime.py` |
| 5 | Build TTM Squeeze (BB-inside-KC + momentum histogram) detector | `src/features/ttm_squeeze.py` |
| 6 | Build ADX(14) trend-strength filter | `src/features/adx.py` |
| 7 | Build macro event leverage overlay | `src/features/event_overlay.py` |
| 8 | Combine into composite entry signal | `src/signals.py` |
| 9 | Implement exit logic (signal-invalidation stop, scale-out/trail take-profit) | `src/exits.py` |
| 10 | Wire into backtest engine with prop-firm Phase 1 rules | `src/backtest.py` |
| 11 | Run baseline backtest, iterate exit parameters via `/cbt:optimize` | `experiments/` |

---

## Success Criteria

- [ ] Sharpe Ratio > 2.0
- [ ] Win Rate > 55%
- [ ] Passes Prop Firm Phase 1 (10% target) without breaching drawdown/daily-loss limits in backtest

## Account Rules

**Account Type:** prop_firm

| Rule | Value |
|------|-------|
| Phase | 1 |
| Max Drawdown (from initial) | 10% |
| Daily Loss Limit (from prev day) | 5% |
| Profit Target | 10% |
| Breach Action | Halt trading |

---

## Kill Criteria

Abandon strategy if:
- [ ] Backtest Sharpe < 1.0 after full iteration cycle
- [ ] Strategy breaches Phase 1 drawdown/daily-loss limits repeatedly across walk-forward windows
- [ ] CVD/funding data proves too sparse or unreliable across target exchanges
- [ ] TTM Squeeze/ADX filters cut trade frequency so much the backtest has too few trades to be statistically meaningful

---

## Questions for Research Phase

1. Does OI-weighted funding + CVD alignment have documented edge in existing quant research, or is this purely a novel composite?
2. What's the realistic execution risk (slippage, funding payment timing) of running this on Hyperliquid at target size vs. backtest assumptions?
3. What ADX threshold and TTM Squeeze histogram-momentum lookback actually separate trending from choppy regimes in BTC specifically (textbook defaults are equity-market-derived, may not transfer directly to crypto's volatility profile)?

---

*Generated by CBT Framework /cbt:discover, edited 2026-07-23 per user request (wallet-positioning removed, TTM Squeeze + ADX added)*
