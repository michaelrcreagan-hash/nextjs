# Next.js Legacy Research Data — Audit Findings
**Audit date:** October 10, 2026  
**Baseline source branch:** `main` at `e6232b7e5f06d567c7408407c9f39df1563bcfde`  
**Validation workflow:** [Legacy research data audit](https://github.com/michaelrcreagan-hash/nextjs/actions/runs/38069091582)  
**Evidence:** machine-readable `nextjs-research-price-inventory` artifact from the workflow. 

## Audited market data (market records only)

| Source | CSV files | Rows | Structural check | Coverage across files |
| --- | ---: | ---: | --- | --- |
| `ai-bottleneck-alpha/data/prices` | 65 | 81,504 | 65 pass; 0 rejected | Earliest 2021-06-01, latest 2026-08-26 |
| `crypto-prop-strategies/data/h4` | 8 | 52,536 | 8 pass; 0 rejected; missing bars | 2023-08-28 through 2026-08-27 |
| `trading/hedgefund/data_long` | 66 | 228,734 | 66 pass; 0 rejected | Earliest 2009-01-02, latest 2026-07-10 |
| **Total** | **139** | **362,774** | **139 structurally parseable** | NOT PIT strategy certification |

The audit confirms CSV structure, ordered timestamps, valid numerical OHLC/volume values and file SHA-256 signatures. This **does not** verify original vendor data, historical symbol identity, corporate-action adjustment, point-in-time eligible universe, trade execution, historical available information or strategy edge.

## Missing 4H Coinbase-derived bars — exact observations

Every one of the eight crypto files (BTC, ETH, SOL, XRP, DOGE, LINK, AVAX, LTC) has the same two discontinuities:

| Window (UTC) | Missing expected bar timestamps | Missing per symbol |
| --- | --- | ---: |
| 2025-10-25 12:00 -> 20:00 | 2025-10-25 16:00 | 1 |
| 2026-05-07 20:00 -> 2026-05-08 08:00 | 2026-05-08 00:00, 04:00 | 2 |

**Missing total:** 3 per symbol, 24 across eight symbols.

These are *missing intervals*, not zero-volume candles. Check Coinbase Exchange's original interval records or an authorized matching-venue archive, preserve upstream timestamps, and insert only after independently validating any recovered bars. Do not forward-fill OHLC/volume or use synthetic bars in an execution replay. Keep legacy originals immutable and place repaired derived series in a separately named dataset with an append-only receipt.

The Coinbase series derives from **1H** candles resampled to 4H using `min_hours_per_bar = 3`. Even after filling gaps, it is inadequate for certifying a prop-firm intrabar stop/drawdown sequence.

## Futures

`strategies/hermes_agent/Data/futures/meta_1h.json` and `meta_1d.json` describe Yahoo continuous contracts and historical date ranges, but `strategies/*/Data/futures/*.csv` is ignored by Git; **zero actual futures CSV files** were present in the audited GitHub checkout. Source metadata must not be labeled recovered historical bars. Recovery requires an authorized original host backup or a separate independently sourced exchange contract dataset.

## Research governance and account boundaries

Historical backtests in this repository predate canonical validation. Treat claimed optimal returns/prop recommendations as *unverified legacy hypothesis outputs*, not current champions. The canonical harness's published negative verdicts and frozen holdouts must not be modified.

This is a PUBLIC repository with already tracked historical account-related files. The auditor explicitly does NOT inspect account data. Updated ignore patterns affect newly added untracked files only. Removing sensitive tracked content from the HEAD and public Git history requires a separately planned migration/history remediation; do not print account values or private account identifiers in public action logs or PRs.

## Import gate for Hermes

1. Pin the source repository SHA and use the audit workflow's immutable SHA256 manifests.
2. For each eligible data file, independently recompute SHA256 and validate timestamps and original source.
3. Quarantine all 4H windows with missing source bars until explicit recovery or censoring rules are registered.
4. Validate duplicate/timezone/adjustments, listing and delisting dates, split/dividend histories and PIT exposure.
5. Record which files are already present in `agentic-trading-research-harness`; do not duplicate them.
6. Place verified market observations in canonical data storage under new dataset versions and frozen contracts; preserve source bytes and traceability.
7. Do not import personal account snapshots or old promotion decisions.
