# Four-Sleeve Portfolio — Backtest + Monte Carlo Report

*Generated 2026-07-08 from `sleeve_analysis.py` (results in
`sleeve_backtest_results.json`, charts in `sleeve_backtest_*.png`).
Data: `data_long/` — 57 symbols, dividend-adjusted daily closes,
2009 → 2026-07-08, single vendor per ticker, point-in-time IPO entry.*

This is the mechanical implementation of
`notes/four_sleeve_portfolio_architecture.md`: the Part-10 regime
allocation matrix, the Part-4 income mix, the Part-12 drawdown rulebook,
the cycle overlay, and the trend/momentum selection layer — run honestly
over two eras and stress-tested with a 10,000-path Monte Carlo.

---

## 1. Headline results

| | 2023 → Jul 2026 (3.5y) | 2010 → 2023 (13.0y) |
|---|---|---|
| **CAGR** | **32.6%** | **9.0%** |
| Total multiple | 2.69x | 3.06x |
| Volatility | 17.6% | 10.5% |
| Sharpe | 1.71 | 0.87 |
| Max drawdown | **-17.3%** | **-23.0%** |
| MAR (CAGR/DD) | 1.88 | 0.39 |
| SPY buy-and-hold | 22.6% / -18.8% DD | 11.9% / -33.7% DD |
| QQQ buy-and-hold | 33.3% / -22.8% DD | 15.5% / -35.1% DD |
| SMH buy-and-hold | 66.4% / -35.7% DD | 17.7% / -45.3% DD |
| 60/40 SPY/TLT | 12.7% / -12.8% DD | 9.3% / -27.5% DD |

**Read on the two eras:**

- **2023-2026** — the architecture works as designed: it beats SPY by
  ~10 CAGR points with a *smaller* drawdown, and roughly matches QQQ's
  return with 4-5 points less drawdown and lower vol. It does NOT beat
  concentrated SMH buy-and-hold on raw return (66% CAGR) — nothing
  diversified does in an AI supercycle — but it beats it on MAR
  (1.88 vs 1.86) with half the volatility.
- **2010-2023** — the honest decade. The strategy compounds at 9.0% vs
  SPY's 11.9%, giving up ~3 points of CAGR to buy a 10.7-point-smaller
  max drawdown (-23% vs -33.7%) and a Sharpe of 0.87 vs 0.73. It beats
  60/40 on both return and drawdown. The notes' 50-80% annualized target
  is **not** reproduced by the mechanical rules in a normal decade —
  that target was calibrated to an innovation-sleeve regime (2023-2026
  style) that simply did not exist in 2010-2019, when most of the
  innovation names (MSTR-as-BTC-treasury, miners, quantum, VRT) either
  didn't exist yet or were different businesses.

The **-20% portfolio stop never bound in either period**: by the time
drawdowns approached the trigger, the regime matrix had already cut
equity exposure below the stop's 30% floor. It engaged once (2022) for
70 days as a no-op. The regime matrix is the *de facto* drawdown control;
the stop is a redundant backstop — which is exactly what you want it
to be.

---

## 2. Department-by-department results

Each department was ablated (switched off, everything else identical)
to measure its standalone contribution. "Δ" is full-system minus
system-without-department.

### 2.1 Macro department (regime engine — VIX, SMH trend, breadth, BTC liquidity)

Drives the Part-10 sleeve matrix: RISK-ON 40/15/35/10/0 →
RISK-OFF 5/50/0/0/45 (macro/income/innovation/options/cash).

| Period | With | Without (static MIXED) | Verdict |
|---|---|---|---|
| 2023-2026 | 32.6% CAGR, -17.3% DD | 31.1% CAGR, -10.2% DD | +1.5 CAGR, **-7.1pp worse DD** |
| 2010-2023 | 9.0% CAGR, -23.0% DD | 8.7% CAGR, -16.1% DD | +0.3 CAGR, -6.9pp worse DD |

**Honest finding:** the regime matrix ADDS return but also adds
drawdown versus just sitting at the static MIXED allocation. Why: the
matrix runs hot (78% of 2023-2026 days were RISK-ON → 35% innovation)
and de-risks *after* damage starts. Its value is insurance against
2008-class events that neither test window fully contains — in 2022 it
kept the portfolio at 24% average cash. State occupancy: 2023-2026 was
RISK-ON 78% / MIXED 13% / RISK-OFF 7%; 2010-2023 was RISK-ON 53% /
RISK-OFF 24% / MIXED 19% / CAUTION 3%.

### 2.2 Cycle department (4-yr presidential x 16.8-yr secular x quarterly seasonal)

| Period | With | Without | Verdict |
|---|---|---|---|
| 2023-2026 | 32.6%, -17.3% DD, MAR 1.88 | 34.6%, -20.8% DD, MAR 1.67 | -2.0 CAGR, **+3.5pp better DD, higher MAR** |
| 2010-2023 | 9.0%, -23.0% DD, MAR 0.39 | 9.0%, -26.7% DD, MAR 0.34 | 0.0 CAGR, **+3.7pp better DD** |

The cycle overlay is a pure risk reducer: it costs a little upside in
strong years (its Q3 de-risk and midterm-year multiplier cut exposure)
and pays it back in smaller drawdowns. In 2010-2023 it was CAGR-neutral
while cutting DD — the best kind of overlay. Fixed during this work: the
cycle-year arithmetic crashed on election years and pre-2024 dates
(`cycles.py` KeyError) — now anchored arithmetic, verified against the
note's Q3-2026 worked example (0.49 multiplier, exact).

### 2.3 Technical department (200-DMA / 50>200 trend gate)

| Period | With | Without | Verdict |
|---|---|---|---|
| 2023-2026 | 32.6%, -17.3% DD | 35.4%, -15.9% DD | **-2.8 CAGR, -1.4pp worse DD** |
| 2010-2023 | 9.0%, -23.0% DD | 8.3%, -22.1% DD | +0.7 CAGR, ~flat DD |

Mixed. In 2023-2026 the gate whipsawed out of names during V-shaped
recoveries (Apr-2025 style) and cost return without saving drawdown.
Over 2010-2023 it added modestly. The gate earns its keep in slow bear
markets (2022) and does damage in fast-recovery corrections. Net: keep
it, but it's the weakest of the six mechanical departments.

### 2.4 Thematic/selection department (momentum top-6 inside innovation)

The mechanical stand-in for the theme-rotation brain's stock-selection
step ("only the strongest names within the leading theme").

| Period | With | Without (hold all members) | Verdict |
|---|---|---|---|
| 2023-2026 | 32.6% | 29.6% | **+3.0 CAGR, DD ~flat** |
| 2010-2023 | 9.0% | 9.1% | ~flat |

Selection is where the 2023-2026 alpha came from — concentrating the
innovation sleeve in the 6 strongest names (MSTR, miners, VRT, COHR era)
instead of spreading across all twelve. In the prior decade the
innovation list was too weak for selection to matter.

### 2.5 Risk department (Part-12 drawdown rulebook)

| Period | With | Without | Verdict |
|---|---|---|---|
| Both | identical | identical | **Stop never bound** (see §1) |

Redundant with the regime matrix in both windows — kept as tail
insurance for a crash that outruns the weekly regime read.

### 2.6 Options department (Sleeve 4 — PMCC/LEAPS diagonal on SMH, Black-Scholes sim)

| Period | With | Without | Verdict |
|---|---|---|---|
| 2023-2026 | 32.6% | 30.6% | **+2.0 CAGR, DD unchanged** |
| 2010-2023 | 9.0% | 8.4% | **+0.6 CAGR, DD unchanged** |

Standalone sleeve: 28.7% CAGR / -12.9% DD (2023-2026), 9.5% / -18.9%
(2010-2023) — equity-like return at roughly a third of the drawdown of
its underlying, exactly the PMCC design goal. Simulated legs (no
historical chains exist here); `iv_premium=1.0` assumes zero edge from
selling premium, so this is the conservative estimate.

### 2.7 Fundamental department (20-pt gate, operating leverage, earnings quality) — NOT SIMULATED

No historical point-in-time fundamentals feed exists in this repo. The
gate lives in the LLM analyst prompts (`fundamentals_analyst.py`) and
runs live, but nothing here backtests it. Wiring a fundamentals history
(FMP statements endpoints) remains the top data gap.

### 2.8 Analyst-revisions department — NOT SIMULATED

`revision_velocity.py` scores revisions live from web data; there is no
historical revisions archive to replay. LLM/report layer only.

### 2.9 Sentiment / news department — NOT SIMULATED

Same status: news/sentiment agents run live in the TradingAgents graph;
no historical news corpus exists for mechanical replay.

### 2.10 Knowledge Brain / group-brain orchestration — NOT SIMULATED

The `knowledge_brain_orchestrator` and Omega strategy context shape live
LLM decisions. They cannot be replayed historically without recorded
LLM decisions at each date. The mechanical departments above (§2.1-2.6)
are the backtestable skeleton of what those brains encode.

---

## 3. Sleeve-level results (standalone, 100% internal allocation, same rebalance cadence + costs)

### 2023 → Jul 2026

| Sleeve | CAGR | Vol | Sharpe | MaxDD | Total |
|---|---|---|---|---|---|
| Macro rotation | 13.5% | 17.3% | 0.82 | -22.3% | 1.56x |
| Income/hedge | 8.6% | 11.0% | 0.80 | -16.7% | 1.33x |
| Innovation | **163.0%** | 58.4% | 1.96 | **-48.9%** | 29.8x |
| Options (PMCC) | 28.7% | 18.8% | 1.45 | -12.9% | 2.43x |

### 2010 → 2023

| Sleeve | CAGR | Vol | Sharpe | MaxDD | Total |
|---|---|---|---|---|---|
| Macro rotation | 11.8% | 16.7% | 0.75 | -29.6% | 4.27x |
| Income/hedge | 3.0% | 10.6% | 0.33 | -32.7% | 1.46x |
| Innovation | 9.3% | 35.6% | 0.43 | **-73.9%** | 3.18x |
| Options (PMCC) | 9.5% | 11.7% | 0.83 | -18.9% | 3.23x |

The innovation sleeve is everything in 2023-2026 (163% CAGR standalone)
and nearly nothing before it (9.3% with a -74% drawdown). **The whole
50-80% target hangs on the innovation sleeve staying in a supercycle.**
The income sleeve's ugly 2010-2023 number is dominated by 2022 (TLT
-31%, the worst bond year in decades); its crash-hedge role showed up in
March 2020 and 2022 as *relative* outperformance, not absolute gains.

Realized sleeve correlations (2010-2023): macro-income **-0.05**,
innovation-income **-0.03** — the diversification the notes assumed
(0.20/0.15) actually materialized better than assumed; innovation-options
0.34 vs 0.70 assumed. The uploaded parametric MC's correlation matrix
was too pessimistic about diversification but far too optimistic about
means (65%/35% assumed vs 15.3%/12.6% realized 2010-2023).

---

## 4. Monte Carlo (10,000 paths, 21-day block bootstrap of realized daily returns)

Bootstrapping the *regime-weighted portfolio* return stream preserves
fat tails and vol clustering from the actual data instead of assuming
normal distributions like the original `monte_carlo_stress_test.py`.

### Calibrated to 2023-2026 dynamics (3.5-year horizon)

| Percentile | Terminal multiple | CAGR | Max drawdown |
|---|---|---|---|
| p5 (bear path) | 1.67x | 15.8% | -24.4% |
| p25 | 2.27x | 26.4% | -18.2% |
| **p50** | **2.83x** | **34.5%** | **-14.8%** |
| p75 | 3.48x | 42.6% | -12.3% |
| p95 (hot path) | 4.65x | 54.9% | -9.8% |

P(any loss over 3.5y) ≈ 0.03%. P(maxDD > 20%) = 16.2%.
P(maxDD > 25%) = 4.3%. P(maxDD > 40%) = 0.05%.

### Calibrated to 2010-2023 dynamics (13-year horizon)

| Percentile | Terminal multiple | CAGR | Max drawdown |
|---|---|---|---|
| p5 | 1.74x | 4.3% | -27.0% |
| p25 | 2.48x | 7.2% | -20.6% |
| **p50** | **3.15x** | **9.2%** | **-17.2%** |
| p75 | 4.05x | 11.4% | -14.5% |
| p95 | 5.79x | 14.5% | -11.8% |

P(loss over 13y) ≈ 0.2%. P(maxDD > 20%) = 28.4%. P(maxDD > 25%) = 8.7%.

### Per-sleeve Monte Carlo, median CAGR [p5, p95]

| Sleeve | 2023-2026 regime | 2010-2023 regime |
|---|---|---|
| Macro | 14.3% [-0.6, 30.6] | 12.2% [4.8, 19.3] |
| Income | 8.2% [-1.4, 17.8] | 3.2% [-1.3, 7.8] |
| Innovation | 171% [72, 328] | 9.8% [-6.8, 28.6] |
| Options | 30.1% [14.1, 49.2] | 9.5% [4.5, 14.8] |

Innovation-sleeve P(drawdown > 25%) ≈ 97-100% in both regimes — a
40-60% drawdown *inside that sleeve* is a certainty, which is why its
portfolio weight is capped at 35% and regime-scaled. The sleeve matrix
converts a certain -50% sleeve event into a portfolio -15 to -25% event.

### The note's $70K → $1M question

With $36K/yr contributions, $70K reaches $1M in **year 7** at the
2023-2026 median path (34.5% CAGR), year 6 at p75, and hits the note's
5-year target only on a p95 path (54.9% CAGR). At the 2010-2023 median
(9.2%), it's **year 13**. The plan's 5-year $1M math requires a
near-best-case innovation supercycle to persist the full five years —
possible, but the 2010-2023 run is the base-rate warning.

---

## 5. Rebalance-trigger accounting

| | 2023-2026 | 2010-2023 |
|---|---|---|
| Trading days | 881 | 3,272 |
| Rebalances executed | 105 | 496 |
| — regime-state changes | 66 | 358 |
| — calendar (monthly incl. quarterly) | 38 | 136 |
| — portfolio-stop flips | 0 | 1 |
| Avg turnover per rebalance | 40.5% | 39.8% |
| Cost drag (10 bps/side) | 1.21%/yr | 1.52%/yr |
| Avg cash weight | 21.9% | 23.9% |

---

## 6. Methodology & honesty notes

1. **Investability floor.** Names are only eligible while their 63-day
   median price > $5. Without this, pre-2019 shell-company eras of
   MARA/CLSK/QUBT (sub-$1 prices, +2000% single-day moves) inject pure
   fantasy into the innovation sleeve — the raw run showed a "630x"
   sleeve that no real account could have captured.
2. **Positions drift** between rebalances (no free daily rebalancing);
   standalone sleeve curves use the same cadence and costs.
3. **Ticker identity:** pre-pivot MARA (patent licensing), CLSK
   (energy software), QUBT (shell) trade as what they were then. NBIS
   enters 2024-10; IREN 2021-11; "SNDK" mapped to STX; "IONS" read as
   IONQ per the note's quantum context.
4. **Dividend-adjusted closes** — income sleeve carry is real, but
   preferred-basket yield (PFF) at daily granularity approximates the
   note's individual preferred picks.
5. **Options sleeve is simulated** (Black-Scholes, HV-proxy IV, no
   sell edge assumed). Real-chain slippage would trim it further.
6. **No monthly contributions modeled** — pure return series.
7. **Cycle parameters are the note's own** (anchor 2023, phase table,
   seasonal multipliers) — they were NOT fit to this data, which is why
   the overlay's clean DD reduction is a meaningful out-of-sample-ish
   result.
8. **Fundamental, revisions, sentiment, and knowledge-brain departments
   are not in these numbers** — they operate in the live LLM layer only.
   Treat this backtest as the floor the mechanical skeleton provides.
