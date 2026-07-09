# Integrated Knowledge Brain Trading Agent
*Signal source: knowledge-group brains → Execution layer: ai_trading_floor / TradingAgents → Portfolio: unified_macro_rotational_framework / four_sleeve_portfolio_architecture*

---

## EXECUTIVE SUMMARY

This agent uses your existing three-tier stack already on disk:

1. **Signal:** knowledge-group brain outputs
2. **Portfolio:** unified_macro_rotational_framework + four_sleeve_portfolio_architecture + haze
3. **Execution:** ai trading floor repo + TETradingAgents components

I’m not creating another runner that reimplements trading logic. I’m wiring live feeds into the exact agents/scaffolds you already installed.

---

## 1. SIGNAL LAYER — KNOWLEDGE BRAIN INPUTS

Use these group brain outputs as trade signals:

| Group | Source | Role | Output |
|---|---|---|---|
| Capital Wars + Fed/FOMC | knowledge-group brains | Macro regime + liquidity regime | Regime score: RISK_ON / MIXED / CAUTION / RISK_OFF; liquidity bias |
| Hyperscalers + NVIDIA/OpenAI + Anthropic | knowledge-group brains | Thematic rotation + capex + AI bottleneck | Theme acceleration score; bottleneck layer ranking; directional bias on SMH/XLK/AI names |
| TipRanks top analysts | knowledge-group brains | Single-name conviction overlay | Buy/Hold/Sell sentiment deltas; price-target revision spreads; analyst-rank filter (top 1–3%) |

### Signal Contract (what the brain outputs must expose)
Use these exact fields so execution layer can consume them without another translation pass:
- `group`
- `score` 0–100
- `mood`: bullish / neutral / bearish
- `delta`: more bullish / more bearish / stable
- `tickers` []
- `themes` []
- `catalysts` []
- `published`

---

## 2. PORTFOLIO RULES — DO NOT REIMPLEMENT

Use the existing strategy docs as the source of truth:

| File | Role |
|---|---|
| `unified_macro_rotational_framework.md` | Regime target, cycle rules, Q3/Q4 rotation |
| `four_sleeve_portfolio_architecture.md` | Position sizing, options overlay, execution |
| `cyclical_overlay_4yr_16yr.md` | 4-year + 16.8-year cycle sizing |
| `sector_rotation_engine.md` | Quarterly ETF rotation order |
| `iae_quick_reference.md` | 100-pt scorer, tiers, ATR rules, 88% Sell Composite |
| `sector_stock_confluence_screen_q3_2026.md` | Stock-level confluence weights |
| `ai_bottleneck_multi_layer_strategy.md` | AI bottleneck tier rules |
| `monte_carlo_summary.json` | Stress-test assumptions |
| `crypto_allocation_addendum.md` | Crypto sleeve limits |
| Pine script | Entry-screen tiers |

### Non-negotiable portfolio rules
 Regime gate: MIXED → CAUTION = 40–45% equity now
- Macro override: only add Q4 exposure after combined cycle signal ≥ +4 or election/post-FOMC confirmation
- Layer overlay: Hyperscaler CapEx + NVIDIA earnings = knowledge brain catalyst with mandatory 25% AI exposure reduction 4 weeks before NVDA earnings
- Theme caps: AI compute ≤ 35%; memory ≤ 20%; networking ≤ 12%; infrastructure ≤ 15%
- Single-name max: Platinum 12%; Gold 8%; Silver 5%; Bronze watchlist only
- Risk per trade: 1–1.5%; options max risk 1% per spread; 0DTE ≤ 5% of options book
- Correlation guard: no NVDA + SMH + SOXL + AMD core at same time; overlap allowed only as reduced sleeve
- Exit rule: 88% Sell Composite ≥3 triggers = scale 50%; ≥4 = full exit; no averaging down

---

## 3. EXECUTION LAYER — USE EXISTING REPOS

Based on the actual files in your installed repos, the correct execution path is:

### 3.1 ai trading floor — equity + options + risk
Path: `C:\Users\mcrea\Ai Agent Trading\ai_trading_floor\`
Use:
- `agents/spot_equity.py` — macro rotation sleeve
- `agents/leaps_execution.py` — options overlay
- `agents/risk_manager.py` — drawdown control
- `agents/phase_scoring.py` — conviction scoring
- `get_quotes.py` — market data
- `requirements.txt` — verify python deps

### 3.2 ai trading floor with backtester — validation
Path: `C:\Users\mcrea\Ai Agent Trading\ai_trading_floor_with_backtester\`
Use:
- `backtesting/runner.py` — backtest candidate portfolios
- `imaw_backtester.py` — trade simulation
- `data/real_providers.py` — live data hooks

### 3.3 TradingAgents — multi-agent research
Path: `C:\Users\mcrea\Ai Agent Trading\TradingAgents\`
Use:
- `cli/main.py` — existing multi-agent workflow
- Do not override config. Use your `.env` for keys only.
- Use this as the research layer that produces analyst-style summaries from knowledge brain content

### 3.4 Trading floor scaffold
Path: `C:\Users\mcrea\Ai Agent Trading\trading-floor\`
Use only as scaffold; actual logic lives in the agents above.

---

## 4. INTEGRATION FLOW

```text
knowledge-group brains
    ↓ JSON report + weekly markdown
Expert filter:
- Fed/FOMC + Capital Wars → regime + liquidity
- Hyperscalers/NVIDIA/Anthropic → AI theme + capex signals
- TipRanks → analyst revision top 1–3% names


```

`group_brain_report.json`
→ runs as a cron job or exported as JSON
→ agent planner reduces to 1–3 tickers per theme

Then use ai_trading_floor agents to execute only when regime + tier + ATR + cycle all align.

---

## 5. AUTOMATED AGENT PIPELINE

### Step 1: Knowledge brain scraper
Path: `C:\Users\mcrea\AppData\Local\hermes\skills\knowledge-group-brains`
Run daily:
- `python knowledge_group_brain_scraper.py`
- Output: `group_brain_report.json`, `group_brain_weekly_report.md`

### Step 2: Signal extractor
Create `C:\Users\mcrea\AppData\Local\hermes\skills\knowledge-group-brains\scripts\extract_signals.py`

Read `group_brain_report.json` and output:

```json
{
  "regime": {
    "score": 64,
    "mood": "Neutral",
    "delta": "stable",
    "trigger": "Fed/FOMC/Capital Wars"
  },
  "themes": [
    {"theme": "AI Infrastructure", "score": 97, "direction": "bullish", "tickers": ["VRT", "COHR", "ANET"]},
    {"theme": "AI Compute", "score": 50, "direction": "neutral", "tickers": ["NVDA", "AVGO"]}
  ],
  "single_name": [
    {"ticker": "VRT", "score": 64, "direction": "bullish", "catalyst": "Hyperscaler capex upbeat"},
    {"ticker": "NVDA", "score": 50, "direction": "neutral", "delta": "more bearish"}
  ],
  "alerts": [
    "NVDA earnings within 4 weeks: reduce SMH 25% per framework",
    "FOMC within 2 weeks: reduce size 30% per regime rules"
  ]
}
```

### Step 3: Decision engine
Create `C:\Users\mcrea\Ai Agent Trading\integrated_decision_engine.py`

Inputs:
- `group_brain_report.json`
- `unified_macro_rotational_framework.md` rules
- `four_sleeve_portfolio_architecture.md` rules
- `iae_quick_reference.md` rules
- Live price data via `ai_trading_floor/get_quotes.py`

Logic:
1. Regime gate: if RISK_OFF → no new longs; if MIXED/CAUTION → 40–45% equity cap
2. Seasonal/c