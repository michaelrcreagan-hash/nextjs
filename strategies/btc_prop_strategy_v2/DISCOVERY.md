# Strategy Discovery: btc_prop_strategy_v2

**Date:** 2026-07-23
**Phase:** Discovery Complete
**Engine:** pandas
**Project Type:** hybrid (multi-strategy composite + regime confluence scoring)

---

## Core Hypothesis

A three-sub-strategy BTC perpetual-futures book (trend following, mean reversion, funding-rate carry) outperforms any single approach because it diversifies across market regimes. Layering a 6-layer macro/cycle/on-chain/derivatives/technical/DCB confluence score on top gates exposure to periods where the edge is strongest, and free Coinglass microstructure filters (OI, CVD, liquidation clusters, net delta) plus calendar/session timing (FOMC drift, ETF flows, best trading hours) sharpen entry timing within that gate.

### Market Behavior Exploited
- **Trend Rider:** sustained directional moves confirmed by EMA/Supertrend/ADX structure.
- **Range Hunter:** short-term mean reversion in low-ADX chop, RSI(2) extremes.
- **Funding Farmer:** crowded perp positioning (funding rate extremes) mean-reverts, capturing the funding payment as a near-arbitrage.
- **DCB overlay:** dead-cat-bounce failures in confirmed bear regimes are the highest-R:R setup in the dataset (68-75% win rate at top confluence) because crowded bear-market relief rallies fail at predictable technical levels (declining 200DMA, SOPR reclaim-fail).
- **Coinglass/timing layers:** institutional order flow (CVD divergence, large orders, net delta) and systematic post-FOMC/session drift are measurable, repeatable microstructure edges independent of the above.

### Theoretical Basis
- EMA/Supertrend/ADX trend-following: well-documented directional persistence once ADX confirms trend strength.
- RSI(2) mean reversion: classic Larry Connors short-horizon reversion, works best when ADX confirms *absence* of trend.
- Funding-rate carry: structural — perp funding pays the side betting against the crowd; historically 70-90% win rate, short hold.
- Macro/on-chain confluence: MVRV Z, Puell, RHODL are valuation extremes with documented (if degrading post-ETF) predictive power; DXY/M2 gate risk-on/risk-off regime.
- DCB-short: bear-market relief rallies statistically fail at the declining 200DMA (~82% historical rejection rate) and SOPR reclaim-and-fail (~80%).
- Coinglass layer: OI/CVD/liquidation/net-delta divergences reflect real order-flow imbalance ahead of price; independently backtested each adding 3-8% win rate over an 8-year, 452-trade sample.
- Session/day timing: liquidity and participant mix vary by session (USA open highest volume/volatility, Europe mid-session most prone to reversal) — empirically measurable, not just folklore.

---

## Entry Conditions

| Condition | Description | Data Required |
|-----------|-------------|----------------|
| Macro regime gate | DXY trend + Global M2 (60-90d lag) + real yields must not oppose trade direction by ≥2 factors | DXY, M2, 10Y TIPS yield |
| Cycle position | Months post-halving, 200WMA position/slope, Pi Cycle (confirmation only, degraded reliability post-2021) | BTC weekly OHLCV |
| On-chain confluence | MVRV Z (<0 long / >5.5 short), Puell (<0.5 / >3.0), RHODL, LTH supply % trend, STH realized loss | On-chain (Glassnode/CryptoQuant-class data) |
| Trend Rider trigger | 9 EMA crosses 21 EMA + Supertrend flip + ADX(14)>25, on 4H entry / 1D trend timeframe | BTC OHLCV 4H/1D |
| Range Hunter trigger | RSI(2)<10 (long)/>90 (short) + price at BB(20,2) outer band + ADX(14)<20, on 1H, confirmed by volume>150% of 20MA + Stoch RSI reversal from extreme | BTC OHLCV 1H |
| Funding Farmer trigger | Funding rate 7d-MA beyond ±0.01%/8h + CVD confirming direction, on 4H | Funding rate, spot+futures CVD |
| DCB-short trigger (bear regime only) | Confirmed bear (price<365DMA) AND ≥4 of 5 top DCB signals firing AND price within 5% of declining 200DMA from below AND bounce ≥10 days/≥15% old | OHLCV, 200DMA, SOPR, funding, LTH supply |
| Coinglass confluence booster | OI rising+price falling (short) or analog long case; funding in optimal zone (-0.01% to +0.03% for shorts); CVD divergence present; price near liquidation cluster; net long%>55% (contrarian short) or analog long case | Coinglass-class OI/CVD/liquidation/net-delta data |
| Timing filter | Prefer USA open (16:00-18:00 UTC) or early Asia (00:00-02:00 UTC), Tue-Wed best days; avoid Europe mid-session (10:00-14:00 UTC) and Friday post-16:00 UTC entries | Session clock only |
| Macro-event filter | No new positions 3 days pre-FOMC; aggressive entries 24-48h post-FOMC if hawkish; CPI surprise >+0.2% favors shorts, <-0.2% pauses shorts 3 days | Economic calendar |
| ETF flow filter | 2-day average net outflow (or neutral) favors shorts; >$300M inflow pauses new shorts | ETF flow data (IBIT/FBTC/etc.) |

### Entry Signal Logic
```
macro_gate = evaluate(dxy_trend, m2_trend, real_yields, fomc_stance)
if macro_gate == BLOCKED and requested_leverage > 2x:
    skip

confluence_score = weighted_sum(macro, cycle, onchain, derivatives, technical, dcb)
# macro is gate, not scored, per multi-layer framework's explicit correction
if count(layers with |score| >= 30, same direction) < 4:
    NO TRADE

for each sub_strategy in [trend_rider, range_hunter, funding_farmer]:
    if sub_strategy.trigger_fires() and timing_filter_passes() and macro_event_filter_passes():
        coinglass_boost = score_coinglass_layer(oi, funding, cvd, liq_heatmap, net_delta, large_orders)
        size = base_risk * confluence_tier_multiplier(confluence_score) * (1 + coinglass_boost)
        enter(direction, size=min(size, prop_firm_max_risk_per_trade))

if regime == confirmed_bear and dcb_short_trigger_fires():
    enter(SHORT, size=dcb_confidence_score_based_size, leverage<=5x_capped_at_prop_firm_max)
```

---

## Exit Conditions

### Take Profit
Scale-out 50/30/20 across three targets (backtest-validated as superior to all-or-nothing: 71.2% win rate / -19.3% max DD vs 58.4% win rate / -27.6% max DD for all-or-nothing).
- Trend Rider: T1/T2/T3 via ATR/measured-move, trail remainder at Supertrend flip.
- Range Hunter: RSI(2) reversion to 50.
- Funding Farmer: funding normalizes to neutral, or max hold reached.
- DCB-short: prior swing low minus 38.2% Fib extension, or nearest HVN below.

### Stop Loss
- Trend Rider: 2x ATR(14, 4H) trailing.
- Range Hunter: 1x ATR(14, 1H).
- Funding Farmer: none (time-boxed exit only, 24-48h max hold) — funding-rate carry is not directional so ATR stop isn't the right tool.
- DCB-short: 1.5x ATR(14, 4H) above bounce peak, no exception.
- All: signal-invalidation override — macro regime score jumping >20 points in 1 day, or a Fed-pivot headline, force-exits regardless of price-based stop.

### Other Exit Conditions
- Three-month-rule override: 3 consecutive green monthly closes invalidates any active DCB-short setup pending regime reclassification.
- Auto-deleverage after 2 consecutive stops; resume only after one winning trade or regime reconfirmation.
- CME-gap awareness: no new counter-trend perp position within 48h of CME open if unfilled gap >$1,500 exists.

---

## Data Requirements

| Dataset | Resolution | Source | Size Estimate | Status |
|---------|------------|--------|----------------|--------|
| BTC OHLCV | 1H/4H/1D/1W | FMP `crypto` (confirmed reachable this session) | Small-Medium | ✅ Reachable |
| Funding rate + OI | Per funding interval | Hyperliquid `info` endpoint free/keyless per prior research in crypto_algo_trading strategy — **but confirmed blocked from this sandbox's network egress** in that same research | Unknown | ⚠️ Blocked in this environment, API itself is open |
| Spot + Futures CVD | Tick/1m aggregated | No packaged source found in prior research either — build-it-yourself trade-tape aggregation | Unknown | ❌ Not reachable as ready dataset |
| DXY, Global M2, 10Y real yields | Daily | AlphaVantage / FMP `economics` (available via MCP tools this session) | Small | ✅ Reachable |
| On-chain (MVRV Z, SOPR, Puell, RHODL, LTH supply, exchange reserves) | Daily | No confirmed reachable connector this session — Glassnode/CryptoQuant-class, needs sourcing | Unknown | ❌ Not yet sourced |
| Coinglass (liquidation heatmap, net delta, large orders) | Real-time/intraday | No confirmed reachable connector this session | Unknown | ❌ Not yet sourced |
| ETF flows (IBIT/FBTC/etc.) | Daily | Farside Investors per source docs (free) — not yet tested in this environment | Small | ⚠️ Untested |
| FOMC/CPI/NFP calendar | Event dates | Tipranks `get_economic_calendar` (confirmed reachable per crypto_algo_trading prior research) | Small | ✅ Reachable |

This strategy carries the **same funding/OI and CVD blocked-data problem** already documented in `crypto_algo_trading/DISCOVERY.md` — both strategies share that dependency. On-chain valuation metrics (MVRV Z/Puell/RHODL) and Coinglass microstructure data are net-new blocked/unsourced dependencies specific to this strategy and are the biggest open data-sourcing risk.

### Data Scale
- **Estimated rows:** unknown — not yet sourced
- **Engine:** pandas (default; revisit if intraday CVD/liquidation data volumes push into fast-engine territory)
- **Rationale:** consistent with crypto_algo_trading — don't switch engines speculatively

### Data Validation Checklist
- [ ] No gaps in timestamps across OHLCV, funding, on-chain, and Coinglass feeds
- [ ] All feeds aligned to a common bar interval (4H primary)
- [ ] Sufficient history for a full macro cycle (2018-2026, 3 full cycles, per source backtests)

---

## Build Plan

**Complexity Level:** Complex (three sub-strategies + confluence scoring engine + macro gating + prop-firm risk manager; no ML but high feature/composition count)

| Step | Description | Output |
|------|-------------|--------|
| 1 | Source BTC OHLCV, funding/OI, CVD, DXY/M2/yields, on-chain, Coinglass, ETF flows, macro calendar | `Data/*.csv` or `.parquet` |
| 2 | Build indicator library (EMA, Supertrend, ADX, RSI(2), BB, ATR) | `src/indicators.py` |
| 3 | Build CVD engine + divergence detector | `src/cvd_engine.py` |
| 4 | Build macro/cycle/on-chain/derivatives/technical/DCB confluence scorer + macro gate | `src/regime_filter.py` |
| 5 | Build Trend Rider sub-strategy | `src/trend_rider.py` |
| 6 | Build Range Hunter sub-strategy | `src/range_hunter.py` |
| 7 | Build Funding Farmer sub-strategy | `src/funding_farmer.py` |
| 8 | Build DCB-short overlay (bear-regime conditional) | `src/dcb_overlay.py` |
| 9 | Build Coinglass confluence booster (OI/CVD/liquidation/net-delta/large-orders) | `src/coinglass_filters.py` |
| 10 | Build session/day/FOMC/ETF timing filters | `src/timing_filters.py` |
| 11 | Build prop-firm risk manager (daily loss, total DD, per-trade risk, trade frequency, cooldown, consistency check) | `src/risk_manager.py` |
| 12 | Build position sizing (confluence-tiered, prop-firm-capped) | `src/position_sizing.py` |
| 13 | Build multi-strategy signal allocator (50/30/20 base alloc + DCB overlay) | `src/signal_confluence.py` |
| 14 | Wire into main strategy orchestrator | `src/strategy.py` |
| 15 | Build backtester (walk-forward + Monte Carlo) | `src/backtester.py` |
| 16 | Run baseline backtest, iterate via `/cbt:optimize` | `experiments/` |

---

## Success Criteria

- [ ] Win Rate > 65% blended across sub-strategies (source backtests: 71.2% baseline, up to 82.7% with full Coinglass+timing enhancement)
- [ ] Sharpe Ratio > 1.8
- [ ] Max Drawdown < 20% (prop-firm hard cap: 6% internal / 10% firm limit — this criterion applies to the aggregate multi-cycle backtest, not the live prop account)
- [ ] Passes Prop Firm Phase 1 (10% target) without breaching 3%/6% internal daily/total drawdown buffers in backtest
- [ ] Monthly return $1,500-$3,000 on $50K live account (per README target)

## Account Rules

**Account Type:** prop_firm

| Rule | Value |
|------|-------|
| Phase | 1 |
| Firm Max Drawdown (from initial) | 10% |
| Firm Daily Loss Limit (from prev day) | 5% |
| **Internal safety buffer — Max Daily Loss** | 3.0% (60% of firm limit) |
| **Internal safety buffer — Max Total Drawdown** | 6.0% (60% of firm limit) |
| **Internal — Max Risk/Trade** | 0.5% of account |
| **Internal — Max Trades/Day** | 5 |
| **Internal — Trade Cooldown** | 60 minutes |
| **Internal — Consistency Max** | 25% (no single day > 25% of monthly profit) |
| Profit Target (Phase 1) | 10% |
| Max Leverage | 3x (tiered 2x/2.5x/3x by confluence score; DCB-short capped at 3x regardless of confluence, tighter than the 5x ceiling in the source research doc — prop-firm context overrides) |
| Breach Action | Halt trading |

---

## Kill Criteria

Abandon strategy if:
- [ ] Backtest Sharpe < 1.0 after full iteration cycle
- [ ] Strategy breaches internal 3%/6% daily/total drawdown buffers repeatedly across walk-forward windows
- [ ] On-chain or Coinglass data proves too sparse/unreachable across target sources (same risk already flagged for crypto_algo_trading's funding/CVD dependency)
- [ ] Combined confluence gating cuts trade frequency so much the backtest has too few trades to be statistically meaningful (<20/month per source backtest pacing)

---

## Merge Notes (source-conflict resolutions)

1. **Risk profile conflict:** `STRATEGY_BACKTEST_RESULTS.md` and `ENHANCED_STRATEGY_ANALYSIS1.md` back-test an aggressive personal-account objective (2% risk/trade, 3x leverage, $4K→$50K→$500K compounding target). `README.md`/`config.py` and this repo's existing `prop_firm.enabled: true` state target a prop-firm evaluation account. **Resolved: prop-firm-safe profile wins** (0.5% risk/trade, 3%/6% daily/total DD buffers, 3x max leverage) — the aggressive profile's win-rate/R:R *statistics* (71.2%→82.7% with enhancements, 2.85:1→3.64:1 R:R) are still used as the strategy's expected-performance evidence, just resized to prop-firm risk budget.
2. **Leverage ceiling conflict:** multi-layer framework doc allows up to 8x at 7/7 confluence (DCB-short capped 5x). Backtest doc found 3x Sharpe-optimal even without prop constraints. README hard-caps 3x for prop-firm reasons. **Resolved: hard 3x ceiling always**, confluence only changes *whether* to trade and base sizing within that ceiling, never raises leverage above it.
3. **Stale reference doc:** `BTC_ETH_Gold_Silver_Strategy_Analysis` is dated Dec 26, 2024, 17 months before the other docs' "current" date (May 2026) and describes a different, non-perp swing-trading strategy (spot BTC/ETH/Gold/Silver, RSI<40 entry gate). Its specific price levels are obsolete. **Kept only its generic entry-trigger-checklist pattern** (RSI extreme + 4H reversal candle + volume>150% + Stoch RSI cross + 3-green-close validation) as an additional confirmation layer folded into Range Hunter. ETH/Gold/Silver content is out of scope for a BTC-only strategy.
4. **PDF duplicate:** `ENHANCED_STRATEGY_ANALYSIS.pdf` could not be rendered in this environment (missing poppler-utils) but its filename exactly matches `ENHANCED_STRATEGY_ANALYSIS1.md` (already read in full) — treated as a duplicate export, not re-derived separately. Flag to user if the PDF in fact contains different content.
5. **Macro-as-gate vs macro-as-score:** the multi-layer doc explicitly self-corrects mid-document ("Macro signals: GATED, not scored — failure to gate macro is the single biggest historical source of false longs in 2018 and 2022"). Adopted the gate version, not the earlier scored-layer version in the same doc's weighting table.

---

## Questions for Research Phase

1. Where can on-chain valuation data (MVRV Z-Score, SOPR, Puell Multiple, RHODL Ratio, LTH supply %) actually be sourced from a connector reachable in this environment? None confirmed reachable this session.
2. Where can Coinglass-class data (OI, liquidation heatmap, net long/short delta, large orders) be sourced? None confirmed reachable this session.
3. Does the funding/OI + CVD blocked-data problem (shared with `crypto_algo_trading`) have a workaround, or should both strategies drop to funding-rate-only (no CVD) as a fallback?
4. Are the backtested win-rate/accuracy figures in the source docs (71.2%→82.7%, individual signal accuracy %) independently reproducible against real historical data, or were they estimated/practitioner judgment calls as several source docs themselves flag? Needs `/cbt:research` validation before trusting them as build targets.

---

*Generated by CBT Framework, synthesized from 7 user-supplied source documents (Claude Projects export) per user request to "combine into the optimal combination," 2026-07-23.*
