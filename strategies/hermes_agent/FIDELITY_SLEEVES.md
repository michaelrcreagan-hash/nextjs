# Fidelity Sleeve Analysis — goal ask #1

**Source:** `Portfolio_Positions_Aug232026.xlsx`, exported 2026-08-23 19:56 ET
**Account:** Z34628250 "Joint WROS" — taxable joint brokerage, margin enabled
**Reproduce:** `python3 analyze_fidelity.py`

The goal asked to "focus on the high beta investments, yield/income
investments, options trades and macro hedge trades in fidelity." Those four
sleeves are now sized against what is actually held rather than an assumed
allocation. Two findings below change the whole project's framing, not just
this account.

---

## The account

| | |
|---|---:|
| gross long | $30,533.98 |
| short option value | −$2,947.00 |
| pending (unsettled) activity | −$8,590.93 |
| **net equity** | **$18,996.05** |
| positions | 132 |
| average position | $208.99 |
| cost basis | $37,852.92 |
| unrealized P/L | −$2,878.01 (−7.6%) |

$18,996 is confirmed two independent ways: gross positions plus pending
activity, and back-solving the export's own "Percent of account" column
(median implies $18,997). This is a hard number, unlike the four figures the
author flagged as miscalculated.

---

## The four sleeves

| sleeve | n | value | % net equity | cost basis | unrealized |
|---|---:|---:|---:|---:|---:|
| high beta | 101 | $19,026.41 | 100.2% | $21,113.05 | −$2,086.64 |
| options | 17 | $4,086.00 | 21.5% | $12,603.94 | −$771.42 |
| yield / income | 3 | $3,250.20 | 17.1% | $2,527.39 | +$172.16 |
| macro hedge | 11 | $1,224.37 | 6.4% | $1,608.54 | −$192.11 |
| **total** | **132** | **$27,586.98** | **145.2%** | | |

Sleeves sum to 145% of net equity because $8,591 of unsettled activity is
financed — **this book is running on margin**, at roughly 1.45× gross. That
matters directly: `config.yaml` sets `leverage.enabled: false` for the
hermes_agent baseline on the reasoning that the core mechanism's evidenced
benefit is drawdown reduction. The live Fidelity book is already levered in
the opposite direction of that decision.

Classification is by *purpose*, not wrapper — a VIX or TLT call counts as a
macro hedge, not as generic options exposure. Full per-position mapping in
`experiments/fidelity/positions_by_sleeve.csv`.

### What each sleeve actually contains

**High beta (101 positions, $19.0k).** Semis and AI infrastructure (MU, LITE,
SNDK, CRDO, COHR, ONTO, MRVL, NVDA, AMAT, LRCX, KLAC), crypto miners (WULF,
IREN, CLSK, CORZ, HIVE), power/industrial AI derivatives (VRT, GEV, VST, POWL,
MOD, NVT, HUBB), plus space, quantum and biotech satellites. The sleeve exists
and is genuinely high beta. It is also where the capacity problem lives.

**Options (17 legs, $4.1k net).** Dominated by one structure: a **MSTR Dec-2028
$90/$80 put spread** (long $90 at +$3,220, short $80 at −$2,685, net debit
≈$535, max payoff $1,000). My classifier files it under options because MSTR
is not a macro underlying, but *structurally it is a crypto crash hedge* and
should be read as one. The rest are long-dated calls on crypto-linked names
(BMNR, IBIT, GLXY, SOFI, HIVE, BITO) and a NVDA Sep-2026 220/235 call spread.
Note the sleeve's cost basis is $12,604 against $4,086 of value — **−$771
unrealized on the surviving legs, but the sleeve has already destroyed most of
what was spent on it.** Several legs are near-total losses (HIVE $12 call
−72%, IBIT $33 put −96%, MP $100 call −90%, TLT $84 call −74%).

**Yield / income (3 positions, $3.25k).** STRC (Strategy Inc variable-rate
preferred, $2,666), SATA (Strive variable-rate preferred 10.413%, $551), FIAT
(YieldMax short-Fiat, $33). This is the only sleeve with positive unrealized
P/L (+$172). It is also **not really income** in the diversifying sense: STRC
and SATA are preferreds issued by crypto-treasury companies. Their coupon is
credit-linked to the same asset the rest of the book is long.

**Macro hedge (11 positions, $1.22k, 6.4%).** PFIX (rate vol), UUP (dollar),
GLDM (gold), VIX Nov-2026 20/50 call spread, TLT and IEF calls, SOXS (3× inverse
semis), BNO/DBO/IYE (oil). The intent is right and the instrument selection is
reasonable. **The size is not**: 6.4% of equity hedging a book that is 100%+
gross high beta. A hedge that small changes the outcome of a drawdown by a
rounding error.

---

## Finding 1 — the capital gap is closed

Fidelity was the last unquantified account. With it:

| account | value | share |
|---|---:|---:|
| Merrill IRA | $9,860 | 9.9% |
| Coinbase spot #1 | $19,846 | 19.9% |
| Coinbase spot #2 | $25,000 | 25.1% |
| Hyperliquid perps | $26,000 | 26.1% |
| **Fidelity** | **$18,996** | **19.1%** |
| **total** | **$99,702** | |

The $1.5M goal math assumed $100,000. The identified total is **$99,702** — a
gap of $298. That assumption was sound.

⚠️ The other four figures still carry the author's own "my calculation was
incorrect" flag. Only the Fidelity number is independently verified here.

---

## Finding 2 — the book is 77.5% crypto, and this is the finding that matters

Crypto-linked exposure across all four accounts:

| source | amount |
|---|---:|
| Coinbase spot #1 | $19,846 |
| Coinbase spot #2 | $25,000 |
| Hyperliquid perps | $26,000 |
| Fidelity crypto-linked (24 positions) | $6,423 |
| **total** | **$77,269 = 77.5% of the whole portfolio** |

This reframes the goal's central benchmark. The stated target is to *"outperform
BTC by more than a 3 to 1 multiple."* But the portfolio is already, in
substance, a leveraged bet on crypto. Three consequences:

1. **Beating BTC 3:1 while being 77.5% crypto is close to a contradiction.**
   To beat an asset by 3× you need meaningful exposure to something *other*
   than that asset, or leverage on it. There is no third source of return
   here — the non-crypto 22.5% is mostly AI-semis, which has been positively
   correlated with crypto through this cycle.
2. **Portfolio risk numbers must NET the Fidelity crypto sleeve, not add it.**
   The 24 crypto-linked Fidelity positions duplicate beta the Coinbase and
   Hyperliquid sleeves already carry. Any risk figure that treats Fidelity as
   an independent sleeve overstates diversification.
3. **The 6.4% macro hedge is sized against the wrong number.** It is not
   hedging a $19k equity book, it is the only offset to $77k of one-directional
   crypto exposure. That is a 1.6% hedge ratio.

---

## Finding 3 — the capacity problem is now confirmed in two of four accounts

**79 of 132 Fidelity positions are under $200**, totalling $8,604 (45.3% of net
equity). Average position across the book: $209.

This is the same structure as the Merrill IRA (69 positions averaging ~$143)
that drove `config.yaml`'s `min_position_value_usd: 1000` capacity guard. That
floor would forbid **79 of the 132 positions actually held here**.

Barber & Odean (2000) measured a 6.5pp/yr cost drag on exactly this profile —
high position count, small size, high turnover — with gross returns nearly
identical across activity levels. The entire gap was costs. Two of the four
accounts now display it.

The step-5 baseline measured costs at 2.15% of capital over 2.09 years and
concluded costs were "real, minor, not what's killing this." **That conclusion
was drawn from a simulated book obeying the $1,000 floor.** The live book does
not obey it, so the real-world cost drag is materially higher than the backtest
reports. The floor is not a hypothetical guard — it is a change to current
behaviour.

---

## What I'd do with this account

Ordered by expected effect, not by effort:

1. **Resize the macro hedge to the exposure it is actually hedging.** 6.4% of
   Fidelity is 1.6% of the portfolio. If the hedge is meant to protect $77k of
   crypto beta, it needs to be sized against $77k — and it may belong at the
   portfolio level rather than inside Fidelity at all.
2. **Consolidate the 79 sub-$200 positions.** They are 45% of equity spread so
   thin that no single one can move the account, while each pays full
   round-trip cost. This is the highest-confidence, lowest-risk improvement
   available anywhere in the portfolio, and it needs no forecast to be right.
3. **Recognise the yield sleeve is not diversifying.** STRC and SATA are
   crypto-treasury preferreds. If the thesis is income that survives a crypto
   drawdown, these do not provide it.
4. **Decide about the margin.** Gross is 1.45× net. That is a live leverage
   decision contradicting the baseline config's `leverage.enabled: false`,
   and it should be deliberate rather than a by-product of unsettled activity.
5. **Stop treating Fidelity crypto as diversification.** Net it against the
   Coinbase and Hyperliquid sleeves in every portfolio-level calculation.

Items 1–3 and 5 are analysis conclusions that need no backtest. Item 4 is the
author's call.
