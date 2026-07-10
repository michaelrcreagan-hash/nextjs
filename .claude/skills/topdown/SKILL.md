---
name: topdown
description: "Run the top-down live update: macro regime -> four-sleeve allocation -> theme rotation -> stock funnel -> spot trade setups -> options structures -> macro hedges. Use when the user asks for a live update, current setups, today's trades, allocation targets, or what to buy/hedge right now."
version: 1.0.0
---

# Top-Down Live Update

Runs the full institutional cascade (documented in
`trading/hedgefund/TOPDOWN_WORKFLOW.md`) and delivers the live report.

## Steps

1. **Refresh data if stale.** Check the last bar:
   `tail -1 trading/hedgefund/data/SPY.csv`. If older than the last
   trading day, run `cd trading && python -m hedgefund.fetch_data`
   (needs network; if fetch fails, proceed and note staleness — the
   report stamps per-symbol freshness itself).

2. **Run the pipeline:**
   ```bash
   cd trading && python -m hedgefund.run topdown
   ```
   Options: `--setups N` (default 5), `--no-revisions` (skip the
   analyst-revision fetch when offline — it needs FMP_API_KEY or Yahoo
   reachability and degrades to "—" on failure anyway).

3. **Deliver.** Send the generated report
   (`trading/hedgefund/reports/topdown-YYYY-MM-DD.md`) to the user and
   summarize in chat, leading with: regime state + cycle multiplier,
   the sleeve allocation row, which names qualified (and the single
   biggest reason others were blocked), and the hedge posture.

4. **Interpretation rules** (do not skip when summarizing):
   - Decision order is macro -> theme -> stock -> options; a great
     stock in a REDUCE theme is a pass, not an exception.
   - Setups are quarter-size starters; full size only on follow-through.
   - Options strikes are ATR-derived guides from close-only data —
     tell the user to verify against the live chain before entry.
   - If `no_new_longs` or `invalidated` flags are set, lead with that.

## Machine-readable output

`trading/hedgefund/state/topdown.json` carries the same content as the
report (sleeve weights, position targets, qualified names, setups,
options, hedge signals) for dashboards or follow-on automation.

## Related

- `python -m hedgefund.run daily` — paper-ledger morning run
  (`--deep-dive` adds the LLM analyst layer on top names).
- `strategies/four_sleeve_portfolio/` — research, optimization report,
  and the adopted parameters this pipeline runs on.
