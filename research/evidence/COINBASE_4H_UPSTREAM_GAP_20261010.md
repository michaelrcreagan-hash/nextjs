# Coinbase 4H Historical Gap — Native Source Reconciliation

Date audited: **2026-10-10**.
Base archive: `crypto-prop-strategies/data/h4/`, eight Coinbase/USD pairs, 6,567 rows per pair.
Classification: **BLOCKED_UPSTREAM**; **24 source observations still missing**.

## Exact gaps

| Bar start (UTC) | Markets affected | Available equivalent source-accurate replacement |
| --- | --- | --- |
| 2025-10-25 16:00 | BTC, ETH, SOL, AVAX, DOGE, LINK, LTC, XRP | **None** |
| 2026-05-08 00:00 | same eight | **None** |
| 2026-05-08 04:00 | same eight | **None** |

## Verified native source checks

GitHub Actions [run 38070858049](https://github.com/michaelrcreagan-hash/nextjs/actions/runs/38070858049) queried public Coinbase Exchange `/products/{symbol}-USD/candles` with **hourly** granularity. For each of eight markets, the relevant 2025 12-hour window returned only **8 hourly records**, and the relevant 2026 16-hour window returned **12 records**. All calls succeeded, while adjacent available bars matched archived source OHLCV.

A second [run 38071192917](https://github.com/michaelrcreagan-hash/nextjs/actions/runs/38071192917) checked the same windows at Coinbase's native **five-minute** granularity and likewise could not assemble any complete 4-hour bar for the 24 missing observations. The public API responses succeeded; source-response hashes and attempted aggregation are preserved in the Actions artifact `coinbase-gap-recovery-receipt` (7-day retention). The associated code reproduces the checks.

**Result: zero data bars recovered, 24 confirmed missing.** These 24 are not price-interpolation candidates. Do not silently substitute Binance, Alpaca or other venue data into Coinbase-derived series. Preserve missingness masks / skip trades that require those windows. If original Coinbase trade archives with complete coverage are ever acquired, run source-specific revalidation.

## Controls and limits

- All eight stored archives are subject to future source-as-of, listing-universe, resampling and fee validation.
- A clean source reconciliation does **not** certify a strategy, a prop firm's intrabar drawdown replay or execution accuracy.
- The canonical harness must import only safe provenance/evidence and mark these exact instrument-timestamps `BLOCKED_DATA`; no altered trade or return series are produced.
- Public Github PRs must never include historical private account files, brokerage positions or cost bases.
