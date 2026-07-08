# Pending — Omega analyst upgrade

`fundamentals_analyst.py`, `market_analyst.py`, and `news_analyst.py` in this
folder are newer versions uploaded from the local Hermes/Omega build. They
are **not wired into the live graph** — dropping them straight into
`agents/analysts/` would break the currently-working deep-dive pipeline,
because they import four symbols that don't exist yet in this repo's
`agents/utils/agent_utils.py`:

- `get_strategy_context_from_state`
- `rank_omega_theme_stocks`
- `scan_omega_defined_risk_options`
- `score_omega_theme_rotation`

These are presumably backed by two files that were listed as part of this
upload but never arrived:

- `agents/utils/agent_utils.py` (an updated version — the current one only
  re-exports data tools + instrument/language helpers, no Omega wiring)
- `agents/utils/options_scanner_tools.py`
- `agents/utils/theme_rotation_tools.py`
- `graph/trading_graph.py` (likely needs updating too, to route the new
  `strategies/` package + `knowledge_brain_orchestrator.py` into the graph)

Once those four files are uploaded, move the three analysts here into
`agents/analysts/` (replacing the current versions) and delete this folder.
