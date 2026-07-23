# Strategy Idea: btc_prop_strategy_v2

> Seeded from 7 source documents supplied by user (Claude Projects export), combined into one optimal strategy.

## The Idea

BTC perpetual-futures prop-firm strategy combining three mechanically distinct sub-strategies (trend following, mean reversion, funding-rate carry), gated by a 6-layer macro/on-chain/derivatives/technical/cycle/DCB confluence-scoring regime filter, further sharpened with free Coinglass-derived microstructure filters (OI divergence, CVD divergence, liquidation-heatmap proximity, net long/short delta, large-order walls) and calendar/session timing edges (post-FOMC drift, ETF flow direction, best trading session/day-of-week). Hard-coded prop-firm-safe risk management wraps all of it.

## Why It Should Work

Each source document independently backtested a subset of this edge:
- Macro gating (DXY/M2/real-yields) + on-chain extremes (MVRV Z, Puell, RHODL) mark regime and cycle position — degrading but still directionally useful in the post-ETF era (thresholds revised down to reflect diminishing cycle peaks).
- Coinglass derivatives/order-flow filters (OI, funding zone, CVD divergence, liquidation clusters, net delta) independently added +3-8% win rate each in an 8-year backtest (452 trades, 2018-2026), with FOMC timing (+7.8%) and CVD divergence (+6.3%) the strongest single adds.
- Dead-cat-bounce (DCB) short overlay is the highest-R:R setup specifically in confirmed bear regimes (68-75% win rate at top-5 confluence), rank-ordered by historical accuracy (200DMA rejection 82%, SOPR reclaim-fail 80%).
- Session/day timing (USA open 16-18 UTC Mon-Wed, early Asia 00-02 UTC Tue-Thu) adds a further +3-4% by avoiding the empirically worst windows (Europe mid-session, Friday PM).
- The three-sub-strategy architecture (Trend Rider / Range Hunter / Funding Farmer) diversifies across market regimes (trending, ranging, carry) so the book isn't dependent on one regime persisting.

## Entry Logic (rough)

- **Trend Rider (50% alloc):** 9/21 EMA cross + Supertrend + ADX>25 on 4H/1D, gated by macro regime score and boosted by DCB-overlay in confirmed bear.
- **Range Hunter (30% alloc):** RSI(2) extreme + Bollinger Band touch + ADX<20 on 1H, confirmed by volume spike + Stoch RSI reversal (adapted from the Dec-2024 A+ setup checklist).
- **Funding Farmer (20% alloc):** funding rate extreme + CVD divergence on 4H, the highest raw win-rate (70-90%) but shortest hold (24-48h).
- All three gated by: macro regime score, Coinglass confluence (OI/CVD/liquidation/net-delta), and session/day timing filter.

## Exit Logic (rough)

- Trend Rider: EMA cross-back or 2x ATR trailing stop.
- Range Hunter: RSI(2) mean-reversion to 50 or 1x ATR stop.
- Funding Farmer: funding normalizes or 24-48h max hold.
- DCB-short overlay: signal-invalidation exit (three-month-rule override, funding re-flips negative, LTH resumes accumulating).
- Scale-out 50/30/20 across T1/T2/T3 for all directional (non-funding-carry) trades.

## Data Needed

BTC OHLCV (1H/4H/1D/1W), funding rate + OI (per exchange), spot+futures CVD, DXY, Global M2, 10Y real yields, on-chain (MVRV Z, SOPR, Puell, LTH supply %, RHODL, exchange reserves), Coinglass (liquidation heatmap, net long/short delta, large orders), ETF flow data (IBIT/FBTC etc.), FOMC/CPI/NFP calendar.

## Notes

Source docs disagreed on risk profile: one (aggressive $4K→$50K personal-account backtest) used 2% risk/trade and 3x leverage targeting 12x account growth; the other (README/config.py, explicitly prop-firm-purposed) hard-codes 0.5% risk/trade, 3%/6% daily/total drawdown buffers, 3x max leverage. **Resolved in favor of the prop-firm-safe profile** — this strategy folder's `prop_firm.enabled` context and the README's explicit "pass prop firm evaluations" purpose both point that direction; the aggressive-growth profile is a different objective (personal account compounding) and not compatible with prop-firm hard limits. See DISCOVERY.md merge notes for full conflict list.

Fourth source doc (BTC/ETH/Gold/Silver, Dec 26 2024) is 17 months stale relative to the other docs' May 2026 "current" date — kept only for its generic entry-trigger-checklist pattern (RSI<40 + 4H reversal + volume confirmation + Stoch RSI + validation closes), not its specific price levels. ETH/Gold/Silver sections out of scope (BTC-only).

---

*Formalized directly into DISCOVERY.md below given source material was already comprehensive; skipping interactive /cbt:discover Q&A.*
