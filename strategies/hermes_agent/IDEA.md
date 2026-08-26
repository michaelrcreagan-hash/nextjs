# Strategy Idea: hermes_agent

> Use this file to capture your initial thoughts about the strategy.
> This will be used as input for the /cbt:discover phase.

## The Idea

*What is the core idea of this strategy? What are you trying to exploit?*

Formalize the live "Hermes" multi-domain agent bus (already running outside
this repo, cron-scheduled via `cron_config.json`) into a CBT-managed,
mechanically backtestable strategy. Hermes runs a "Head Trader" synthesis
agent over ~15-20 domain agents on a shared state bus (`state.json`):
macro (FRED), fundamental/analyst_sentiment/earnings/catalysts (FMP),
technical, options (Alpaca + Alpha Vantage fallback), portfolio_allocation
/ portfolio_rebalancing (Alpaca + Fidelity), hedging, news, crypto_perps
(Hyperliquid/OKX/Coinbase — funding, OI, CVD, orderbook imbalance), and a
separate BTC daily-bias model blending ETF flows / funding / OI / CVD /
exchange netflow / whale alerts / CME basis into a weighted composite score
with regime guards (RSI extremes, Fear&Greed). Output is daily/intraday
trade setups with entry/stop/target/RR/probability/profit-factor estimates
and paper-order specs, gated by a regime label (RISK-ON/MIXED/RISK-OFF)
and a portfolio sizing multiplier.

## Why It Should Work

*What is the theoretical or empirical basis for this edge?*

Unclear yet — this is exactly what /cbt:discover and /cbt:research need to
pin down. Honest starting caveats surfaced in the uploaded state:
- The BTC ML ensemble's own rolling backtest reports 0.48 directional
  accuracy / 0.46 AUC — no better than a coin flip. `btc_bias_report.json`
  already downgrades to "transparent rule-weighted features instead."
- Many domain agents are currently returning zeroed/empty output
  (`portfolio_value: 0`, `fundamentals: 0`, `technicals: 0`,
  `crypto_perps_hyperliquid` all-zero) — either a fresh deployment or a
  wiring problem. Treat every "OK" status in `team_brief.json` /
  `head_trader_brief.json` as "ran without error," not "produced a
  validated signal."
- **Account roles, confirmed with the user 2026-08-26:** Alpaca ($16,431
  equity) is a **paper/testing sandbox** for validating strategies before
  they touch real capital — it is not part of the $1.5M goal math. The
  **real portfolio** toward the $100k+$3k/mo → $1.5M-by-2029 target lives
  across **Fidelity** (the margin/options account trading NVDA/IBIT/TLT
  calls & puts, leveraged ETFs SOXL/TQQQ, thematic ETFs URNM/SLV/SPHB/
  JEPI), **Coinbase**, **crypto perps** (Hyperliquid/OKX), and a
  **retirement account**. hermes_agent's backtest/paper-validation loop
  should run in the Alpaca-equivalent sandbox; live sizing decisions it
  produces are meant to route to the real accounts.
- Cron jobs also reference a `prop_firm_balance` / `4%/mo target` track —
  confirm during discovery whether that's a fourth, fully separate pool
  (this repo's `strategies/crypto_algo_trading` already has
  `prop_firm.enabled: true`) or folded into one of the above.
- **Retirement account** appears in the confirmed account list but has no
  uploaded data yet (no positions/transactions snapshot) — flag as a data
  gap for discovery.

## Entry Logic (rough)

*When do you want to enter trades?*

Head Trader synthesis: regime label (macro composite) sets a sizing
multiplier; per-symbol setups need F/T/S/M sub-scores (Fundamental/
Technical/Sentiment/Macro, 0-10 each per `trade_setups.json` /
`crypto_squeeze_report.json`) above a confluence threshold, risk/reward
computed from ATR-style stop/target, existing-position conflict check
before sizing (`position_check.allocatable_bp`).

## Exit Logic (rough)

*When do you want to exit trades?*

Not yet specified in the uploaded state — stop_loss/take_profit levels are
generated per setup but no trailing/scale-out rule is visible yet. Compare
against this repo's existing sell-composite / trailing-stop-by-phase logic
in `trading/hedgefund/sell_composite.py` and `strategies/ai_bottleneck_stocks`
before reinventing one.

## Data Needed

*What data do you think you'll need?*

Already uploaded this session (in `strategies/hermes_agent/Data/` once
copied over, or referenced from `/root/.claude/uploads/...`):
`btc_historical_data.csv` (2024-07-23 → date, BTC/IBIT/FBTC/ARKB/BITB/ETHA/
MSTR/ETH/SOL/SPY/TLT daily closes), `btc_ml_features.csv` (engineered
features + `target` column — looks ML-ready but inherits the 0.48-accuracy
caveat above), plus point-in-time snapshots (`team_brief.json`,
`head_trader_brief.json`, `crypto_squeeze_report.json`, `trade_setups.json`,
`btc_bias_report.json`, `state.json` bus dump, live Fidelity/Alpaca
transaction logs) that describe the *live system's shape* but are not
historical time series — they can't be backtested directly. Discovery needs
to separate "data to replay mechanically" from "live wiring to describe."

## Notes

*Any other thoughts, references, or considerations?*

**Confirmed with the user 2026-08-26: hermes_agent is a new, standalone
mechanical strategy** — not an orchestration layer over the existing
four-sleeve/AI-bottleneck/crypto desks, and not a live-ops-only project.
It gets its own discovery → research → EDA → config → plan → build →
iterate cycle, backtested and validated on its own merits like any other
`strategies/*` project in this repo. That said, discovery should still
name explicitly what (if anything) it borrows conceptually from the
existing validated desks (regime gating, sell-composite exits, sizing
rules) versus what's genuinely new to Hermes's own F/T/S/M confluence-
score + multi-domain-agent design, so overlap is a deliberate choice, not
an accident.

---

*When ready, run `/cbt:discover` to formalize this into a complete strategy specification.*
