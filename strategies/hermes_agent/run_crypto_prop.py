"""
Goal ask #5 -- bull/bear crypto strategy for a Breakout-style prop account.

  "seperately create a bull market and bear market prop trading strategy for
   crypto via the breakout prop trading firm ... the goal is to make 70k a
   year 4% or more per month on a 100k crypto prop account"

Runs on Data/crypto_panel_5y.csv (5.01y, 25 names, Coinbase daily).

⚠ PROP RULES ARE ASSUMED, NOT CONFIRMED
----------------------------------------
Breakout's actual rule set was never supplied and I could not verify it from
here. This models the HARDER of the two common variants, so results are
conservative rather than flattering:

    max drawdown   10%, TRAILING FROM HIGH-WATER MARK
    daily loss      5%, measured from the previous day's closing equity
    monthly target  4%
    breach          account halts permanently

If Breakout measures max drawdown from the INITIAL balance instead (the softer
variant), survival improves materially -- the floor stops rising as the account
grows. Confirm before relying on any number here. `config.yaml`'s `prop_firm`
block already carries these fields.

WHAT THE MONTE CARLO SAID THIS NEEDS (GOAL_RECONCILIATION.md)
--------------------------------------------------------------
4%/month is reachable at PF ~1.3-1.8 IF frequency is 20-40 trades/month, and
per-trade risk dominates survival: at PF 2.0, moving 1% -> 2% risk cuts
12-month survival from 91.7% to 25.0%. So the design target is small risk,
high frequency. This script measures whether a real breakout rule on real
crypto data actually delivers that PF -- rather than assuming it.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

STRATEGY_DIR = Path(__file__).resolve().parent
PANEL = STRATEGY_DIR / "Data" / "crypto_panel_5y.csv"
OUT = STRATEGY_DIR / "experiments" / "crypto_prop"

# Prop account rules (assumed -- see module docstring).
ACCOUNT = 100_000.0
MAX_DD_PCT = 10.0
DAILY_LOSS_PCT = 5.0
MONTHLY_TARGET_PCT = 4.0
TRAILING_DD = True

# Costs: Breakout is a crypto prop firm, so perp-style taker fees apply,
# not Coinbase spot. Using the Hyperliquid figures from config.yaml's
# venue_costs as the closest real reference the project has.
TAKER_PCT = 0.035
SLIP_BPS = 5.0


def load_panel():
    rows = list(csv.DictReader(PANEL.open()))
    syms = [c for c in rows[0] if c != "Date"]
    dates = np.array([r["Date"] for r in rows])
    px = np.full((len(rows), len(syms)), np.nan)
    for i, r in enumerate(rows):
        for j, s in enumerate(syms):
            v = r[s]
            if v not in ("", "None", None):
                px[i, j] = float(v)
    return dates, syms, px


def rolling_extreme(px, window, kind):
    """Trailing max/min over `window` bars, ending at t-1 (never includes t)."""
    n, m = px.shape
    out = np.full((n, m), np.nan)
    f = np.nanmax if kind == "max" else np.nanmin
    allnan = np.isnan(px)
    for t in range(window + 1, n):
        w = px[t - window:t]
        # Skip all-NaN columns rather than letting nanmax warn on them; a name
        # that has not listed yet must produce NaN, not a spurious extreme.
        ok = ~allnan[t - window:t].all(axis=0)
        if ok.any():
            out[t, ok] = f(w[:, ok], axis=0)
    return out


def atr_proxy(px, window=14):
    n, m = px.shape
    tr = np.zeros_like(px)
    tr[1:] = np.abs(px[1:] - px[:-1])
    out = np.full((n, m), np.nan)
    allnan = np.isnan(px)
    for t in range(window + 1, n):
        ok = ~allnan[t - window:t].all(axis=0)
        if ok.any():
            out[t, ok] = np.nanmean(tr[t - window:t][:, ok], axis=0)
    return out


def regime(btc, fast=50, slow=200):
    """
    BULL when BTC is above both MAs, BEAR when below both, else NEUTRAL (flat).

    Both MAs are shifted one bar. The neutral band matters: a prop account
    cannot afford to be positioned during the chop between regimes, where a
    trend rule whipsaws and the daily-loss limit does the rest.
    """
    n = len(btc)
    r = np.zeros(n, dtype=np.int8)      # 0 neutral, 1 bull, -1 bear
    for t in range(slow + 1, n):
        p = btc[t - 1]
        f = np.nanmean(btc[t - 1 - fast:t - 1])
        s = np.nanmean(btc[t - 1 - slow:t - 1])
        if p > f and p > s:
            r[t] = 1
        elif p < f and p < s:
            r[t] = -1
    return r


def run(dates, syms, px, breakout_n=20, risk_pct=0.75, atr_mult=2.5,
        max_concurrent=5, rr=2.0, allow_short=True):
    n, m = px.shape
    hi = rolling_extreme(px, breakout_n, "max")
    lo = rolling_extreme(px, breakout_n, "min")
    atr = atr_proxy(px)
    btc = px[:, syms.index("BTC")]
    reg = regime(btc)

    equity = ACCOUNT
    peak = ACCOUNT
    curve = np.zeros(n)
    prev_day_eq = ACCOUNT
    halted = False
    halt_reason = None
    halt_bar = None

    # open positions: sym -> dict
    open_pos = {}
    trades = []

    for t in range(n):
        if halted:
            curve[t] = equity
            continue

        # ---- manage open positions ----
        for j in list(open_pos):
            p = px[t, j]
            if np.isnan(p):
                continue
            pos = open_pos[j]
            d = pos["dir"]
            hit_stop = (d == 1 and p <= pos["stop"]) or (d == -1 and p >= pos["stop"])
            hit_tp = (d == 1 and p >= pos["tp"]) or (d == -1 and p <= pos["tp"])
            if hit_stop or hit_tp:
                gross = pos["units"] * p
                cost = gross * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
                pnl = d * pos["units"] * (p - pos["entry"]) - cost - pos["entry_cost"]
                equity += pnl
                trades.append({"sym": syms[j], "dir": d, "entry": pos["entry"],
                               "exit": p, "pnl": pnl,
                               "reason": "tp" if hit_tp else "sl",
                               "bar_in": pos["bar"], "bar_out": t})
                del open_pos[j]

        # ---- breach checks (before new entries) ----
        # BUG FIXED: this previously tested `equity` (realized cash only)
        # against `prev_day_eq` (marked, including unrealized). Whenever a
        # position was open and in profit, realized < marked and the daily-loss
        # rule fired spuriously -- which is why every arm "breached" in
        # early 2022 on 5-20 trades. Prop firms mark to market, so both sides
        # of every comparison must be the marked value.
        marked = equity
        for j, pos in open_pos.items():
            p = px[t, j]
            if not np.isnan(p):
                marked += pos["dir"] * pos["units"] * (p - pos["entry"])

        floor = (peak if TRAILING_DD else ACCOUNT) * (1 - MAX_DD_PCT / 100.0)
        if marked <= floor:
            halted, halt_reason, halt_bar = True, "max_drawdown", t
            curve[t] = marked
            continue
        if marked <= prev_day_eq * (1 - DAILY_LOSS_PCT / 100.0):
            halted, halt_reason, halt_bar = True, "daily_loss", t
            curve[t] = marked
            continue

        # ---- entries ----
        direction = reg[t]
        if direction != 0 and len(open_pos) < max_concurrent:
            cands = []
            for j in range(m):
                if j in open_pos or np.isnan(px[t, j]) or np.isnan(atr[t, j]):
                    continue
                if atr[t, j] <= 0:
                    continue
                if direction == 1 and not np.isnan(hi[t, j]) and px[t, j] > hi[t, j]:
                    cands.append((px[t, j] / hi[t, j], j))
                elif direction == -1 and allow_short and not np.isnan(lo[t, j]) \
                        and px[t, j] < lo[t, j]:
                    cands.append((lo[t, j] / px[t, j], j))
            cands.sort(reverse=True)
            for _, j in cands[:max_concurrent - len(open_pos)]:
                p = px[t, j]
                risk_usd = equity * (risk_pct / 100.0)
                stop_dist = atr[t, j] * atr_mult
                if stop_dist <= 0:
                    continue
                units = risk_usd / stop_dist
                notional = units * p
                # A prop account is not margin-unlimited; cap notional at 5x equity
                if notional > equity * 5:
                    units = equity * 5 / p
                    notional = units * p
                entry_cost = notional * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
                open_pos[j] = {
                    "dir": direction, "entry": p, "units": units,
                    "stop": p - direction * stop_dist,
                    "tp": p + direction * stop_dist * rr,
                    "entry_cost": entry_cost, "bar": t,
                }
                equity -= entry_cost

        mark = equity
        for j, pos in open_pos.items():
            p = px[t, j]
            if not np.isnan(p):
                mark += pos["dir"] * pos["units"] * (p - pos["entry"])
        curve[t] = mark
        peak = max(peak, mark)
        prev_day_eq = mark

    return {"curve": curve, "trades": trades, "halted": halted,
            "halt_reason": halt_reason, "halt_bar": halt_bar,
            "regime": reg, "final": curve[-1]}


def summarize(res, dates, label):
    tr = res["trades"]
    curve = res["curve"]
    valid = curve > 0
    c = curve[valid]
    if len(c) < 2 or not tr:
        return {"label": label, "n_trades": len(tr), "error": "no trades"}
    pnl = np.array([t["pnl"] for t in tr])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    years = (np.datetime64(dates[-1]) - np.datetime64(dates[0])).astype(int) / 365.25
    cagr = (c[-1] / ACCOUNT) ** (1 / years) - 1
    dd = (c / np.maximum.accumulate(c) - 1).min()

    # monthly returns -- the metric the prop target is actually stated in
    months = {}
    for i, d in enumerate(dates):
        if curve[i] > 0:
            months.setdefault(str(d)[:7], []).append(curve[i])
    mret = []
    keys = sorted(months)
    for a, b in zip(keys, keys[1:]):
        mret.append(months[b][-1] / months[a][-1] - 1)
    mret = np.array(mret) if mret else np.array([0.0])
    hit = (mret >= MONTHLY_TARGET_PCT / 100.0).mean()

    return {
        "label": label,
        "final_equity": round(float(c[-1]), 2),
        "cagr_pct": round(100 * cagr, 2),
        "max_dd_pct": round(100 * dd, 2),
        "profit_factor": round(float(pf), 3),
        "n_trades": len(tr),
        "trades_per_month": round(len(tr) / (years * 12), 1),
        "win_rate_pct": round(100 * len(wins) / len(tr), 1),
        "expectancy_usd": round(float(pnl.mean()), 2),
        "halted": res["halted"],
        "halt_reason": res["halt_reason"],
        "halt_date": str(dates[res["halt_bar"]]) if res["halt_bar"] else None,
        "median_monthly_pct": round(100 * float(np.median(mret)), 2),
        "months_hitting_4pct": round(100 * float(hit), 1),
        "n_months": len(mret),
    }


def main():
    dates, syms, px = load_panel()
    reg = regime(px[:, syms.index("BTC")])
    print("=" * 100)
    print("BREAKOUT-STYLE CRYPTO PROP -- bull/bear, $100k, 10% trailing DD, "
          "5% daily loss, 4%/mo target")
    print("=" * 100)
    print(f"  panel   : {len(dates)} bars, {len(syms)} names, {dates[0]} -> {dates[-1]}")
    print(f"  regime  : bull {100*(reg==1).mean():.1f}%  "
          f"bear {100*(reg==-1).mean():.1f}%  neutral {100*(reg==0).mean():.1f}%")
    print(f"  ⚠ prop rules ASSUMED (harder variant) -- confirm with Breakout")

    print("\n" + "-" * 100)
    print(f"  {'arm':<34s} {'CAGR':>8s} {'maxDD':>8s} {'PF':>6s} {'trades':>7s} "
          f"{'t/mo':>6s} {'win%':>6s} {'med mo':>7s} {'4%mo':>6s} {'halted':>16s}")
    print("-" * 100)

    results = []
    grid = [
        ("bull+bear risk0.5%", dict(risk_pct=0.5, allow_short=True)),
        ("bull+bear risk0.75%", dict(risk_pct=0.75, allow_short=True)),
        ("bull+bear risk1.0%", dict(risk_pct=1.0, allow_short=True)),
        ("bull+bear risk2.0%", dict(risk_pct=2.0, allow_short=True)),
        ("BULL ONLY risk0.75%", dict(risk_pct=0.75, allow_short=False)),
        ("bull+bear bo10 risk0.75%", dict(risk_pct=0.75, breakout_n=10)),
        ("bull+bear bo40 risk0.75%", dict(risk_pct=0.75, breakout_n=40)),
        ("bull+bear rr3 risk0.75%", dict(risk_pct=0.75, rr=3.0)),
    ]
    for label, kw in grid:
        r = run(dates, syms, px, **kw)
        s = summarize(r, dates, label)
        results.append(s)
        if "error" in s:
            print(f"  {label:<34s} {'no trades':>60s}")
            continue
        halt = f"{s['halt_reason']} {s['halt_date']}" if s["halted"] else "-"
        print(f"  {label:<34s} {s['cagr_pct']:>7.2f}% {s['max_dd_pct']:>7.2f}% "
              f"{s['profit_factor']:>6.2f} {s['n_trades']:>7d} "
              f"{s['trades_per_month']:>6.1f} {s['win_rate_pct']:>5.1f}% "
              f"{s['median_monthly_pct']:>6.2f}% {s['months_hitting_4pct']:>5.1f}% "
              f"{halt:>16s}")
    print("-" * 100)

    ok = [r for r in results if "error" not in r and not r["halted"]]
    print(f"\n  arms surviving 5 years without a breach: {len(ok)} of {len(results)}")
    if ok:
        best = max(ok, key=lambda r: r["profit_factor"])
        print(f"  best surviving PF: {best['label']}  PF {best['profit_factor']}  "
              f"CAGR {best['cagr_pct']}%  {best['trades_per_month']} trades/mo")
        print(f"\n  REQUIRED (per GOAL_RECONCILIATION Monte Carlo): PF 1.8-2.0 at "
              f"15-20+ trades/month")
        print(f"  ACHIEVED                                       : PF "
              f"{best['profit_factor']} at {best['trades_per_month']} trades/month")
        verdict = (best["profit_factor"] >= 1.8
                   and best["trades_per_month"] >= 15
                   and best["median_monthly_pct"] >= 4.0)
        print(f"\n  VERDICT: {'MEETS the 4%/month target' if verdict else 'DOES NOT meet the 4%/month target'}")
    else:
        print("  every arm breached. The 4%/month target is not reachable with this rule set.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({
        "prop_rules": {"account_usd": ACCOUNT, "max_dd_pct": MAX_DD_PCT,
                       "trailing_from_hwm": TRAILING_DD,
                       "daily_loss_pct": DAILY_LOSS_PCT,
                       "monthly_target_pct": MONTHLY_TARGET_PCT,
                       "status": "ASSUMED -- harder variant; confirm with Breakout"},
        "costs": {"taker_pct": TAKER_PCT, "slippage_bps": SLIP_BPS,
                  "note": "Hyperliquid perp figures from config venue_costs"},
        "panel": {"bars": len(dates), "symbols": syms,
                  "range": [str(dates[0]), str(dates[-1])]},
        "regime_occupancy_pct": {"bull": round(100*float((reg==1).mean()),1),
                                 "bear": round(100*float((reg==-1).mean()),1),
                                 "neutral": round(100*float((reg==0).mean()),1)},
        "arms": results,
        "trials": len(results),
    }, indent=2))
    print(f"\nsaved: experiments/crypto_prop/results.json")


if __name__ == "__main__":
    main()
