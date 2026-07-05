# Data Requirements for macro_sector_dominance

## Required Files

| File | Format | Columns | Notes |
|------|--------|---------|-------|
| `vix.csv` | CSV | `date, close` | Daily VIX |
| `smh.csv` | CSV | `date, close` | Daily SMH price (for 200d MA) |
| `net_liquidity.csv` | CSV | `date, value` | Formula undefined — see `DISCOVERY.md` open questions |
| `ism.csv` | CSV | `date, value` | Monthly ISM Manufacturing PMI |
| `dxy.csv` | CSV | `date, close` | Daily DXY |
| `sector_etfs.csv` | CSV/Parquet | `date, ticker, close` | Sector universe undefined — see `DISCOVERY.md` |

## Data Sources

- VIX, SMH, DXY, sector ETFs: standard OHLCV feed (FMP or similar)
- ISM Manufacturing PMI: economic data provider
- Net liquidity: Fed/Treasury data, exact formula pending user spec

## Validation

Blocked on: net liquidity formula, regime-score thresholds, and sector universe/rank-combination method — see `DISCOVERY.md` open questions.
