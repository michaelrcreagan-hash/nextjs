# Donchian 4H — The Strategy That Survived

**Date:** 2026-07-23
**Pipeline:** /cbt:research (web) → build → grid + walk-forward → risk-frontier + challenge-pass simulation
**Data:** 18,692 OKX 4H bars, BTC-USDT, 2018-07 → 2026-07

---

## Why this strategy

Web research converged on one 4H approach with multi-source evidence of surviving both bull and bear regimes: **Donchian channel breakout, long/short, higher-timeframe trend filter, ATR trailing stop** — Turtle-style, documented positive through 2017 bull / 2018 bear / 2021 bull / 2022 bear / 2023 recovery, and category-consistent with the only academically-validated component from RESEARCH.md (SFI 2025 Donchian-ensemble paper, Sharpe 1.5-1.6).

Sources: [QuantPedia multi-timeframe BTC study](https://quantpedia.com/how-to-design-a-simple-multi-timeframe-trend-strategy-on-bitcoin/) (Sharpe 0.80 with higher-TF filter), [QuantifiedStrategies Donchian trend-following](https://quantifiedstrategies.substack.com/p/donchian-trend-following-strategy) (20/55 system positive across all regimes since 2017), [TradingView Donchian+ATR-trail robustness across 2.5-3.5 multipliers](https://es.tradingview.com/script/NeEiwmDq-Donchian-Breakout-with-ATR-Trailing-Stop-Trend-Following/), prop-challenge risk guides ([For Traders](https://fortraders.com/blog/5-proven-strategies-to-pass-a-prop-firm-challenge), [CryptoFundTrader](https://cryptofundtrader.com/pass-crypto-prop-firm-challenge-guide/)).

## Rules (final, validated config)

```
Timeframe:    4H bars
Entry long:   close > highest high of last 20 bars AND close > EMA(120 bars) [daily-trend filter]
Entry short:  close < lowest low of last 20 bars AND close < EMA(120)
Exit:         2.5x ATR(14) trailing stop only (ratchets, never loosens). No profit target.
Position:     one at a time, signal on bar close, execute next bar open
Sizing:       risk% of equity / stop distance, 3x leverage cap
Costs:        0.04% taker + 0.02% slippage per side
```

## Results (vs the killed merged strategy)

| Metric | Killed v2 build (best) | **Donchian 4H (lb=20, trail=2.5, filter on)** |
|--------|------------------------|------------------------------------------------|
| Full-history Sharpe | 0.006 | **1.073** |
| OOS Sharpe (5-window walk-forward) | -0.608 | **+0.428 — only positive OOS of the entire session** |
| CAGR (0.5% risk) | ~0% | 9.9% |
| Max drawdown | -6.46% | **-4.40%** |
| Profit factor | 1.01 | **1.80** |
| Trades (8.5yr) | 127 | 462 (OOS windows: 121, well above 30-min significance) |
| Win rate | 29.9% | 40.9% (classic trend profile: small losses, big winners) |

Independent sanity check: full-period Sharpe 1.07 ≈ QuantPedia's published 0.80 for the same approach — the edge **reproduces** from literature, unlike the source-doc claims that died in testing.

Overfitting checks: OOS positive (unique), IS:OOS ratio 2.7:1 (degradation present — expect live closer to OOS 0.4-0.7 than IS 1.15), parameters stable across trail 2.5-3.5 grid, trade count sufficient. Filter-on beats filter-off on risk-adjusted basis at every lookback.

## Risk frontier (challenge math)

Sharpe is risk-invariant; CAGR and DD scale with the risk dial:

| Risk/trade | CAGR | Max DD | 60-day challenge pass | Breach | Unlimited-time pass | Median days to +10% |
|-----------|------|--------|----------------------|--------|--------------------|--------------------|
| 0.5% | 9.9% | -4.4% | 3% | 0% | — | — |
| **0.75%** | **14.9%** | **-6.6%** | 9% | **0%** | **99.2%** | 205 |
| **1.0%** | **19.9%** | **-8.7%** | 14% | 1.5% | **94.7%** | 160 |
| 1.25% | 25.0% | -10.8% | 19% | 5.4% | 86.0% | 125 |
| 1.5% | 30.0% | -12.8% | 23% | 14.5% | — | — |
| 2.0% | 40.1% | -16.8% | 35% | 21.1% | — | — |

(612 rolling 60-day windows for time-limited; 251-286 windows for unlimited-time barrier analysis: first hit of +10% vs -6%.)

## Verdict on the actual request

**"Pass the prop challenge":** achievable with high historical probability — **at 0.75-1.0% risk, 95-99% of historical start dates eventually hit +10% before breaching -6%,** median 5-7 months. Pick a firm with no time limit (common now). Time-limited 60-day challenges drop pass odds to 9-14% per attempt purely because BTC doesn't trend on demand — but with ~0-1.5% breach risk, a failed attempt is a timeout (retry), not a blown account.

**"5% a month":** does not exist at survivable risk. 5%/month = 60%+/yr, needs ~3% risk/trade on this edge → breach odds >40%/attempt and certain eventual account loss. Realistic sustainable rate on the funded account: **1.2-1.7%/month (CAGR 15-20%) at 0.75-1.0% risk.** Any strategy document promising 5%/month at prop-firm drawdown limits is describing risk-of-ruin, not income — this session already killed one such document set with 594 backtests.

**"Bull or bear":** yes — long/short symmetric, trend filter picks direction; the 2018 and 2022 bears are inside the backtest and the equity curve survived both with PF 1.8.

## Recommended deployment config

```yaml
strategy: donchian_4h
entry_lookback: 20        # 4H bars
trail_atr_mult: 2.5
atr_period: 14
daily_filter: true        # EMA(120 x 4H)
risk_per_trade_pct: 0.75  # challenge phase; may raise to 1.0 on funded account
max_leverage: 3
expectation: OOS Sharpe 0.4-0.7, CAGR 12-20%, maxDD 7-9%, months not weeks to target
```

Caveats: single asset, single strategy, 8.5yr sample; IS/OOS degradation is real; costs modeled at 0.06%/side — a firm with worse spreads erodes the edge; forward-test on demo before paying a challenge fee.

---

# Addendum — Deep Analysis + Multi-Asset Iteration (2026-07-27)

## ⚠️ Monte Carlo correction: the risk table above is sequence-lucky

The risk frontier above reports the **single historical path's** max drawdown (-6.6% at 0.75% risk). Bootstrap resampling of the trade sequence (10,000 iterations, sizing-normalized to per-trade percentage returns so equity-relative sizing is preserved) shows that path was favorably ordered:

| Risk/trade | CAGR | Historical max DD | **MC median max DD** | **P(hit -6% internal)** | **P(hit -10% firm limit)** | P(-10%) over 2yr |
|-----------|------|-------------------|---------------------|------------------------|---------------------------|------------------|
| 0.25% | 5.0% | — | -3.5% | 4.2% | **0.1%** | 0.0% |
| 0.35% | 6.9% | — | -4.9% | 24.6% | **1.1%** | 0.1% |
| 0.50% | 9.9% | -4.4% | -6.8% | 68.3% | **10.4%** | 1.3% |
| 0.60% | 11.9% | — | -8.2% | 87.9% | **23.8%** | 4.1% |
| 0.75% | 14.9% | -6.6% | **-10.2%** | 98.2% | **52.6%** | 12.0% |
| 1.00% | 19.9% | -8.7% | **-13.3%** | 100.0% | **86.6%** | 32.7% |

**The 0.75% risk level previously recommended carries a 52.6% chance of blowing a 10%-max-drawdown funded account over an 8.5-year career** (12% within any 2 years). The single backtest path hid this. This supersedes the 0.75-1.0% recommendation above.

## Deep analysis (BTC, 0.75% risk, 462 trades)

Per-year: profitable in 8 of 9 years. Worst: 2021 (-$446, essentially flat), 2025 (+$3,255). Best: 2023 (+$36,758), 2024 (+$26,283).

Directional symmetry — the "bull or bear" question answered with real numbers:

| Split | Trades | Win rate | Net | Profit factor |
|-------|--------|----------|-----|---------------|
| Long | 250 | 41.6% | +$91,908 | **2.02** |
| Short | 212 | 40.1% | +$28,918 | **1.42** |
| BTC above 200-day MA (bull) | 235 | 40.9% | +$94,686 | **2.08** |
| BTC below 200-day MA (bear) | 227 | 41.0% | +$26,140 | **1.36** |

Both directions and both macro regimes are profitable, but **bear-regime performance is roughly one-third of bull-regime performance**. The strategy survives bears; it does not thrive in them. Plan income around bull-weighted expectations.

Distribution: avg win $1,482 vs avg loss $583 (2.54x). **Top 5 trades = 53% of all net profit.** Max consecutive losses: 9. Classic trend-following shape — you must sit through long losing streaks to catch the few large winners, and missing a couple of the big ones changes the outcome materially.

## Multi-asset portfolio (the actual fix)

Single-asset drawdown risk forces risk/trade down to ~0.35-0.5%, capping CAGR near 7-10%. Diversifying across imperfectly-correlated majors (same rules, shared equity pool, concurrent positions) raises the ceiling. Data: BTC 18,692 + ETH 18,716 + SOL 12,758 OKX 4H bars.

| Portfolio | Risk/trade | Sharpe | CAGR | MC median DD | P(-10%) 8.5yr | P(-10%) 2yr |
|-----------|-----------|--------|------|--------------|---------------|-------------|
| BTC only | 0.50% | 1.073 | 9.9% | -6.8% | 10.4% | 1.3% |
| **BTC+ETH** | **0.35%** | **1.221** | **11.8%** | -6.3% | **5.6%** | **0.8%** |
| BTC+ETH | 0.50% | 1.218 | 16.8% | -8.9% | 32.3% | 8.0% |
| **BTC+ETH+SOL** | **0.35%** | **1.225** | **13.7%** | -7.0% | **9.7%** | **1.8%** |
| BTC+ETH+SOL | 0.30% | 1.226 | 11.8% | -6.0% | 3.8% | 0.7% |
| BTC+ETH+SOL | 0.50% | 1.222 | 19.7% | -9.9% | 48.5% | 11.8% |

**Diversification is a free improvement on both axes:** BTC+ETH at 0.35% beats BTC-only at 0.50% on return (11.8% vs 9.9%) *and* on ruin risk (5.6% vs 10.4%). Portfolio Sharpe rises 1.073 → 1.22. Benefit saturates by 2-3 assets. Per-asset contribution at 0.5% risk: BTC +$103,786 / ETH +$54,453 / SOL +$37,411 — all three positive independently, so this isn't one asset carrying the book.

## Final recommendation (supersedes the config above)

```yaml
strategy: donchian_4h_multiasset
assets: [BTC-USDT, ETH-USDT, SOL-USDT]   # BTC+ETH alone captures most of the benefit
entry_lookback: 20         # 4H bars
trail_atr_mult: 2.5
atr_period: 14
daily_filter: true         # EMA(120 x 4H)
risk_per_trade_pct: 0.35   # per position, on shared equity -- do NOT exceed 0.5%
max_leverage: 3
expected: CAGR ~13-14% (≈1.1%/month), MC median DD -7%, P(blowing 10% limit within 2yr) ~1.8%
```

Revised answers:
- **Pass the challenge:** yes, at 0.35% risk on a no-time-limit firm. Slower (target is months out) but ruin risk is genuinely low (~2% over two years).
- **5%/month:** confirmed impossible. Reaching even 20% CAGR (1.5%/month) pushes 2-year ruin probability to ~12%; 5%/month would require risk levels where account loss is near-certain. **Honest ceiling is ~1.1-1.4%/month.**
- **Bull or bear:** works in both, but expect ~3x better results in bull regimes (PF 2.08 vs 1.36). Do not budget bull-market income during a bear.

Remaining untested: the SFI paper's *ensemble* variant (aggregating multiple Donchian lookbacks rather than a single 20-bar channel) — the literature suggests this raises Sharpe further and is the clearest next iteration.

---

*Generated by CBT Framework — research/deep-analyze/iterate/optimize pass, 2026-07-23; deep-analysis + multi-asset addendum 2026-07-27*
