# Data Requirements for crypto_algo_trading

## Required Files

| File | Format | Columns | Notes |
|------|--------|---------|-------|
| `funding_oi.csv` | CSV/Parquet | `timestamp, symbol, funding_rate, open_interest` | Per-perp, intraday (per funding interval or 1h resampled) |
| `spot_cvd.csv` | CSV/Parquet | `timestamp, symbol, price, volume, side` (buy/sell) or pre-aggregated `cvd` | Used to derive spot cumulative volume delta |
| `futures_cvd.csv` | CSV/Parquet | `timestamp, symbol, price, volume, side` or pre-aggregated `cvd` | Used to derive futures cumulative volume delta |
| `hyperliquid_wallets.csv` | CSV/Parquet | `wallet, date, return_pct, win_rate, position, notional` | Leaderboard snapshot + per-wallet position history |
| `btc_weekly.csv` | CSV/Parquet | `timestamp, open, high, low, close, volume` | Weekly BTC OHLCV for the regime filter |
| `macro_events.csv` | CSV | `date, event_type` (CME_OPEX / CPI / FOMC) | Manual or sourced from an economic calendar |

## Data Sources

- Funding/OI: exchange API (Hyperliquid, Binance, or Bybit — pick per `/cbt:research`)
- Spot/futures trade tape: exchange API or a data vendor (tick-level, aggregate to CVD)
- Hyperliquid wallet leaderboard: Hyperliquid public API
- BTC weekly OHLCV: any standard OHLCV source
- Macro event dates: economic calendar API or manually maintained CSV

## Validation

Run this to validate your data:
```python
# Validation script will be generated in /cbt:build
```

Known risks to check for during validation:
- Funding/OI and CVD series must align to a common bar interval before combining into the composite signal
- Wallet leaderboard snapshots need to be frequent enough that positioning reads aren't stale
- All intraday feeds need timestamp alignment across exchanges (no drift/gaps)
