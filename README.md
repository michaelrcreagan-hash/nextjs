# Next.js Trading Research Dashboard — Legacy Research Archive

This repository contains the Next.js dashboard **and earlier historical research**.
It is a *source archive*, not the canonical strategy-validation or trading-execution authority.

**Canonical research system:** [agentic-trading-research-harness](https://github.com/michaelrcreagan-hash/agentic-trading-research-harness). That project's `contracts/AUTHORITY_MODEL.md`, policies, data contracts, reviewed strategy registry and independent-validation gates govern any use of legacy records.

## Historical market data available here

| Path | Actual data present | Research limitation |
| --- | --- | --- |
| `ai-bottleneck-alpha/data/prices/` | Daily equity/ETF OHLCV with adjusted close | Current selected names; historical index/sector membership not established |
| `ai-bottleneck-alpha/data/fundamentals/raw/` | Company-level SEC XBRL extracts, not uniformly populated | File/acceptance-date and original-vs-restated logic needs independent audit |
| `crypto-prop-strategies/data/h4/` | Eight Coinbase-derived 4H spot markets | Derived by resampling 1H candles, not intrabar prop execution/tick evidence |
| `trading/hedgefund/data_long/` | Close/volume daily time series across AI, ETF, metals/energy, quantum and crypto-related symbols | Historical ticker identities and vendor vintage not proven PIT |
| `strategies/hermes_agent/Data/futures/` | Metadata describing historical continuous futures | CSV data is **ignored by Git and not present in GitHub checkout**; metadata is not the data |
| `strategies/hermes_agent/Data/real_accounts/` | Historical account snapshots, **sensitive** | Never publish/import as current account state or certify tax lots |

**Do not assume results in `ai-bottleneck-alpha/STRATEGY_REPORT.md`,
`crypto-prop-strategies/STRATEGY_REPORT.md`, or `trading/hedgefund/REPORT.md` are currently validated strategies.** They describe older experiments, different universes/assumptions and development windows. Existing canonical NO_EDGE/FAILED_REVIEW decisions prevail until a newly registered, independently validated experiment establishes otherwise.

## Reproducible source inventory

Run the standard-library-only auditor from a checkout:

```bash
python research/audit_legacy_sources.py --root . --output /tmp/nextjs-source-inventory.json
python -m unittest discover -s research/tests -v
```

The auditor visits only three explicit historical market-data folders, reports file SHA-256 hashes, row counts, earliest/latest bar, OHLC/timestamp anomalies and known evidence limitations. **It does not load account snapshots.** Its results are research ingestion candidates, not proof of PIT membership, trade executions or strategy edge.

For import into the canonical harness, freeze this repository's commit SHA, run the auditor, independently compare overlapping data, verify rights/availability, pin actual market data and preserve original immutable receipts. The canonical harness should **reference or copy only authorized verified market data**, not strategies' prior promotional summaries or any holdings files.

## Data privacy

This public repository historically committed account-related artifacts. An updated `.gitignore` will prevent most new untracked account files from being added inadvertently, **but cannot remove already committed files from Git history**. Before treating the repository as a safe public archive, inspect tracked files, arrange private secure storage, remove sensitive files from HEAD and plan an owner-approved history rewrite/mirror migration if needed. Check for credentials in history and revoke exposed secrets. Do not publish private portfolio details to actions logs or public PRs.

## Website development

```bash
npm install
npm run dev
```

The Next.js site is separate from deterministic research scripts. Changes to live dashboards and any scheduled jobs need their own review; the source auditor never places trades or changes portfolio state.
