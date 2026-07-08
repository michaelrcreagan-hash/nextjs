# Strategy Discovery: four_sleeve_portfolio

**Date:** 2026-07-08
**Phase:** Discovery Complete (auto — sourced from
`trading/hedgefund/notes/four_sleeve_portfolio_architecture.md` and the
completed mechanical backtest in
`trading/hedgefund/monte_carlo/SLEEVE_BACKTEST_REPORT.md`)
**Engine:** pandas
**Project Type:** indicator (regime-weighted multi-sleeve allocation)

---

## Core Hypothesis

A four-sleeve portfolio — Macro Rotation (30-40%), Income/Hedge (20-25%),
Innovation (20-30%), Options overlay (10-15%) — rebalanced by a macro
regime matrix (RISK-ON/MIXED/CAUTION/RISK-OFF), a 4yr x 16.8yr x seasonal
cycle overlay, and a drawdown rulebook, compounds at 50-80% annualized
with <25% drawdowns by concentrating the return engine (innovation) while
the income sleeve and cash buffer absorb crashes.

### Mechanical implementation already validated
`trading/hedgefund/sleeves.py` + `monte_carlo/sleeve_analysis.py`.
Realized (all triggers, 10 bps/side): **32.6% CAGR / -17.3% DD
(2023-2026)**, **9.0% CAGR / -23.0% DD (2010-2023)**. The 50-80% target
only appears in innovation-supercycle conditions.

### Open questions for research
1. Is each sleeve's edge documented and durable, or already arbitraged?
2. What do existing implementations do differently/better per sleeve?
3. Which department deserves optimization first (the backtest says the
   trend gate is the weakest and selection is the alpha source)?
4. What failure modes does the literature warn about that our two test
   windows don't contain?

## Kill Criteria (from discovery)
- Portfolio drawdown >25% with triggers active
- 2010-2023-style regime returning while positioned for supercycle
- Innovation sleeve edge fully explained by beta after costs
