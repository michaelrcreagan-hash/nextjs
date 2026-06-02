# Edge Terminal

Live multi-asset trading dashboard — **BTC · Altcoins · AI bottleneck stocks** — with perps for crypto and options for stocks. Built with Next.js 15, React 19, Tailwind 4, lightweight-charts and recharts.

## Tabs

| Tab | What it does |
|-----|--------------|
| 📋 **Daily Brief** | One-screen synthesis: BTC daily-bias framework, risk-on/off regime, bottleneck status, top AI setups, EPS-revision leaders, catalysts ≤10d, options-flow + negative-funding alerts |
| 🌍 **Macro Regime** | Risk-on/off indicator (VIX / DXY / 10Y / SPY-breadth → 0-100 regime score) |
| ₿ **BTC Cycle** | Weekly OHLCV, 12-signal cycle-bottom detector, DCA ladder |
| ⚡ **Perps & Futures** | Coinglass-style funding + open interest (+ 24h liquidations when keyed) |
| 📉 **Short Signals** | 9-condition BTC perp-short checklist + position calculator |
| 🪙 **Altcoin Squeeze** | APEX-Squeeze V3 12-condition short-squeeze score (max 12.5) |
| 🤖 **AI Stocks** | 5-layer AI bottleneck framework (watchlist → rotation → fundamentals → technical setup + options) |
| 📊 **Options Flow** | IBIT / MSTR / VIX chains, P/C, max-pain, IV skew, GEX proxy |
| 💰 **Trade Tracker** | localStorage P&L log, equity curve, goal progress |

## AI bottleneck 5-layer framework (AI Stocks tab)

1. **Watchlist Universe** — ~25 tickers across semis, hyperscalers, AI infra, power, memory, custom silicon.
2. **Bottleneck Rotation** — GPU scarcity → networking → power/cooling → inference → custom ASIC. Active constraint is read from live hyperscaler **earnings-call transcripts** (FMP) and/or basket momentum.
3. **Fundamental Screen** — guidance quality (analyst estimates), EPS-revision momentum, beat-and-raise trajectory → composite.
4. **Technical Setup** — ADX / DMI / RSI / RVOL → Entry / Stop / TP1-3 (ATR-anchored) + companion options table (long calls / bull-call-spreads, 30-60 DTE).
5. **Daily Brief** — synthesizes everything (the 📋 tab).

## Getting started

```bash
npm install
cp .env.example .env.local   # optional — add API keys (see below)
npm run dev                  # http://localhost:3000
```

## Data sources & API keys

All keys are **optional**. Without them the app uses keyless public sources (Yahoo Finance, Binance, CoinGecko) and every tab still renders. Add keys to upgrade to richer/real data — set them in `.env.local` locally or in **Vercel → Settings → Environment Variables**.

| Env var | Unlocks | Fallback when absent |
|---------|---------|----------------------|
| `FMP_API_KEY` | AI Stocks: real quotes/candles, Layer 3 analyst estimates + earnings surprises, earnings catalysts, Layer 2 transcript-driven phase detection | Yahoo Finance + price-trend proxies |
| `COINGLASS_API_KEY` | Perps & Altcoin Squeeze: aggregated cross-exchange funding, OI change, 24h long/short liquidations (real C2/C7) | Binance Futures funding + OI |

See `.env.example` for the exact endpoints each key powers. The only sub-score still proxied with a key set is the exact 30/60/90-day EPS-revision delta, which requires an estimate-history / SPG (S&P Global Visible Alpha) as-of-date feed — wire it in `app/api/stocks/route.ts → fmpFundamentals()`.

## Frameworks located from source material

- **Risk-on/risk-off indicator** → Macro Regime tab + `/api/macro`.
- **Daily bias framework** → `/api/daily-bias` (BTC HTF EMA structure + 4H momentum + funding → −100…+100), featured atop the Daily Brief.

---

⚠️ **Educational tool only — not financial advice.** Always use stop-losses and manage risk.
