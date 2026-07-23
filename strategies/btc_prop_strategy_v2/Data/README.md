# Data Requirements for btc_prop_strategy_v2

## Required Files

| File | Format | Columns | Notes |
|------|--------|---------|-------|
| btc_ohlcv_1h.parquet | Parquet | timestamp, open, high, low, close, volume | Primary Range Hunter timeframe |
| btc_ohlcv_4h.parquet | Parquet | timestamp, open, high, low, close, volume | Trend Rider entry / Funding Farmer / DCB overlay |
| btc_ohlcv_1d.parquet | Parquet | timestamp, open, high, low, close, volume | Trend Rider trend timeframe / on-chain daily alignment |
| btc_ohlcv_1w.parquet | Parquet | timestamp, open, high, low, close, volume | 200WMA, cycle position |
| funding_oi.parquet | Parquet | timestamp, funding_rate, open_interest | Blocked in this sandbox's network egress (see DISCOVERY.md) |
| cvd_spot_futures.parquet | Parquet | timestamp, spot_cvd, futures_cvd | Not sourced as ready dataset -- build-it-yourself trade-tape aggregation |
| macro.parquet | Parquet | timestamp, dxy, m2_yoy, real_yield_10y | DXY/M2/yields |
| onchain.parquet | Parquet | timestamp, mvrv_z, sopr, puell, rhodl, lth_supply_pct, exchange_reserves | Not sourced -- needs Glassnode/CryptoQuant-class connector |
| coinglass.parquet | Parquet | timestamp, liq_heatmap, net_long_pct, large_orders | Not sourced -- needs Coinglass-class connector |
| etf_flows.parquet | Parquet | date, net_flow_usd | Farside Investors per source docs, untested this session |
| macro_calendar.csv | CSV | date, event_type, surprise | FOMC/CPI/NFP dates -- Tipranks confirmed reachable |

## Data Sources

- BTC OHLCV: FMP `crypto` connector (confirmed reachable this session)
- Macro calendar: Tipranks `get_economic_calendar` (confirmed reachable per crypto_algo_trading prior research)
- DXY/M2/yields: AlphaVantage / FMP `economics`
- Funding/OI: Hyperliquid public `info` endpoint -- free/keyless but blocked from this sandbox's egress (shared blocker with crypto_algo_trading)
- Spot/futures CVD, on-chain valuation, Coinglass microstructure: no connector confirmed reachable this session -- flagged as open research questions in DISCOVERY.md
- ETF flows: Farside Investors (free, per source docs) -- untested

## Validation

Run this to validate your data:
```python
# Validation script will be generated in /cbt:build
```
