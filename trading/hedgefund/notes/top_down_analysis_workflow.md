# Top-Down Analysis Workflow — 4-Sleeve Portfolio
*Signal → Regime → Theme → Security → Execution*
*Integrates: knowledge-group brains + macro/cyclical framework + four-sleeve architecture + ai_trading_floor execution*

---

## WORKFLOW MAP

```
TIER 1 — MACRO/LIQUIDITY (Knowledge Brain: Capital Wars + Fed/FOMC)
    ↓ outputs: regime score, liquidity bias, kill switches
    ↓
TIER 2 — THEME ROTATION (Knowledge Brain: Hyperscalers + NVIDIA/OpenAI + Anthropic)
    ↓ outputs: theme acceleration scores, bottleneck layer ranking, sector ETF bias
    ↓
TIER 3 — SINGLE-NAME CONVICTION (Knowledge Brain: TipRanks + strategy docs confluence)
    ↓ outputs: tiered names (Platinum/Gold/Silver), entry zones, stops, targets
    ↓
TIER 4 — EXECUTION (ai_trading_floor agents + integrated_decision_engine campaigns)
    ↓ outputs: trade tickets, position sizes, options overlays, hedge book
```

---

## INPUTS (run once daily, before market open)

| Source | File/Key | Load Method |
|---|---|---|
| Knowledge brains | `knowledge-group-brains/output/group_brain_report.json` | `knowledge_group_brain_scraper.py` |
| Strategy docs | `unified_macro_rotational_framework.md` | Static rules |
| | `four_sleeve_portfolio_architecture.md` | Static rules |
| | `cyclical_overlay_4yr_16yr.md` | Static rules |
| | `sector_rotation_engine.md` | Static rules |
| | `iae_quick_reference.md` | Static rules |
| | `ai_bottleneck_multi_layer_strategy.md` | Static rules |
| | `monte_carlo_summary.json` | Stress-test overlay |
| | `crypto_allocation_addendum.md` | Crypto sleeve rules |
| Live data | `ai_trading_floor/get_quotes.py` | yfinance/API |
| Campaigns | `knowledge-group-brains/output/integrated_campaigns.json` | `integrated_decision_engine.py` |
| Signals | `knowledge-group-brains/output/signals.json` | `signal_extractor.py` |

---

## TIER 1 — MACRO/LIQUIDITY GATE

**Input:** Capital Wars + Fed/FOMC knowledge brain scores

**Logic:**
```
regime_score = avg(capital_wars.score, fed_fomc.score)  # 0-100

IF regime_score >= 66:
    regime = "RISK_ON"
    equity_target = 75-85%
    cash_target = 5-10%
    leverage_factor = 1.0

ELIF regime_score >= 40:
    regime = "MIXED"
    equity_target = 40-50%
    cash_target = 10-15%
    leverage_factor = 0.7

ELIF regime_score >= 20:
    regime = "CAUTION"
    equity_target = 25-35%
    cash_target = 20-30%
    leverage_factor = 0.4

ELSE:
    regime = "RISK_OFF"
    equity_target = 0-15%
    cash_target = 40-60%
    leverage_factor = 0.0
```

**Additional gates (from iae_quick_reference):**
- VIX > 30 → force RISK_OFF for 48h
- SMH < 200 DMA → no new AI/semi longs
- 10Y > 5% + ISM < 48 → defensive only
- NAV drawdown -10% → leverage 0.5x; -20% → leverage 1.0x; -25% → CAUTION

**Aug 2026 current state:** Regime score 50 = MIXED → 40-45% equity, 10-15% cash, 0.7x leverage

---

## TIER 2 — THEME ROTATION

**Input:** Hyperscalers + NVIDIA/OpenAI + Anthropic knowledge brain scores

**Cycle overlay (cyclical_overlay_4yr_16yr.md):**
- Current: Q3 2026 = defensive/choppy
- 4-year cycle: Year 3 post-election = risk-on setup building
- 16.8-year secular: Phase 2 = innovation/growth leadership
- Combined signal: MIXED → prepare Q4 rotation into IWM/XLK/SMH/XLC

**Theme scoring:**
```
FOR each theme in [AI Compute, AI Infrastructure, Memory, Networking, Cloud, Healthcare, Utilities, Gold, Uranium, Copper, Crypto]:
    theme_score = avg(knowledge_brain_scores_for_theme)
    IF theme_score >= 70:
        bias = "OVERWEIGHT"
        target_weight = base_weight * 1.3
    ELIF theme_score >= 50:
        bias = "NEUTRAL"
        target_weight = base_weight
    ELIF theme_score >= 35:
        bias = "UNDERWEIGHT"
        target_weight = base_weight * 0.6
    ELSE:
        bias = "AVOID"
        target_weight = 0
```

**Q3 2026 theme targets (MIXED regime):**

| Theme | Brain Score | Bias | Target Weight | Notes |
|---|---|---|---|---|
| AI Infrastructure / Power | 100 | OVERWEIGHT | 12-15% | Hyperscaler capex strongest signal |
| Memory / HBM | 75-80 | OVERWEIGHT | 10-12% | HBM scarcity, MU/SNDK |
| Healthcare | 64-86 | OVERWEIGHT | 12-15% | LLY/UNH confluence, defensive |
| Utilities / Nuclear | 48-100 | OVERWEIGHT | 10-15% | NEE/CEG, data center power |
| Gold / Miners | 0-48 | NEUTRAL | 8-10% | Aug seasonal, geopolitical hedge |
| Uranium | 27 | NEUTRAL | 5% | CCJ, defensive commodity |
| Copper | 0 | NEUTRAL | 5% | FCX, electrification |
| AI Compute | 50 | NEUTRAL | 5-8% | Trim L4 as scarcity eases |
| Networking/Optical | 48-55 | NEUTRAL | 5-8% | COHR/LITE, bottleneck L3 |
| Crypto | 48 | NEUTRAL | 3-5% | BTC-IBIT, MSTR overlay |

---

## TIER 3 — SINGLE-NAME CONVICTION

**Input:** TipRanks knowledge brain + strategy doc confluence scores

**Conviction formula (100 points):**
```
Fundamentals (20): Rev>20%, GM>45%, OM>20%, FCF>25%, OpEx leverage≥+10pp
Trend/RS (20): Price>50DMA>200DMA, 55d Donchian, RS>SPY/QQQ/SMH
Analyst Revisions (10): 30d EPS revision spread ≥+2
Institutional (10): 13F accumulation, dark pool buys
AI Layer Cake (10): L1-L6 classification
Situational Awareness (10): Compute scarcity, energy, inference, defense
Tokenization (5): BTC treasury, mining, RWA
Thematic Leadership (5): Top 3 in bottleneck layer
```

**Tier classification:**
- Platinum 90-100: max 12%, spot + 10-15% LEAP calls
- Gold 85-89: max 8%, spot + 5% debit spread sleeve
- Silver 70-84: max 5%, debit spreads preferred
- Bronze 55-69: watchlist only, no position
- Avoid <55: exit existing

**Q3 2026 top names by sleeve:**

### Sleeve 1 — Macro Rotation (37% target)
| Ticker | Weight | Tier | Entry Zone | Stop | Target | Catalyst |
|---|---|---|---|---|---|---|
| LLY | 12% | Platinum 96 | $950-1,000 | $870 (-8%) | $1,200-1,300 | GLP-1 demand, Alzheimer's |
| UNH | 8% | Platinum 91 | $580-600 | $520 (-10%) | $720 | Medicare Advantage |
| NEE | 10% | Gold 88 | $68-72 | $62 (-10%) | $95 | Data center power |
| JNJ | 5% | Gold 85 | $155-160 | $145 (-7%) | $195 | Dividend king, defensive |
| CCJ | 5% | Gold 86 | $55-60 | $50 (-10%) | $80-90 | Uranium supercycle |
| FCX | 5% | Gold 82 | $48-52 | $44 (-10%) | $68 | Copper electrification |
| GDXJ | 5% | Gold 84 | $52-55 | $48 (-10%) | $72 | Junior gold leverage |

### Sleeve 2 — Income/Hedge (25% target)
| Position | Weight | Structure | Yield/Role |
|---|---|---|---|
| TLT | 10% | ETF + 87/90 call debit spread | 4% yield + capital appreciation |
| GLD | 8% | ETF | Tail-risk hedge, Aug seasonal |
| PFF | 5% | Preferred ETF + covered calls | 5.8% yield |
| JNK/HYF | 2% | High-yield ETF | 5-6% carry |

### Sleeve 3 — Innovation (30% target)
| Ticker | Weight | Tier | Entry Zone | Stop | Target | Thesis |
|---|---|---|---|---|---|---|
| MSTR | 8% | Platinum 98 | $450-500 | $380 (-15%) | $900 | Bitcoin treasury |
| VRT | 4% | Platinum 95 | $65-75 | $58 (-15%) | $130 | AI bottleneck king |
| SNDK | 3% | Gold 88 | $55-65 | $50 (-10%) | $110 | AI storage |
| CLSK | 3% | Gold 92 | $18-22 | $15 | $45 | BTC miner |
| COHR | 2% | Gold 92 | $85-95 | $78 | $160 | Silicon photonics |
| IREN | 2% | Gold 90 | $20-25 | $17 | $50 | BTC miner |
| NBIS | 2% | Gold 90 | $22-28 | $19 | $55 | Alternative asset mgr |
| MARA | 2% | Gold 88 | $15-18 | $12 | $35 | BTC miner |
| QUBT | 3% | Silver 82 | $8-12 | $7 | $25 | Quantum computing |
| IONS | 2% | Silver 80 | $45-55 | $40 | $90 | RNA biotech |

### Sleeve 4 — Options Overlay (10-15% notional)
| Underlying | Strategy | Strikes | Max Loss | Rationale |
|---|---|---|---|---|
| LLY | Call debit spread | $1,050/$1,100 | 1% | Platinum technical |
| UNH | Call debit spread | $620/$650 | 1% | Medicare tailwind |
| NEE | Put credit spread | $70/$65 | 0.5% | Defensive income |
| CCJ | Call debit spread | $60/$70 | 1% | Uranium supercycle |
| MSTR | Call debit spread | $550/$650 | 2% | Highest conviction |
| VRT | Call debit spread | $85/$100 | 1.5% | Bottleneck leader |
| SPY | VIX call hedge | VIX $25/$30 | 1% | Crash protection |

---

## TIER 4 — EXECUTION RULES

**Daily workflow:**
1. Run `knowledge_group_brain_scraper.py` → `group_brain_report.json`
2. Run `signal_extractor.py` → `signals.json`
3. Run `integrated_decision_engine.py` → `integrated_campaigns.json`
4. Apply regime gate from Tier 1
5. Filter campaigns by tier and sleeve
6. Check 88% Sell Composite before any new entry
7. Generate trade tickets

**Entry conditions (all must pass):**
- Regime gate: score >= threshold for tier
- Price > 50 DMA (or pullback to 20 DMA with RSI <= 38)
- RVOL > 1.2x on green close
- No FOMC within 2 weeks (or reduce size 30%)
- No NVDA earnings within 4 weeks (reduce AI exposure 25%)
- ATR-based position size: `(equity × 1.0%) / (2 × ATR)`

**Exit conditions (any trigger = scale down):**
- 88% Sell Composite >= 3 triggers → scale 50%
- 88% Sell Composite >= 4 triggers → full exit
- Close < 50 DMA + volume > 1.5x avg
- Single-day loss > 2% on 3x ATR stop
- No averaging down

**Options rules:**
- Max 1% risk per spread
- Close debit spreads 21 days before earnings
- Close all short options into FOMC/NVDA earnings
- 0DTE max 5% of options book
- IV Rank >60% → sell credit spreads
- IV Rank 30-60% → buy debit spreads on skids
- IV Rank <30% → avoid selling

**Correlation guard:**
- No NVDA + SMH + SOXL + AMD core at same time
- Max AI compute 35% of equity
- Max memory 20%
- Max networking 12%
- Max infrastructure 15%

---

## OUTPUT FORMAT

**Daily briefing (Telegram/terminal):**

```
🌐 REGIME: MIXED (score 50/100) | Q3 Defensive | 40-45% equity target

✅ BUY SIGNALS (regime PASS):
  1. VRT BUY | Platinum 92 | weight 6.0% | AI Infrastructure
  2. SNDK BUY | Gold 88 | weight 4.0% | Memory/Storage
  3. LLY BUY | Gold 86 | weight 4.0% | Healthcare
  4. MSFT BUY | Gold 85 | weight 4.0% | Cloud/AI
  5. CCJ BUY | Gold 82 | weight 4.0% | Uranium

⏸️ HOLD (regime block):
  - AMZN, MU, AVGO, NVDA (Platinum requires score >=55)

🔴 SELL/AVOID:
  - None today

⚠️ ALERTS:
  - NVDA earnings within 4 weeks: reduce AI exposure 25%
  - FOMC within 2 weeks: reduce size 30%
  - Sep 18 Quad Witching: reduce overnight exposure

📊 SLEEVE DEPLOYMENT:
  Macro: 37% → LLY 12%, UNH 8%, NEE 10%, JNJ 5%, CCJ 5%, FCX 5%, GDXJ 5%
  Income: 25% → TLT 10%, GLD 8%, PFF 5%, JNK 2%
  Innovation: 30% → MSTR 8%, VRT 4%, SNDK 3%, CLSK 3%
  Options: 8% → spreads on LLY/UNH/NEE/CCJ/MSTR
  Cash: 0% → deploy $3K monthly contribution per schedule
```

---

## AUTOMATION

**Cron schedule:**
```
0 6 * * 1-5   python knowledge_group_brain_scraper.py    # Daily 6am
0 7 * * 1-5   python signal_extractor.py                 # Daily 7am
0 7:30 * * 1-5 python integrated_decision_engine.py      # Daily 7:30am
0 8 * * 1-5   python ai_trading_floor/main.py single --date $(date +%Y-%m-%d)  # Daily 8am
```

**Skill entry point:**
```bash
hermes.run("integrated_trading_agent")
```

---

## FILES TO CREATE/MODIFY

| File | Action | Purpose |
|---|---|---|
| `integrated_trading_agent.md` | ✅ Created | Master workflow doc |
| `knowledge-group-brains/scripts/signal_extractor.py` | ✅ Created | Extract signals from brain report |
| `knowledge-group-brains/scripts/integrated_decision_engine.py` | ✅ Created | Build campaigns with regime gating |
| `ai_trading_floor/agents/knowledge_brain_bridge.py` | 🔄 Next | Bridge campaigns into existing agents |
| `TradingAgents/tradingagents/strategies/knowledge_brain_orchestrator.py` | 🔄 Next | TradingAgents strategy wrapper |

---

## CURRENT STATUS

✅ Knowledge brains: 8/8 groups active, Quiver removed
✅ Signal extractor: parses group_brain_report.json correctly
✅ Decision engine: generates 20 campaigns with regime gating
✅ Strategy docs: unified, 4-sleeve, cyclical, macro, Monte Carlo all on disk
🔄 Next: bridge `integrated_campaigns.json` into `ai_trading_floor` execution agents
