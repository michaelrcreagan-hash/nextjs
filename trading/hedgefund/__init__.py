"""Agentic hedge fund: mechanical layer.

Regime engine, outperformer screener, strategy rules, backtester,
walk-forward optimizer, and the orchestrator that ties them to the
TradingAgents LLM graph. Distilled from the two master strategy docs
(AI Infrastructure Hedge Fund OS + Institutional Top-Down System).

All heavy computation is pure pandas/numpy over cached CSVs in
``hedgefund/data`` — no network access at backtest time.
"""

__version__ = "0.1.0"
