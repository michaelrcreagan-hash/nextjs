# Unified Institutional Alpha Engine — Quick Reference Charts
*Copy-paste ready for notebook, wall, or terminal*

---

## CHART 1: TRADING STRATEGY QUICK REFERENCE

### A. THE 4-LAYER ARCHITECTURE

| Layer | Name | Inputs | Output | Frequency |
|---|---|---|---|---|
| **1** | Macro Regime Engine | VIX, SMH/200DMA, DXY, 10Y, ISM, Global M2, FCI | RISK-ON / MIXED / CAUTION / RISK-OFF | Daily |
| **2** | Theme Rotation Engine | 20 themes scored 0–100 on RS, Revisions, Earnings, Flow, Macro | Dynamic theme weights | Weekly |
| **3** | Security Selection | 100-pt conviction = Fundamentals + Trend + Revisions + Institutional + Layer Cake + SA + Tokenization + Thematic Lead | Tier 1-4 + target weight | Daily/Weekly |
| **4** | Execution & Portfolio | 4 desks, options selector, 88% Sell Composite, hedge book, dynamic leverage | Trade tickets + risk checks | Intraday/Daily |

---

### B. FUNDAMENTAL GATE (20 Points of 100)

| Metric | Threshold | Points |
|---|---|---|
| Revenue growth YoY | >20% | 8 |
| Gross margin | >45% | 4 |
| Operating margin | >20% | 4 |
| FCF / Revenue | >25% | 4 |
| Operating leverage (rev growth − OpEx growth) | ≥+10 pp | 4 |
| **Total** | | **20 max** |

**Pass requirement:** ≥14/20 to proceed. Below that = no new position.

---

### C. TECHNICAL SIGNALS QUICK LOOKUP

| Signal | Entry Condition | Stop | Target | Max Hold |
|---|---|---|---|---|
| **Turtle (55d Donchian)** | Close > 55d high + trend_ok + ADX>25 + RVOL>2× | Entry − 2× ATR | 3× ATR | 4–8 weeks |
| **Pullback** | 10–25% off high + RSI≤38 + closes above prior day high + RVOL>1× | Below swing low − 0.5× ATR | 1.5× risk, 3× risk, trail | 2–6 weeks |
| **Reversal** | ≥20% drop in 20d + RSI≤28 + above 200DMA + weekly bullish engulfing | Below reversal bar low | 2× risk | 1–4 weeks |
| **ATR Compression Breakout** | BB squeeze (<0.8× avg width) + Donchian breakout + RVOL>1.5× | Entry − 1.5× ATR | Measured move of base | 1–3 weeks |
| **LEAP / Options Catalyst** | Tier 1/2 + IV Rank <30% + earnings/catalyst within 2 weeks | Defined by spread width | 50% at +1× ATR, trail balance | 2–8 weeks |

---

### D. ATR & VOLATILITY RULES

#### Position Sizing
```
Units = (Equity × Risk%) / (2 × ATR)
Risk per trade = 1.0–1.5% equity
Max units per ticker = 2
```

#### Options: When to Buy vs Sell Premium

| IV Rank | Action | Structure | ATR Rule for Strikes |
|---|---|---|---|
| **>60%** | **SELL** premium | Credit spread or iron condor | Short strike = ±1.5× ATR; Long = ±0.5× ATR beyond short |
| **30–60%** | **BUY** debit spreads on skids | Debit spread | Long = ±1.0× ATR; Short = ±2.0× ATR |
| **<30%** | Avoid selling; buy strangles only if catalyst pending | Long strangle | Strikes at ±2.5× ATR |

#### Breakout vs Chop Detection

| Condition | Interpretation | Action |
|---|---|---|
| ATR expanding + price > VWAP + RVOL>2× | **Trend ignition** | Add on pullback to EMA8/21 |
| ATR compressing <0.65× 60d ATR for 2+ weeks | **Volatility squeeze** | Prepare for directional breakout; reduce size until direction confirms |
| ATR spiking 2× normal + close outside BB | **Exhaustion / parabolic** | Trim 50%; move stop to breakeven |
| ATR flat + RVOL<0.6× on rallies | **Chop / no demand** | Do not add; reduce to minimum size |

---

### E. 88% SELL COMPOSITE (Red / Exit)

| Trigger | Counts As |
|---|---|
| Options P/C spike + dark pool distribution | 1 |
| RSI >80 + divergence OR declining volume on rally | 1 |
| RVOL failure <0.6× on breakout day | 1 |
| Hyperscaler CapEx flat/miss + stock >5% off ATH | 1 |
| OpEx timing + RSI >72 | 1 |

**3+ triggers = Scale 50%. 4+ triggers = Full exit. No averaging down.**

---

### F. TIER CLASSIFICATION & SIZING

| Tier | Score | Max Weight | Preferred Structure |
|---|---|---|---|
| **Platinum** | 90–100 | 12% | Spot core + 10–15% LEAP calls |
| **Gold** | 85–89 | 8% | Spot core + 5% debit spread sleeve |
| **Silver** | 70–84 | 5% | Debit spreads preferred; avoid spot |
| **Bronze** | 55–69 | Watchlist only | No position |
| **Avoid** | <55 | 0% | Exit existing |

---

### G. MACRO KILL SWITCHES

| Event | Threshold | Action |
|---|---|---|
| VIX spike | >30 | RISK-OFF 48h minimum; no new longs |
| SMH breakdown | <200 DMA | No new AI/semi longs |
| Rates + inflation | 10Y >5% + ISM <48 | Defensive only |
| Drawdown | NAV −10% | Reduce leverage 0.5× |
| Drawdown | NAV −20% | Leverage → 1.0× |
| Drawdown | NAV −25% | Switch to CAUTION |

---

## CHART 2: AI BOTTLENECK TRADE IDENTIFICATION (TOP-DOWN)

### PROCESS FLOW

```
MACRO / LIQUIDITY
    ↓
HYPERSCALER CAPEX (Demand Signal)
    ↓
BOTTLENECK LAYER (Supply Constraint)
    ↓
COMPANY / THEME SELECTION (Conviction Score)
    ↓
TECHNICAL SETUP (Entry / Stop / Target)
    ↓
EXECUTION (Spot + Options + Hedge)
```

---

### STEP 1: MACRO / LIQUIDITY GATE

| Check | RISK-ON | MIXED | CAUTION | RISK-OFF |
|---|---|---|---|---|
| Global M2 YoY | Expanding | Flat+ | Contracting | Contracting fast |
| SMH vs 200 DMA | Above | Above | Below | Below |
| VIX | <18 | 18–25 | 25–30 | >30 |
| FCI (Financial Conditions) | Loose | Neutral | Tight | Very tight |
| DXY | Falling/Flat | Mixed | Rising hard | Spike |
| **Gross Exposure Allowed** | **80%** | **50%** | **25%** | **0% new** |

**Rule:** If any single indicator is in RISK-OFF, drop gross exposure by 1 bracket.

---

### STEP 2: HYPERSCALER CAPEX TRACKER

Track these **every quarter**:

| Hyperscaler | Ticker | CapEx YoY | GPU Orders ↑ | Networking ↑ | Memory ↑ | Power ↑ | Inference ↑ | Score |
|---|---|---|---|---|---|---|---|---|
| Microsoft | MSFT | | | | | | | |
| Amazon | AMZN | | | | | | | |
| Google | GOOGL | | | | | | | |
| Meta | META | | | | | | | |
| Oracle | ORCL | | | | | | | |

**Score each column: Raised = +2, Flat = +1, Cut = −3.**
- **Total ≥8:** Overweight AI Compute + Memory
- **Total 5–7:** Overweight the specific layer being raised
- **Total ≤4:** Defensive; reduce AI exposure

---

### STEP 3: BOTTLENECK LAYER RANKING (9-Phase / 5-Layer)

| Layer | Current Status (July 2026) | Capital Flow | Leading Names | ETF Proxy |
|---|---|---|---|---|
| **L1 — Power / Grid** | 🔴 Dominant | INFLOW | VRT, ETN, PWR, CEG, VST | XLU, PAVE |
| **L2 — Memory / HBM** | 🔴 Dominant | INFLOW | MU, SNDK, WDC, STX | SMH, DRAM |
| **L3 — Networking / Optical** | 🟡 Emerging | ACCELERATING | ANET, CRDO, COHR, LITE, MRVL | SMH, IGV |
| **L4 — Compute / GPUs** | 🟢 Easing | PEAK → rotate out | NVDA, AMD, AVGO, TSM | SMH |
| **L5 — Packaging / Custom** | 🟡 Emerging | ACCELERATING | AMAT, LRCX, KLAC, ASML, ONTO | SMH, KSTR |

**Rotation Rule:** Overweight L1–L3 in 2026. Trim L4 as scarcity eases.

---

### STEP 4: COMPANY SELECTION (100-Point Conviction)

| Factor | Weight | Your 7-Ticker Screen |
|---|---|---|
| Fundamentals | 20 | Rev>20%, GM>45%, OM>20%, FCF>25%, OpEx leverage≥+10pp |
| Trend / RS | 20 | Price>50DMA>200DMA, 55d Donchian, RS>SPY/QQQ/SMH |
| Analyst Revisions | 10 | 30d EPS revision spread ≥+2 |
| Institutional Buying | 10 | 13F accumulation, dark pool buys |
| AI Layer Cake | 10 | L1–L6 classification |
| Situational Awareness | 10 | Compute scarcity, energy, inference, defense, robotics, data infra, strategic national importance |
| Tokenization / Digital Asset | 5 | BTC treasury, mining, stablecoin, RWA |
| Thematic Leadership | 5 | Top 3 in bottleneck layer |

**Entry threshold:** Score ≥75 + Tier ≥Gold + regime not RISK-OFF.

---

### STEP 5: TECHNICAL SETUP TRIGGER

| Setup | Trigger | ATR Condition | Entry | Stop |
|---|---|---|---|---|
| **Turtle** | Close > 55d Donchian | ATR expanding | Open → add | Entry − 2× ATR |
| **Pullback** | 10–25% off high, RSI≤38 | ATR normal | Close > prior day high | Below swing low − 0.5× ATR |
| **Reversal** | ≥20% drop, RSI≤28 | ATR elevated | Weekly bullish engulfing | Below reversal bar |
| **ATR Squeeze** | BB width <0.8× avg | ATR compressed <0.65× 60d | Donchian breakout + RVOL>1.5× | Entry − 1.5× ATR |
| **LEAPs / Options** | Tier 1/2 + catalyst | IV rank <30% | Buy deep ITM call or debit spread | Defined by spread |

---

### STEP 6: EXECUTION & RISK

| Rule | Value |
|---|---|
| Risk per trade | 1.0–1.5% equity |
| Max single name | 12% (Platinum), 8% (Gold), 5% (Silver) |
| Max sector/bucket | AI Compute 35%, Semi Equip 15%, Memory 20%, etc. |
| Correlation guard | No NVDA + SMH + SOXL + AMD simultaneously |
| Options max risk | 1% per trade (0.5% around earnings) |
| Margin / leverage | Dynamic: L_regime × VIX_factor × Vol_CB |
| Hedge book | QQQ/SMH put spreads + VIX calls + TLT/Gold; renew every 45 days |

---

## CHART 3: HIGH-IMPACT MACRO EVENTS & OPTIONS EXPIRIES

### MONTHLY ECONOMIC CALENDAR (Must-Track)

| Date Type | Event | Impact on Strategy |
|---|---|---|
| **FOMC meeting** | Rate decision + dot plot + Powell presser | Highest. Bonds, gold, semis, tech move. Reduce size 2 days before. |
| **CPI / PPI** | Inflation data | 2nd highest. Rates move → tech/growth trades. |
| **Payrolls (NFP)** | First Friday | 3rd. Dollar, rates, risk-on/off swing. |
| **ISM Manufacturing** | 1st business day | Early economic pulse. <48 = defensive. |
| **ISM Services** | 3rd business day | 70% of GDP. >55 = strong. |
| **Fed speeches** | Random | Watched for tone shift. |
| **Quad witching** | 3rd Friday of Mar/Jun/Sep/Dec | Options expiry = unusual volume. |

---

### QUARTERLY HYPERSALER EVENTS

| Event | Typical Timing | Market Impact |
|---|---|---|
| **MSFT Earnings** | Late Jan / Apr / Jul / Oct | AI CapEx guide = sector-wide move |
| **META Earnings** | Same | Ad revenue + Capex = AI demand proxy |
| **GOOGL Earnings** | Same | Cloud + AI spending = demand signal |
| **AMZN Earnings** | Same | AWS + capex = demand signal |
| **NVDA Earnings** | Mid Feb / May / Aug / Nov | GPU demand = Layer 1/2 prices move |
| **TSMC Earnings** | Mid Jan / Apr / Jul / Oct | Foundry pricing + advanced node demand |

**Rule:** Reduce AI exposure 25% 4 weeks before NVDA earnings. Re-enter within 2 days post beat/raise.

---

### MONTHLY OPTIONS EXPIRIES (Liquid ETFs)

| Week | Monday | Tuesday | Wednesday | Thursday | Friday |
|---|---|---|---|---|---|
| **Every week** | | | | | **0DTE expiry** |
| **3rd Friday** | | | | | **Monthly expiry (PM-settled for equities/ETFs)** |

#### Key Expiry Dates to Watch (July–Dec 2026)

| Month | Standard Expiry | OpEx Quad Witching | Notable |
|---|---|---|---|
| **July 2026** | Jul 18 | | Post-NVDA earnings |
| **August 2026** | Aug 21 | | Summer doldrums; low volume |
| **September 2026** | Sep 18 | **Sep 18** | **Quad witching** — highest volume of year |
| **October 2026** | Oct 16 | | Pre-election volatility |
| **November 2026** | Nov 20 | | Post-election; FOMC often mid-Dec |
| **December 2026** | Dec 18 | **Dec 18** | Year-end rebalancing + tax loss/gain |

#### Trade Around Expiry Rules

| Timing | Action |
|---|---|
| **Monday–Wednesday of expiry week** | Normal entries; watch for gamma flip |
| **Thursday** | Reduce size 50% if not in a high-conviction catalyst trade |
| **Friday AM** | Only close or roll; no new entries unless 0DTE catalyst confirmed |
| **0DTE (same-day)** | Max 5% of options book; defined risk only; no wide iron condors |
| **Post-expiry Monday** | Reassess theme scores; hunt for new setups |

---

### CRYPTO OPTIONS EXPIRIES

| CME Bitcoin Expiry | Typical Dates | Impact |
|---|---|---|
| Monthly | Last Friday of month | BTC/IBIT volatility spike 1–2 days before |
| Quarterly | Mar/Jun/Sep/Dec last Friday | **Largest** BTC options expiry; max pin risk |

**Rule:** Do not hold IBIT options through CME expiry unless you have delta-hedged or defined risk on both sides.

---

## CHART 4: SCORING QUICK KEY

```
SCORE BREAKDOWN (100 total)
├─ Fundamentals ............ 20
├─ Trend / RS .............. 20
├─ Analyst Revisions ....... 10
├─ Institutional Buying .... 10
├─ AI Layer Cake ............ 10
├─ Situational Awareness .... 10
├─ Tokenization ............. 5
└─ Thematic Leadership ....... 5

TIERS
├─ PLATINUM (90–100) → Full core, up to 12%
├─ GOLD     (85–89)  → Standard core, up to 8%
├─ SILVER   (70–84)  → Reduced / options preferred, up to 5%
├─ BRONZE   (55–69)  → Watchlist
└─ AVOID    (<55)     → Exit existing, no new entries

THEME SCORES (0–100)
├─ >90 = Increase allocation
├─ 80–90 = Maintain
├─ 70–80 = Watch
└─ <70 = Reduce

IV RANK → STRATEGY
├─ >60% = Sell credit spreads / iron condors
├─ 30–60% = Buy debit spreads on skids
└─ <30% = Avoid selling; buy strangles only if catalyst

ATR STRIKE RULE
├─ Credit spread short strike = ±1.5× ATR
├─ Credit spread long strike = ±0.5× ATR beyond short
├─ Debit spread long = ±1.0× ATR
└─ Iron condor wings = ±1.2× ATR
```

---

## PRINT / SCREEN GOLDEN RULES

1. **Never add to a losing position** until it recovers to cost basis
2. **Never average down more than once**
3. **Never hold debit spreads into final 14 days**
4. **Never size up during a losing streak** — wait for 3 consecutive winners
5. **Never override RISK-OFF regime gate**
6. **Single name >12% → trim immediately**
7. **Start all new positions at quarter-size**; earn full size through confirmed follow-through
8. **Max 1% risk per trade** (0.5% around binary events)
9. **After any >2% loss**, log exact failure before re-entering
10. **Macro changes first, theme second, stock third, options fourth** — never reverse this order
