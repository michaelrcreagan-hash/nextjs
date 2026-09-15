# Quick reference — Breakout prop, 4H crypto

## Fund this one

**ALT combined (long + short), $10,000 classic evaluation**

| | |
|---|---|
| Universe | ETH, SOL, XRP, DOGE, LINK, AVAX, LTC |
| Timeframe | 4H bars |
| Risk per trade | **0.50%** of current equity |
| Stop | **2.0 × ATR(14)** |
| Target | **1.25R** (= 2.5 × ATR) |
| Max concurrent | **3** positions |
| Daily stand-down | flatten all at **−1.5%** from the day's opening equity, no new entries until next day |
| Hard rules | $1,000 target · $600 static floor (never resets) · 3% daily loss limit |

**Expected:** ~17 trades/month · 55–61% win rate · PF 1.43–1.84 · 3–4 months to pass
**Worst regime:** 66.7% pass, 10% breach → **2.0 expected payouts before ruin**

---

## Entry checklist

Every value below is from the **previous closed bar**. Never act on the forming bar.

### LONG — all must be true
- [ ] Prior close **>** Keltner upper = `EMA16 + 1.75 × ATR14`
- [ ] `EMA21 > EMA50`
- [ ] Efficiency Ratio(20) **≥ 0.30**
- [ ] ADX(14) **≥ 25** *and* rising vs 14 bars ago
- [ ] Volatility regime is **normal or expansion** (not compression, not extreme)

### SHORT — all must be true
- [ ] Prior close **<** Keltner lower = `EMA16 − 1.75 × ATR14`
- [ ] `EMA21 < EMA50`
- [ ] Efficiency Ratio(20) **≥ 0.30**
- [ ] ADX(14) **≥ 25** *and* rising vs 14 bars ago
- [ ] Volatility regime is **normal or expansion**

Long and short can never both fire on one symbol — the EMA condition is mutually
exclusive. Measured overlap across the full panel: **0 bars.**

### Volatility regime
Let `r70 = ATR14 / EMA70(ATR14)` and `r1y = ATR14 / EMA2190(ATR14)`.

| Regime | Condition | Trade? |
|---|---|---|
| Extreme | `r1y > 1.6` | no |
| Expansion | `r70 > 1.15` and `r1y > 1.0` | **yes** |
| Compression | `r70 < 0.85` | no |
| Normal | anything else | **yes** |

Evaluated in that order — extreme overrides expansion.

---

## Order management

| | |
|---|---|
| Entry | market at the **open** of the signal bar |
| Stop | `entry − dir × 2.0 × ATR14` |
| Target | `entry + dir × 2.5 × ATR14` |
| Position size | `0.005 × equity ÷ (2.0 × ATR14)` units |
| Notional cap | `equity × leverage ÷ 3` per position |
| Time stop | close at market after **90 bars** (15 days) |
| If a bar hits both | assume the **stop** filled first |

---

## Do not

- **Do not trade long-only.** 0% pass rate at every parameter setting tested, both cohorts.
- **Do not take the $200k turbo.** Nothing clears it. Its target:drawdown is 3:1 vs the classic's 1.67:1.
- **Do not size BTC up to make it work.** BTC-only needs 2.0% risk to finish in time, which leaves it 3 losses from a breach. It fails cost and neighbourhood stress.
- **Do not raise the target past 1.5R.** Every surviving config sits at 1.0–1.5R. Under a floor that never resets, each loss is permanent, so likelier targets beat bigger ones.
- **Do not skip the −1.5% daily stand-down.** It is doing real work in the breach numbers. Overriding it once means trading a different, worse strategy.

---

## Runners-up, with their defect

| Book | Worst-regime pass | Breach | Why not |
|---|---|---|---|
| BTC combined, classic | 83.3% | 10.0% | Neighbouring stop breaches 56.7%; costs ×2 takes breach 10% → 33% |
| ALT short only, classic | 70.0% | 10.0% | Median neighbour is 39% of base — a spike, not a plateau |
| BTC short only, classic | 66.7% | 10.0% | Median neighbour is 47% of base |
| ALT short only, turbo | 56.7% | 13.3% | Median neighbour is 54% of base |
| ALT long only, turbo | 43.3% | **53.3%** | Breach rate disqualifies it outright |
| BTC combined, turbo | 26.7% | 13.3% | Dies entirely at ×2 costs |

---

## Health checks while live

Stop and re-examine if any of these appear:

- Fewer than **10 trades in a month** — the edge depends on ~17/month; below that the clock beats you
- Win rate under **45%** over 30+ trades — bear-window measured floor was 54.6%
- Two daily stand-downs in one week
- Any single loss larger than **1.0R** — means stops are slipping, and the cost stress says that is where this strategy breaks
- Realised profit factor under **1.2** over 50+ trades

## Known blind spot

Six of the eight assets fell in **both** halves of the three-year test window.
This panel contains no altcoin bull market, so **the short engine has never been
tested against one.** If alts enter a sustained uptrend, the short side is
operating out of sample — cut its size until you have live evidence.
