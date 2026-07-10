# AI Hedge Fund v7.0

**Unified Top-Down Trading System**: Macro Regime → Composite Scoring → Signal Detection → Options Sizing → Macro Hedges

Built from 48 hours of iterative research: 572 indicator combinations tested, 4,576 backtest runs, 66-stock AI bottleneck universe, 4-tier conviction system, 6-module composite engine, and 3 Pine Script v6 strategies.

## Quick Start

```bash
# Full scan (all 7 phases)
python main.py --scan

# Deep dive single ticker
python main.py --ticker NVDA

# Specific scans
python main.py --breakout
python main.py --pullback
python main.py --options
python main.py --hedge

# Save to JSON
python main.py --scan --output report.json
```

## Installation

```bash
git clone <repo>
cd ai-hedge-fund-v7
pip install yfinance numpy pandas
python main.py --scan
```

## What It Does

1. **Detects Macro Regime** (RISK-ON/MIXED/CAUTION/RISK-OFF) from VIX, SMH trend, market breadth, BTC, and analyst revision velocity
2. **Scores 66 Stocks** with 6 weighted modules including the proprietary Module F (Analyst Revision Velocity)
3. **Finds Breakouts** using the backtest-proven ATR+RSI combination (Composite 23.6, -0.9% max drawdown)
4. **Finds Pullbacks** using Fib 61.8% + Keltner Lower (74% win rate, -0.5% max drawdown)
5. **Builds Options Trades** with IV-rank-based strategy selection and VIX-based position sizing
6. **Constructs Macro Hedges** with regime-appropriate allocation to VIXY, TLT, GLD, SQQQ
7. **Computes Technical Confluence** across 8 IAE layers for additional confirmation

## TradingView Integration

Copy any `.pine` file from `pinescript/` into TradingView Pine Editor (mobile-compatible, v6):

- **V7_BREAKOUT_ATR_RSI.pine** — Pure breakout strategy
- **V7_PULLBACK_FIB_KELTNER.pine** — Pure pullback strategy
- **V7_COMBINED_STRATEGY.pine** — Auto-selecting combined strategy

## Backtest Results

| Strategy | Best Combo | Composite | Max DD | Win Rate |
|----------|-----------|-----------|--------|----------|
| Breakout | ATR + RSI | 23.6 | -0.9% | 62% |
| Pullback | Fib 61.8% + Keltner | 17.7 | -0.5% | 74% |

## Architecture

```
Phase 1: regime.py       Macro regime detection
Phase 2: composite.py    6-module scoring (A-F)
Phase 3: breakout.py     ATR+RSI signals
Phase 4: pullback.py     Fib+Keltner signals
Phase 5: confluence.py   8-layer IAE scoring
Phase 6: options.py      IV-rank options sizing
Phase 7: hedge.py        Macro hedge construction
         scanner.py      Orchestrator
```

## License

MIT
