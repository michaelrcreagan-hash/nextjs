# Strategy Discovery: crypto_algo_trading

**Date:** 2026-07-05
**Phase:** Discovery Complete
**Engine:** pandas
**Project Type:** hybrid (composite quant signals + wallet-ranking filter)

---

## Core Hypothesis

Crypto derivatives positioning (OI-weighted funding), spot/futures order-flow imbalance (CVD), and the revealed positioning of consistently profitable Hyperliquid traders together carry more signal than any single input. When all three align, the strategy takes a directional position; a macro regime filter (BTC 20-week SMA) and event-driven leverage throttling manage tail risk around known volatility catalysts.

### Market Behavior Exploited
Crowded, overleveraged positioning (visible via funding + OI) combined with order-flow divergence from spot vs. futures CVD signals short-term dislocations. Overlaying the actual positioning of a filtered set of high-win-rate, high-return Hyperliquid wallets acts as a smart-money confirmation/contrarian-crowd filter on top of the raw derivatives data.

### Theoretical Basis
- **OI-weighted funding:** extreme funding + rising OI indicates crowded leveraged positioning prone to unwind/squeeze.
- **Spot vs. futures CVD divergence:** structural — futures-led moves without spot participation tend to be less durable (or vice versa, signal building spot accumulation).
- **Top-wallet positioning:** informational edge — wallets pre-filtered on consistent win rate and return% are assumed to have persistent skill or information advantage; following/confirming with their exposure raises signal quality.

---

## Entry Conditions

| Condition | Description | Data Required |
|-----------|-------------|---------------|
| Funding/OI extreme | OI-weighted funding rate crosses a defined extreme threshold (crowded long/short) | Funding rate, open interest (per exchange/perp) |
| CVD alignment | Spot CVD and futures CVD both trend in the entry direction (or show a defined divergence pattern) | Spot trade tape, futures trade tape → cumulative volume delta |
| Smart-money confirmation | Net positioning of the filtered top-wallet cohort (ranked by return% + win-rate consistency) agrees with direction | Hyperliquid wallet leaderboard + per-wallet position/PnL history |
| Regime filter (macro) | BTC weekly close above 20-week SMA (long bias) / below (short bias or flat) | BTC weekly OHLCV |
| Momentum filter (added) | RSI(14) between `rsi_min` and `rsi_max`, and price above `ma_short` which is above `ma_long` (direction-aligned crossover) | Symbol OHLCV close, RSI(14), MA(`ma_short`), MA(`ma_long`) |

Merged per `Edge_config.yaml` / `Parameters_ranges.yaml`: the RSI/MA layer does not replace the composite (funding+CVD+wallet+regime) — it's an additional confirmation filter. A candidate entry must still pass the original 4 conditions; RSI/MA then further times/confirms it. Tunable ranges (from `Parameters_ranges.yaml`): `funding_rate` in [-0.1, -0.01, 0.01, 0.1], `rsi_min` in [40, 50, 60], `rsi_max` in [60, 70, 80], `ma_short` in [10, 20, 30], `ma_long` in [50, 100, 200], `leverage` in [1, 2, 3, 4, 5]. Default point estimate (from `Edge_config.yaml`): `funding_rate: -0.05`, `rsi_min: 50`, `rsi_max: 70`, `ma_short: 20`, `ma_long: 50`.

### Entry Signal Logic
```
if oi_weighted_funding is at extreme(direction)
   and spot_cvd_trend == direction
   and futures_cvd_trend == direction
   and top_wallet_net_position == direction
   and btc_weekly_close vs 20w_SMA supports direction
   and rsi_min <= RSI(14) <= rsi_max
   and MA(ma_short) vs MA(ma_long) supports direction:
        enter(direction, size=base_size * leverage_overlay)
```
`leverage_overlay` = 0.5x around CME OpEx / CPI / FOMO windows, else 1x (needs an economic-calendar/event-date feed).

---

## Exit Conditions

### Take Profit
No single fixed target — optimize empirically for whatever maximizes overall realized return during backtesting/iteration (candidates to test: fixed R:R, trailing, scale-out). Baseline mechanic to start from: **scale out 50% at first target, trail remainder with a 20-day low stop** — treat the exact target/trail parameters as tunable in `/cbt:optimize`, not fixed here.

### Stop Loss
**Signal invalidation** — exit when the entry thesis breaks: funding/OI normalizes or flips, CVD alignment reverses, or the top-wallet cohort's net positioning flips against the trade. Not a fixed %/ATR stop.

Concrete invalidation triggers merged from `Edge_config.yaml`: `funding_rate` reaching `0.1` (crowded-opposite extreme) or BTC closing below its 200-period MA — both treated as instances of the signal-invalidation exit above, not a separate fixed stop.

### Risk Caps (added)
`leverage_max: 5`, `position_max: 0.1` (10% of capital per position) — hard ceilings from `Edge_config.yaml`, applied regardless of the `leverage_overlay` event throttle above.

### Other Exit Conditions
- **Macro kill-switch:** if BTC closes below its 20-week SMA for 2 consecutive weeks, flatten/avoid new longs (regime filter, not per-trade stop).
- **Event risk overlay:** reduce leverage 50% around CME options expiry, CPI, and FOMO/FOMC windows — risk management layer, applies regardless of open positions.

---

## Data Requirements

| Dataset | Resolution | Source | Size Estimate | Status |
|---------|------------|--------|---------------|--------|
| Funding rate + OI (per perp) | Intraday (likely 1h or per-funding-interval) | Exchange API (Hyperliquid/Binance/Bybit) | Unknown | [ ] Need |
| Spot trade tape → CVD | Intraday (tick or 1m aggregated) | Exchange API / data vendor | Unknown | [ ] Need |
| Futures trade tape → CVD | Intraday (tick or 1m aggregated) | Exchange API / data vendor | Unknown | [ ] Need |
| Hyperliquid wallet leaderboard + positions | Daily/near-real-time | Hyperliquid API | Unknown | [ ] Need |
| BTC weekly OHLCV | Weekly | Any OHLCV source | Small | [ ] Need |
| Macro event calendar (CME OpEx, CPI, FOMC dates) | Event dates | Manual/economic calendar API | Small | [ ] Need |

### Data Scale
- **Estimated rows:** unknown — not yet sourced
- **Engine:** pandas (default; revisit at `/cbt:eda` once real data volumes are known — tick-level CVD data across two markets could push this into "fast engine" territory)
- **Rationale:** don't switch engines speculatively; decide once actual row counts from funding/CVD/wallet feeds are known

### Data Validation Checklist
- [ ] No gaps in timestamps across all 4 intraday feeds
- [ ] Funding/OI and CVD series aligned to a common bar interval
- [ ] Wallet leaderboard snapshot frequency sufficient to avoid stale positioning reads
- [ ] Sufficient history for a full macro cycle (ideally 2+ years, spans multiple funding regimes)

---

## Build Plan

**Complexity Level:** Medium (multi-signal composite + wallet-ranking filter; no ML model training, so not full ML pipeline, but too much feature composition to call "simple")

| Step | Description | Output |
|------|-------------|--------|
| 1 | Source funding/OI, spot CVD, futures CVD, wallet leaderboard, BTC weekly OHLCV, macro event dates | `Data/*.csv` or `.parquet` |
| 2 | Build OI-weighted funding extreme detector | `src/features/funding.py` |
| 3 | Build spot/futures CVD trend + alignment detector | `src/features/cvd.py` |
| 4 | Build top-wallet ranking (return% + win-rate consistency) + net positioning aggregator | `src/features/wallets.py` |
| 5 | Build BTC 20-week SMA regime filter | `src/features/regime.py` |
| 6 | Build macro event leverage overlay | `src/features/event_overlay.py` |
| 7 | Combine into composite entry signal | `src/signals.py` |
| 8 | Implement exit logic (signal-invalidation stop, scale-out/trail take-profit) | `src/exits.py` |
| 9 | Wire into backtest engine with prop-firm Phase 1 rules | `src/backtest.py` |
| 10 | Run baseline backtest, iterate exit parameters via `/cbt:optimize` | `experiments/` |

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
- [ ] Wallet-leaderboard signal shows no persistence (top wallets churn too fast to be a stable filter)
- [ ] CVD/funding data proves too sparse or unreliable across target exchanges

---

## Questions for Research Phase

1. Does OI-weighted funding + CVD alignment have documented edge in existing quant research, or is this purely a novel composite?
2. How stable is "top wallet by return% and win-rate" as a cohort over time on Hyperliquid — does membership churn destroy the signal?
3. What's the realistic execution risk (slippage, funding payment timing) of running this on Hyperliquid at target size vs. backtest assumptions?

---

*Generated by CBT Framework /cbt:discover*
