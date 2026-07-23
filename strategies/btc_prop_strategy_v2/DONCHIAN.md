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

*Generated by CBT Framework — research/deep-analyze/iterate/optimize pass, 2026-07-23*
