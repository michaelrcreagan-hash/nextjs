# Data Requirements for crypto_investing_4yr

## Required Files

| File | Format | Columns | Notes |
|------|--------|---------|-------|
| `btc_weekly.csv` | CSV | `date, open, high, low, close` | For 200-week MA |
| `mvrv_zscore.csv` | CSV | `date, mvrv_zscore` | On-chain, needs a Glassnode-style provider |
| `fear_greed.csv` | CSV | `date, value` | alternative.me or similar |
| `btc_dominance.csv` | CSV | `date, dominance_pct` | Market-cap aggregator |
| `eth_alts_prices.csv` | CSV/Parquet | `date, ticker, close` | For distribution-phase rebalancing (ETH 30% / alts 25%) |

## Data Sources

- BTC price: standard OHLCV feed
- MVRV Z-score: on-chain data provider (not typically available via standard market-data APIs — needs a dedicated source)
- Fear & Greed Index: alternative.me API
- BTC dominance: CoinGecko/CMC-style aggregator

## Validation

Need enough history to span 2+ full 4-year cycles (ideally 8-10+ years) for MVRV/Fear&Greed/dominance — availability may be the limiting factor since on-chain metrics like MVRV typically only go back to when the relevant chain data started being tracked.
