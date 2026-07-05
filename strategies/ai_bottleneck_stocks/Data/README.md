# Data Requirements for ai_bottleneck_stocks

## Required Files

| File | Format | Columns | Status |
|------|--------|---------|--------|
| `universe.csv` | CSV | `ticker, layer` | ✅ Defined — ~52 tickers across 9 bottleneck layers, see file |
| `daily_ohlcv.csv` | CSV/Parquet | `timestamp, ticker, open, high, low, close, volume` | ✅ Reachable via FMP (verified live) |
| `earnings_dates.csv` | CSV | `ticker, earnings_date` | Likely reachable via FMP calendar, not yet tested |
| `four_factor_inputs.csv` | CSV | RS vs SMH/SPX + technicals reachable via FMP; earnings-revision momentum + scarcity/moat need a paid source | ⚠️ Partial |
| `phase_score_inputs.csv` | CSV | Momentum sub-factor reachable via FMP; capex velocity, supply tightness, analyst upgrades need a paid/manual source | ⚠️ Partial |

## Data Sources

- Daily OHLCV / technicals: FMP (confirmed reachable this session)
- Earnings-revision momentum: Zacks/Visible Alpha (paid, not connected)
- Options flow (for sell composite): Unusual Whales (paid, not connected)
- Scarcity/moat + supply-chain data: TrendForce/Everstream/earnings transcripts (not connected, largely qualitative)

## Validation

Universe and scoring methodology are resolved (see `DISCOVERY.md`) — no longer blocked on undefined formulas. Remaining gap is data-source access for the paid-feed sub-factors; see open questions in `DISCOVERY.md` for how to proceed (manual placeholder vs. paid subscription vs. rescaled partial score).
