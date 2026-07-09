# Knowledge Brain Framework Suite
*Scalable architectures for auto-updating market intelligence*

---

## EXECUTIVE SUMMARY

This document defines **6 interchangeable knowledge-brain frameworks**, each
optimized for a different source type and signal latency. They share one output
schema so they can be composed into a single alpha engine.

The frameworks are:

| # | Framework | Best For | Latency | Complexity |
|---|---|---|---|---|
| **1** | **Market-Voice Brain** | Traders, analysts, pundits | 7 days | Medium |
| **2** | **Earnings-Transcript Brain** | Earnings calls, guidance | 1 day | Medium |
| **3** | **Sector-Thematic Brain** | Themes, narratives, ETFs | 7 days | Medium |
| **4** | **Crypto-Onchain Brain** | Chains, protocols, DAOs | 24 hours | High |
| **5** | **Macro-Data Brain** | Rates, yields, liquidity | 1 day | Low |
| **6** | **Technical-Confluence Brain** | Charts, flows, positioning | Real-time | High |

---

## DESIGN PRINCIPLES

1. **One output schema** across all frameworks — composable
2. **Auto-updating** — designed for cron/scheduled execution
3. **7-day / 30-day delta** in every framework — trend detection built-in
4. **Source-agnostic plumbing** — swap an RSS feed for an API without rewriting logic
5. **Deterministic confidence scoring** — not vague "bullish/bearish", but numerical 1–10 with rationale

---

## FRAMEWORK 1: MARKET-VOICE BRAIN

### Purpose
Track public commentary from named market participants (Jensen Huang, Stan
Druckenmiller, etc.) and generate buy/rotate/avoid signals.

### Inputs
- Public interviews
- Podcasts/YouTube
- Substack/RSS
- X/Twitter feeds
- Earnings-call appearances

### Output Schema
```json
{
  "brain_id": "stan_druckenmiller",
  "last_updated": "2026-07-07T23:30:00Z",
  "window_7d": {
    "items_collected": 8,
    "sentiment_score": 72,
    "top_themes": ["gold", "copper", "rates"],
    "top_catalysts": ["rate cut", "fiscal stimulus"],
    "quotes": ["..."],
    "sources": ["realvision.com/...", "macrovoices.com/..."]
  },
  "window_30d": {
    "sentiment_score": 58,
    "items_collected": 42
  },
  "delta": "more bullish than last 30 days",
  "actionable": "Consider increasing gold and copper allocation",
  "conviction": 8,
  "tickers_mentioned": ["GLD", "COPX", "TLT", "DBA"]
}
```

### Implementation
- Scraper: `search_web()` with date filtering
- Parser: keyword extraction + optional LLM summarization
- Storage: JSON per brain, daily cron update
- Dedup: URL hash

### What It Detects
| Pattern | Signal |
|---|---|
| Repeated ticker mention | Accumulation/distribution |
| Theme dominance shift | Sector rotation |
| Sentiment delta >15 pts | Potential positioning shift |
| Catalyst language: "about to", "next quarter" | Near-term event |
| Bearish shift + high assets | Possible short candidate |

---

## FRAMEWORK 2: EARNINGS-TRANSCRIPT BRAIN

### Purpose
Parse earnings-call transcripts for guidance changes, tone, and execution
quality. Generate 1–10 scores and event-driven rotation signals.

### Inputs
- SEC EDGAR 8-K filings
- Seeking Alpha transcripts
- Company IR pages
- Estimize transcripts
- API: AlphaWave, Levenson

### Output Schema
```json
{
  "ticker": "NVDA",
  "fiscal_quarter": "Q2 FY2026",
  "report_date": "2026-07-15",
  "window_7d": {
    "transcript_url": "https://seekingalpha.com/article/...",
    "sentiment_score": 85,
    "guidance_delta": "raised",
    "beat_estimate_pct": 12.4,
    "key_quotes": [
      "Data center revenue grew 260% year over year"
    ],
    "management_tone": "confident",
    "qa_tone": "defensive",
    "analyst_pushback": "low"
  },
  "window_30d": {
    "avg_sentiment": 72,
    "prior_guidance": "in-line",
    "analyst_revision_delta": "+4.2%"
  },
  "delta": "more bullish than prior quarter",
  "actionable": "Add on pullback; guided higher with confidence",
  "conviction": 9
}
```

### Implementation
- Scraper: Seeking Alpha / SEC EDGAR for 8-Ks + transcript links
- Parser: regex for guidance language, sentiment lexicons
- Event detector: `raised guidance`, `beat by >10%`, `conservative tone`
- Storage: one JSON per ticker per quarter

### What It Detects
| Pattern | Signal |
|---|---|
| Guidance raised + sentiment >75 | Strong buy |
| Guidance raised + sentiment 60–74 | Add on weakness |
| Guidance in-line + sentiment dropping | Hold, reduce into strength |
| Guidance cut + bearish quotes | Avoid / short |
| Beat >15% + conservative tone | Right-hand-add candidate |
| Analyst pushback high | Beware of hidden weakness |

---

## FRAMEWORK 3: SECTOR-THEMATIC BRAIN

### Purpose
Scan macro commentary, policy documents, and sector research to identify
rotating themes BEFORE they appear in price. Maps directly to our 20 themes.

### Inputs
- Fed speech transcripts
- Congressional testimony
- Infrastructure bills
- ETF flow data
- Sector ETF filings

### Output Schema
```json
{
  "theme": "AI Power Infrastructure",
  "window_7d": {
    "mentions": 45,
    "sentiment_score": 88,
    "new_catalysts": [
      "White House AI infrastructure executive order"
    ],
    "etf_flows": {
      "VRT": "+$120M this week",
      "XLE": "+$45M"
    },
    "keywords": ["power", "data center", "AI", "grid"]
  },
  "window_30d": {
    "mentions": 210,
    "sentiment_score": 75,
    "peak_date": "2026-06-15"
  },
  "delta": "accelerating — +30 mentions vs prior week",
  "actionable": "Rotate into VRT, PWR, CEG within 2 weeks",
  "conviction": 9,
  "etf_correlation": 0.82,
  "related_themes": ["nuclear", "grid modernization"]
}
```

### Implementation
- Scraper: Filter keyword pulls from macrovoices, Fed speech APIs
- NLP: TF-IDF theme extraction + sentiment
- Flow detector: Compare current week to prior 4-week average
- Storage: one JSON per theme per week

### What It Detects
| Pattern | Signal |
|---|---|
| Mentions doubling in 7 days | Theme entering institutional view |
| Theme sentiment >80 + accelerating | Add sector ETF |
| Theme sentiment <35 + declining | Exit sector ETF |
| Related themes converging | Rotational cluster forming |
| ETF flow divergence | Smart money ahead of price |

---

## FRAMEWORK 4: CRYPTO-ONCHAIN BRAIN

### Purpose
Monitor blockchain data, protocol metrics, and crypto commentary. Generate
conviction scores for the 17-coin crypto universe.

### Inputs
- CoinGlass / Glassnode (free tier)
- CryptoQuant
- Dune Analytics dashboards
- LunarCrush social metrics
- CoinDesk / CoinTelegraph headlines
- Substack: @Arthur_0x, @punk6529, @nic__carter

### Output Schema
```json
{
  "asset": "BTC",
  "window_7d": {
    "price": 63430,
    "onchain": {
      "exchange_outflows_7d": "-12,000 BTC",
      "active_addresses": "1.05M",
      "hash_rate": "650 EH/s"
    },
    "social_sentiment": 78,
    "fear_greed": "greed",
    "funding_rate": "+0.01%"
  },
  "window_30d": {
    "onchain_trend": "accumulation",
    "social_sentiment": 62,
    "etf_flows": "+$450M"
  },
  "delta": "more bullish — ETF inflows accelerating, exchange supply declining",
  "actionable": "Add BTC on pullback to $60K–62K",
  "conviction": 8,
  "risks": ["VIX correlation rising", "leverage at 2-year high"]
}
```

### Implementation
- Scraper: Glassnode free API + CoinGlass + LunarCrush RSS
- Parser: exchange flow signals, sentiment from social
- Alert rules: large exchange outflows, funding rate spikes
- Storage: one JSON per asset per day

### What It Detects
| Pattern | Signal |
|---|---|
| Exchange outflow >5K BTC in 7d | Accumulation, add |
| Funding rate >0.05% | Overleveraged, reduce |
| Social sentiment <30 + price dropping | Capitulation, buy |
| ETF inflow >$300M/week | Institutional buying |
| Hash rate declining | Miner capitulation, bottom signal |

---

## FRAMEWORK 5: MACRO-DATA BRAIN

### Purpose
Track macro indicators and generate regime scores. This is the regime-filter
for the 4-sleeve portfolio.

### Inputs
- FRED API (free): 10Y yield, 2Y yield, M2, VIX, ISM
- CBOE VIX futures
- BLS CPI/PCE releases
- BEA GDP advance
- Treasury yield curve
- Global liquidity indices (BNP Paribas)

### Output Schema
```json
{
  "as_of": "2026-07-07",
  "regime": {
    "score": -1,
    "label": "MIXED → CAUTION",
    "components": {
      "rates_signal": -1,
      "liquidity_signal": -1,
      "volatility_signal": 0,
      "growth_signal": 1,
      "inflation_signal": -1
    }
  },
  "signals": [
    "10Y yield at 4.53%, stable — no new signal",
    "VIX at 18.4 — in normal range",
    "ISM at 51.2 — expansion, but slowing",
    "M2 YoY -1.2% — contracting"
  ],
  "rotation_implication": "Q3 defensive rotation intact",
  "equity_exposure_target": "40–45%",
  "sleeve_weights": {
    "macro": "30%",
    "income": "25%",
    "innovation": "15%",
    "options": "5%",
    "cash": "25%"
  }
}
```

### Implementation
- Scraper: FRED API (`requests.get("https://api.stlouisfed.org/fred/series/...")`)
- Parser: rule-based regime scoring
- Regime rules: see unified_macro_rotational_framework.md
- Storage: daily JSON, last 90 days of history

### What It Detects
| Indicator | Threshold | Signal |
|---|---|---|
| 10Y yield > 5% | 2+ weeks | CAUTION → reduce duration |
| VIX > 30 | Any | RISK-OFF → hedge book |
| ISM < 48 | 2+ months | DEFENSIVE → utilities/healthcare |
| M2 YoY inflection from negative | Weekly | RISK-ON → add risk |
| 2Y/10Y yield curve steepening | 1+ month | GROWTH → rotate risk-on |
| HYG spreads > 400bps | Any | CREDIT STRESS → cash |

---

## FRAMEWORK 6: TECHNICAL-CONFLUENCE BRAIN

### Purpose
Scan the full watchlist for technical setups, rank by confluence score, and
output a priority buy/sell list that integrates with the alpha engine.

### Inputs
- yfinance (free)
- TA-Lib / pandas_ta
- TradingView screener API
- Volume profile data

### Output Schema
```json
{
  "generated_at": "2026-07-07",
  "universe_size": 98,
  "signals": {
    "strong_buy": [
      {
        "ticker": "LLY",
        "score": 96,
        "tier": "platinum",
        "confluence_factors": ["donchian_breakout", "above_200dma", "rsi_65", "positive_earnings_revision"],
        "entry_zone": "$950–1,000",
        "stop": "$870",
        "position_size": "12%",
        "sleeve": "macro"
      }
    ],
    "buy": [...],
    "hold": [...],
    "avoid": [...]
  },
  "theme_concentration": {
    "AI Compute": [{"ticker": "NVDA", "count": 12}],
    "Healthcare": [{"ticker": "LLY", "count": 8}]
  },
  "rotation_suggestion": "Healthcare leading; trim tech names into strength"
}
```

### Implementation
- Scraper: yfinance for OHLCV + fundamentals batch
- Engine: 10-layer confluence score (see `iae_technical_confluence_score.pine`)
- Output: JSON ranked list, top 20 buys, top 10 avoids
- Frequency: nightly cron job

### What It Detects
| Pattern | Signal |
|---|---|
| Platinum tier + earnings revision up | Add size |
| Gold tier + rising volume | Momentum add |
| Silver tier + support test | Risk/reward entry |
| Donchian breakdown + death cross | Exit trigger |
| Theme concentration >40% single sector | Trim into strength |

---

## UNIFIED OUTPUT SCHEMA (All Frameworks Share This)

```json
{
  "framework_type": "market_voice | earnings | sector | crypto | macro | technical",
  "as_of": "2026-07-07T23:30:00Z",
  "entity_id": "STAN_DRUCKENMILLER | NVDA | AI_POWER | BTC | US_MACRO | WATCHLIST",
  "sentiment_7d": 72,
  "sentiment_30d": 58,
  "delta": "more_bullish | more_bearish | stable",
  "conviction": 8,
  "actionable": "Specific action with rationale",
  "sources": ["url1", "url2"],
  "tickers_affected": ["GLD", "COPX", "TLT"],
  "position_recommendation": {
    "action": "add | reduce | hold | exit",
    "size_pct": "increase to 8%",
    "entry_zone": "$X–$Y",
    "stop": "$Z",
    "target": "$A"
  },
  "risks": ["Risk 1", "Risk 2"],
  "confidence": 0.82
}
```

---

## COMPOSITION: HOW FRAMEWORKS FEED THE ALPHA ENGINE

```
┌─────────────────────────────────────────────────────────┐
│                  KNOWLEDGE BRAIN SUITE                    │
├──────────────┬──────────────┬──────────────┬─────────────┤
│  Market-Voice│  Earnings    │  Sector-     │ Crypto-     │
│  Brain       │  Transcript  │  Thematic    │ Onchain     │
│  (11 brains) │  Brain       │  Brain       │ Brain       │
│              │  (20 tickers)│  (20 themes) │  (17 assets)│
├──────────────┴──────────────┴──────────────┴─────────────┤
│                    UNIFIED SIGNAL LAYER                    │
│  • Merged sentiment delta                                  │
│  • Cross-framework consensus scoring                       │
│  • Confidence-weighted conviction (1–10)                   │
└────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 EXISTING ALPHA ENGINE                     │
│  • 100-point conviction formula                            │
│  • Macro regime gating                                     │
│  • Theme rotation                                          │
│  • 4-sleeve portfolio                                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              PORTFOLIO ROTATION / TRADE EXECUTION          │
│  • BUY / ADD / REDUCE / AVOID / EXIT                      │
│  • Entry zones, stops, targets                             │
│  • Sleeve-weight adjustments                               │
└─────────────────────────────────────────────────────────┘
```

---

## FRAMEWORK COMPARISON: WHEN TO USE WHICH

| Decision | Use Framework | Because |
|---|---|---|
| "Should I add to this position?" | Market-Voice + Technical | See what smart money says + chart confirmation |
| "Is this earnings beat sustainable?" | Earnings-Transcript + Technical | Guidance language + price action |
| "What sector should I rotate into?" | Sector-Thematic + Technical | Theme momentum + entry setup |
| "Should I buy this crypto?" | Crypto-Onchain + Macro | On-chain data + macro regime fit |
| "What's my equity exposure target today?" | Macro-Data Brain | Purely regime-driven |
| "Which of my 98 tickers is setting up best?" | Technical Confluence | Batch screen with 10-layer score |

---

## CONFIDENCE SCORING RULES (Cross-Framework)

| Score | Meaning | Action Size |
|---|---|---|
| **9–10** | Cross-framework consensus, high-quality sources | Full position |
| **7–8** | One framework strong, others neutral | 75% target size |
| **5–6** | Mixed signals, no clear direction | 50% target size |
| **3–4** | Bearish divergence across frameworks | Reduce / hedge |
| **1–2** | Broad consensus negative | Exit / avoid |

---

## UPGRADE PATH (Priority Order)

### Phase 1: Fix Core Scrapers (Day 1)
1. Replace DuckDuckGo with SearX/Brave in all frameworks
2. Add 5 RSS feeds per top-5 market voices
3. Add FRED API for macro brain
4. Add Glassnode free tier for crypto brain

### Phase 2: Add Structured Sources (Day 2)
1. Earnings-transcript scraper (Seeking Alpha / SEC EDGAR)
2. ETF flow API parsing
3. Crypto exchange flow APIs
4. YouTube transcript via `youtube-transcript-api`

### Phase 3: Cron + Integration (Day 3)
1. Daily cron for macro-data brain (5-minute job)
2. Weekly cron for market-voice brains
3. Earnings brain triggered by calendar
4. Output routing: JSON → master report → Telegram alert

### Phase 4: LLM Enhancement (Day 4)
1. Optional LLM summarization of transcripts
2. Named-entity extraction for tickers/themes
3. Catalyst timeline generation
4. Cross-framework consensus reasoning

---

## EXAMPLE: FULL PIPELINE OUTPUT

```json
{
  "pipeline_run": "2026-07-07T23:59:00Z",
  "frameworks_run": ["market_voice", "earnings", "sector", "crypto", "macro", "technical"],
  "master_signal": {
    "regime": "MIXED → CAUTION",
    "equity_target": "40–45%",
    "top_buys": [
      {
        "ticker": "LLY",
        "score": 96,
        "frameworks_agreeing": ["earnings", "technical", "market_voice"],
        "action": "add to 12%",
        "conviction": "9/10"
      },
      {
        "ticker": "NEE",
        "score": 88,
        "frameworks_agreeing": ["market_voice", "technical", "macro"],
        "action": "add to 10%",
        "conviction": "8/10"
      }
    ],
    "top_avoids": [
      {
        "ticker": "XLE",
        "score": 28,
        "frameworks_agreeing": ["macro", "technical"],
        "action": "exit by September",
        "conviction": "7/10"
      }
    ],
    "crypto_signals": [
      {
        "asset": "BTC",
        "score": 78,
        "frameworks_agreeing": ["crypto", "macro"],
        "action": "add on $60–63K dip",
        "conviction": "7/10"
      }
    ]
  }
}
```

---

## PART 7: SKILL WRAPPERS

Each framework gets a Hermes skill wrapper:

```
knowledge-brains/
├── SKILL.md
├── scripts/
│   ├── knowledge_brain_scraper.py       ← Market-Voice
│   ├── earnings_transcript_brain.py     ← Earnings
│   ├── sector_thematic_brain.py         ← Sector
│   ├── crypto_onchain_brain.py          ← Crypto
│   ├── macro_data_brain.py              ← Macro
│   └── technical_confluence_brain.py    ← Technical
├── config/
│   ├── market_voices.json
│   ├── earnings_watchlist.json
│   ├── themes.json
│   ├── crypto_universe.json
│   ├── macro_indicators.json
│   └── equity_watchlist.json
└── output/
    └── unified_master_report.json
```

---

## PART 8: USAGE EXAMPLES

### Run market-voice brain for Druckenmiller
```bash
python knowledge_brain_scraper.py --brain Stan Druckenmiller --output output/druckenmiller.json
```

### Run earnings brain for NVDA
```bash
python earnings_transcript_brain.py --ticker NVDA --output output/nvda_earnings.json
```

### Run sector brain for "AI Infrastructure"
```bash
python sector_thematic_brain.py --theme "AI Infrastructure" --output output/ai_infra.json
```

### Run crypto brain for BTC
```bash
python crypto_onchain_brain.py --asset BTC --output output/btc_onchain.json
```

### Run macro brain
```bash
python macro_data_brain.py --output output/macro_regime.json
```

### Run technical confluence screen
```bash
python technical_confluence_brain.py --watchlist all --output output/technical_screen.json
```

### Run all + unified report
```bash
python unified_master_report.py --all --output output/master_report.json
```

---

## PART 9: WHAT THIS DELIVERS (Weekly/Monthly)

Once all 6 frameworks are running, you get:

1. **Daily macro regime score** → know when to be aggressive or defensive
2. **Weekly market-voice pulse** → see what the smartest minds are saying
3. **Quarterly earnings updates** → track guidance quality by ticker
4. **Weekly theme flow rankings** → see which narratives are accelerating
5. **Daily crypto onchain check** → add/delay BTC/ETH entries based on real usage
6. **Nightly technical screen** → wake up to a ranked buy list

### The Feedback Loop

```
Macro regime changes
    ↓
Sleeve weights adjust
    ↓
Technical screen re-scores new universe per weight
    ↓
Earnings brain validates/unscripts crowded trades
    ↓
Market-voice brain confirms with personality conviction
    ↓
Crypto brain adds asymmetric tail-risk overlays
    ↓
Execute at confluence levels
```

---

*Framework suite designed for composability. Each brain is independently useful,
but together they form the Situational Awareness and Analyst Revisions inputs
to the existing 100-point conviction formula.*