# Data Requirements for ai_bottleneck_stocks

## Required Files

| File | Format | Columns | Notes |
|------|--------|---------|-------|
| `universe.csv` | CSV | `ticker` | Candidate AI-bottleneck stock universe — **not yet defined** |
| `daily_ohlcv.csv` | CSV/Parquet | `timestamp, ticker, open, high, low, close, volume` | Per-ticker daily bars |
| `earnings_dates.csv` | CSV | `ticker, earnings_date` | For the 60-day post-earnings exit rule |
| `four_factor_inputs.csv` | CSV | Unknown | Blocked — factors not yet specified |
| `phase_score_inputs.csv` | CSV | Unknown | Blocked — factors not yet specified |

## Data Sources

- Daily OHLCV / earnings dates: FMP or similar
- Four-factor / phase-score inputs: undefined, pending strategy spec

## Validation

Blocked until the candidate universe and the four-factor/phase-score definitions are provided — see open questions in `DISCOVERY.md`.
