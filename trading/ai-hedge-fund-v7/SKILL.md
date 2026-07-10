# AI Hedge Fund v7.0 — Comprehensive Trading System

## Overview

Top-down quantitative trading system integrating macro regime detection, 6-module composite scoring, optimized breakout/pullback signals, options sizing, and macro hedging across a 66-stock AI bottleneck universe.

**Architecture**: 7-Phase Pipeline  
**Backtested**: 572 indicator combinations, 4,576 backtest runs  
**Winners**: ATR+RSI breakout (Comp 23.6, DD -0.9%), Fib 61.8%+Keltner pullback (74% WR)

## Quick Start

```bash
python main.py --scan              # Full top-down scan
python main.py --ticker NVDA       # Single ticker deep dive
python main.py --breakout          # Breakout signals only
python main.py --pullback          # Pullback signals only
python main.py --options           # Options trades
python main.py --hedge             # Macro hedges
python main.py --output report.json
```

## 7-Phase Pipeline

### Phase 1: Macro Regime Detection
- **Signals**: VIX, SMH 200DMA, breadth %, BTC trend, Module F avg
- **States**: RISK-ON / MIXED / CAUTION / RISK-OFF
- **Output**: 4-sleeve allocation (Macro/Income/Innovation/Options/Cash)

### Phase 2: 6-Module Composite Scoring
| Module | Weight | Description |
|--------|--------|-------------|
| A: Hyperscaler | 20% | QQQ 20-day ROC proxy |
| B: Earnings | 20% | Company ROC + volume trend |
| C: Peer Val | 15% | Relative to AI layer peers |
| D: Technical | 15% | Multi-timeframe ROC (5d/20d/63d) |
| E: ATR | 10% | Distance from 21 EMA in ATR units |
| F: Revision | 20% | Analyst revision velocity |

**Interpretation**: >65 = strong opportunity, 50-65 = moderate, <40 = avoid

### Phase 3: Breakout Signals (ATR + RSI)
- **Entry**: ATR% > 1.3x 20-day avg AND RSI 50-70
- **Stop**: 2x ATR below entry
- **Target**: 3x ATR above entry
- **Stats**: Composite 23.6, MaxDD -0.9%, Expectancy +$3,265

### Phase 4: Pullback Signals (Fib 61.8% + Keltner Lower)
- **Entry**: Price within 4% of Fib 61.8% AND at/below Keltner Lower
- **Stop**: Below Fib 78.6% or 1.5x ATR
- **Target**: Fib 38.2% retracement
- **Stats**: Composite 17.7, MaxDD -0.5%, Win Rate 74%

### Phase 5: Options Sizing
| IV Rank | Strategy | Direction |
|---------|----------|-----------|
| >50% | Credit Spread | Sell premium |
| 30-50% | Debit Spread | Defined risk directional |
| <30% + breakout | Long Option | Long vega |
| <30% + pullback | PMCC | LEAP + weekly short |

**Sizing**: VIX-based (3% RISK-ON down to 0.5% RISK-OFF) x composite multiplier

### Phase 6: Macro Hedges
| Regime | Hedge % | Cash % |
|--------|---------|--------|
| RISK-ON | 5% | 0% |
| MIXED | 15% | 5% |
| CAUTION | 30% | 20% |
| RISK-OFF | 45% | 45% |

**Hedge Book**: VIXY (30%), TLT (25%), GLD (25%), SQQQ (20%)

### Phase 7: IAE Confluence
8-layer scoring: Trend (18%), Momentum (15%), Volatility (12%), Volume (12%), Mean Reversion (10%), Strength (13%), Breadth (12%), Execution (8%)

## Stock Universe (66 Tickers)

**Tier 1**: NVDA, AVGO, ASML, AMAT, KLAC, LRCX  
**Tier 2**: TSM, SNPS, CDNS, MRVL, MPWR, ONTO, UCTT, TER  
**Tier 3**: NBIS, GEV, DDOG, PANW, AXON, RBRK, SMCI, CRWD  
**Tier 4**: OKLO, BWXT, CCJ, LEU, HOOD, CIFR, WULF, IREN, MSTR, AIPO, MAGS, GRID  
**ETFs**: SMH, SOXL, XLU, XLV, XLI, XBI, QQQ, XLK, PAVE, ICLN, WGMI  

## Pine Script v6 Indicators

Three TradingView strategies included in `pinescript/`:
- `V7_BREAKOUT_ATR_RSI.pine` — Breakout strategy with dashboard
- `V7_PULLBACK_FIB_KELTNER.pine` — Pullback strategy with dashboard
- `V7_COMBINED_STRATEGY.pine` — Auto-selecting combined strategy

All mobile-compatible (<=32 char lines, no continuations, string literal groups).

## Python API

```python
from src.engine.scanner import LiveScanner

scanner = LiveScanner()
report = scanner.full_scan(limit=15)
scanner.print_report()
scanner.to_json("scan_report.json")

# Individual engines
from src.engine.regime import detect_regime, fetch_regime_data
from src.engine.composite import CompositeScorer
from src.engine.breakout import atr_rsi_breakout
from src.engine.pullback import fib_keltner_pullback
from src.engine.options import build_options_trade
from src.engine.hedge import build_hedge_portfolio
```

## Key Research Findings

1. **ATR is the foundation** — appears in 9 of top 10 breakout combos
2. **Fibonacci is the foundation** — appears in ALL top 10 pullback combos
3. **Size-2 beats size-3** — simpler "2 of 2" with right indicators outperforms "2 of 3"
4. **OBV+Keltner ranked ~15th** — ATR alone more predictive than OBV
5. **MFI underperforms Fib** — price levels > oscillators for pullback timing
6. **Best size-3 breakout**: ADX-ATR-EMA (Comp 15.8, CAGR +1.2%, 71 trades)

## Module F: Revision Velocity Formula
```
velocity = sum(rating_change * weight)
weight = success_rate * recency_decay
decay = 0.5^(age_days / 30)
window = 120 days
```

## Dependencies
- yfinance, numpy, pandas
- Python 3.10+

## File Structure
```
ai-hedge-fund-v7/
  main.py                 # CLI entry point
  config.yaml             # All parameters
  src/engine/
    regime.py             # Phase 1: Macro regime
    composite.py          # Phase 2: 6-module scoring
    breakout.py           # Phase 3: Breakout signals
    pullback.py           # Phase 4: Pullback signals
    confluence.py         # Phase 5: IAE confluence
    options.py            # Phase 6: Options sizing
    hedge.py              # Phase 7: Macro hedges
    scanner.py            # Orchestrator
    universe.py           # 66-ticker universe
  pinescript/
    V7_BREAKOUT_ATR_RSI.pine
    V7_PULLBACK_FIB_KELTNER.pine
    V7_COMBINED_STRATEGY.pine
```
