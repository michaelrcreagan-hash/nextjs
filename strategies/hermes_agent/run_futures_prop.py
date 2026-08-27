"""
Goal ask #6 -- US futures prop firm strategy (indices, commodities, rates).

    "another futures prop trading firm available in the usa for futures,
     indicies and commodities ... 4% or more per month on a futures prop
     trading account"

PREVIOUSLY BLOCKED, NOW UNBLOCKED. Every earlier attempt failed on data:
Binance 451s from this environment, Stooq returns an HTML shell instead of CSV,
CoinGecko is crypto-only, and the repo held no futures history. Yahoo's keyless
chart endpoint serves ES/NQ/YM/RTY/CL/GC/SI/HG/ZN/NG, so this is the first time
the ask can be tested rather than deferred.

Reuses the 4H Keltner engine validated for Breakout in
BREAKOUT_OPTIMAL_STRATEGY.md, so the comparison between the crypto and futures
prop programs is like-for-like rather than two differently-tuned systems.

⚠ THE STRUCTURAL DIFFERENCE THAT MATTERS MOST
----------------------------------------------
Breakout's drawdown is STATIC. Most US futures firms (Topstep, Apex, Take
Profit Trader) use a TRAILING drawdown that follows your equity high until the
account is "locked" at some buffer above the start. That is the harder variant,
and it is the one my earliest crypto model wrongly assumed. Under a trailing
floor every new equity high permanently raises the bar, so a strategy that
grinds up and gives back its buffer dies even while profitable overall.

So the crypto result does NOT transfer automatically. This script models the
trailing rule explicitly and reports both variants.

RULES MODELLED (representative Topstep-style $50k Combine -- NOT confirmed with
any specific firm, since none was named):
    account          $50,000
    profit target    $3,000   (6%)
    max drawdown     $2,000   (4%) TRAILING from equity high, locks at start+
    daily loss       $1,000   (2%)
Confirm these against whichever firm you actually pick before relying on any
number here -- the drawdown TYPE matters more than its size.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import src.h4_engine as E
from src.h4_engine import (build_indicators, ema, signals, simulate)

STRATEGY_DIR = Path(__file__).resolve().parent
FUT_DIR = STRATEGY_DIR / "Data" / "futures"
OUT = STRATEGY_DIR / "experiments" / "futures_prop"

PROFILES = {
    "topstep50k_trailing": dict(account=50_000.0, target_usd=3_000.0,
                                max_dd_usd=2_000.0, daily_loss_pct=2.0,
                                trailing=True),
    "topstep50k_static": dict(account=50_000.0, target_usd=3_000.0,
                              max_dd_usd=2_000.0, daily_loss_pct=2.0,
                              trailing=False),
}

# Futures are margin products; a prop account's real constraint is the loss
# limit, not notional leverage. Cap notional at a conservative multiple of
# equity per position so a single instrument cannot dominate.
NOTIONAL_CAP = 4.0
BARS_PER_DAY = 6


def load_4h():
    """Resample the cached hourly futures files to 4H OHLCV on a common grid."""
    raw = {}
    for f in sorted(FUT_DIR.glob("*_1h.csv")):
        sym = f.stem.split("_")[0]
        buckets = {}
        for r in csv.DictReader(f.open()):
            ts = int(r["ts"])
            b = ts - (ts % 14400)
            buckets.setdefault(b, []).append(
                (ts, float(r["open"]), float(r["high"]),
                 float(r["low"]), float(r["close"]), float(r["volume"])))
        out = {}
        for b, rows in buckets.items():
            if len(rows) < 2:      # futures sessions have gaps; 2 of 4 is enough
                continue
            rows.sort()
            out[b] = (rows[0][1], max(x[2] for x in rows),
                      min(x[3] for x in rows), rows[-1][4],
                      sum(x[5] for x in rows))
        raw[sym] = out

    grid = sorted(set.intersection(*(set(v) for v in raw.values())))
    d = {"ts": np.array(grid, dtype=np.int64), "symbols": sorted(raw)}
    for k, i in (("open", 0), ("high", 1), ("low", 2), ("close", 3), ("volume", 4)):
        d[k] = np.ascontiguousarray(
            np.array([[raw[s][t][i] for s in d["symbols"]] for t in grid],
                     dtype=np.float64))
    return d


def simulate_futures(d, ind, sig, profile, risk_pct=0.5, atr_stop=1.5, rr=1.25,
                     max_concurrent=3, start_bar=0, internal_daily_pct=1.0,
                     max_bars_held=90):
    """
    Futures prop run. Same exit/entry logic as the crypto engine, but with the
    TRAILING drawdown option that US futures firms actually use.

    Trailing rule as implemented: the floor is (equity_high - max_dd), and it
    ratchets up with every new equity high but never falls. Once the floor
    reaches the starting balance it locks there -- which is how Topstep-style
    accounts behave and is what makes the early phase the dangerous one.
    """
    n, m = d["close"].shape
    acct = profile["account"]
    target = acct + profile["target_usd"]
    dd = profile["max_dd_usd"]
    trailing = profile["trailing"]
    hard_daily = profile["daily_loss_pct"] / 100.0

    op, hi, lo, cl = d["open"], d["high"], d["low"], d["close"]
    cost_rate = E.TAKER_PCT / 100.0 + E.SLIP_BPS / 10000.0

    equity = acct
    eq_high = acct
    day_anchor = acct
    day_bar0 = start_bar
    day_locked = False
    pos, trades = {}, []
    outcome, out_bar = "open", None

    for t in range(start_bar, n):
        if (t - day_bar0) >= BARS_PER_DAY:
            day_bar0 = t
            day_anchor = equity + sum(
                p["dir"] * p["units"] * (cl[t - 1, j] - p["entry"])
                for j, p in pos.items())
            day_locked = False

        for j in list(pos):
            p = pos[j]
            dirn = p["dir"]
            hit_stop = (lo[t, j] <= p["stop"]) if dirn == 1 else (hi[t, j] >= p["stop"])
            hit_tp = (hi[t, j] >= p["tp"]) if dirn == 1 else (lo[t, j] <= p["tp"])
            timeout = (t - p["bar"]) >= max_bars_held
            if not (hit_stop or hit_tp or timeout):
                continue
            fill = p["stop"] if hit_stop else (p["tp"] if hit_tp else cl[t, j])
            cost = p["units"] * fill * cost_rate
            pnl = dirn * p["units"] * (fill - p["entry"]) - cost - p["entry_cost"]
            equity += pnl
            trades.append({"sym": d["symbols"][j], "dir": dirn, "pnl": pnl,
                           "r": pnl / max(p["risk_usd"], 1e-9),
                           "reason": "sl" if hit_stop else ("tp" if hit_tp else "time"),
                           "bar": t})
            del pos[j]

        marked = equity + sum(
            p["dir"] * p["units"] * (cl[t, j] - p["entry"]) for j, p in pos.items())
        eq_high = max(eq_high, marked)

        # THE floor. Trailing ratchets with equity high but locks at the start
        # balance; static never moves at all.
        floor = min(eq_high - dd, acct) if trailing else acct - dd

        if marked >= target:
            outcome, out_bar = "PASS", t
            break
        if marked <= floor:
            outcome, out_bar = "breach_dd", t
            break
        if marked <= day_anchor * (1 - hard_daily):
            outcome, out_bar = "breach_daily", t
            break

        if not day_locked and marked <= day_anchor * (1 - internal_daily_pct / 100.0):
            for j in list(pos):
                p = pos[j]
                cost = p["units"] * cl[t, j] * cost_rate
                pnl = p["dir"] * p["units"] * (cl[t, j] - p["entry"]) - cost - p["entry_cost"]
                equity += pnl
                trades.append({"sym": d["symbols"][j], "dir": p["dir"], "pnl": pnl,
                               "r": pnl / max(p["risk_usd"], 1e-9),
                               "reason": "internal_stop", "bar": t})
                del pos[j]
            day_locked = True

        if not day_locked and len(pos) < max_concurrent:
            for j in range(m):
                if len(pos) >= max_concurrent or j in pos or sig[t, j] == 0:
                    continue
                a = ind["atr"][t, j]
                if not np.isfinite(a) or a <= 0:
                    continue
                entry = op[t, j]
                dirn = int(sig[t, j])
                risk_px = a * atr_stop
                risk_usd = marked * (risk_pct / 100.0)
                units = risk_usd / risk_px
                cap = marked * NOTIONAL_CAP / max_concurrent
                if units * entry > cap:
                    units = cap / entry
                    risk_usd = units * risk_px
                ec = units * entry * cost_rate
                equity -= ec
                pos[j] = {"dir": dirn, "entry": entry, "units": units,
                          "stop": entry - dirn * risk_px,
                          "tp": entry + dirn * risk_px * rr,
                          "risk_px": risk_px, "risk_usd": risk_usd,
                          "entry_cost": ec, "bar": t}

    return {"outcome": outcome, "bar": out_bar, "trades": trades,
            "bars": (out_bar or n) - start_bar}


def evaluate(d, ind, sig, profile, n_starts=40, warmup=1300, **kw):
    n = d["close"].shape[0]
    starts = np.linspace(warmup, n - 400, n_starts).astype(int)
    res = [simulate_futures(d, ind, sig, profile, start_bar=int(b), **kw)
           for b in starts]
    oc = [r["outcome"] for r in res]
    passes = np.array([o == "PASS" for o in oc], dtype=float)
    rng = np.random.default_rng(0)
    boot = np.array([rng.choice(passes, len(passes), replace=True).mean()
                     for _ in range(2000)])
    tr = [t for r in res for t in r["trades"]]
    pnl = np.array([t["pnl"] for t in tr]) if tr else np.array([0.0])
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    bars = np.mean([r["bars"] for r in res])
    pb = [r["bars"] for r in res if r["outcome"] == "PASS"]
    return {
        "pass_pct": round(100 * oc.count("PASS") / len(res), 1),
        "pass_lo": round(100 * np.percentile(boot, 10), 1),
        "pass_hi": round(100 * np.percentile(boot, 90), 1),
        "breach_dd_pct": round(100 * oc.count("breach_dd") / len(res), 1),
        "breach_daily_pct": round(100 * oc.count("breach_daily") / len(res), 1),
        "trade_win_pct": round(100 * len([t for t in tr if t["pnl"] > 0]) / max(len(tr), 1), 1),
        "profit_factor": round(float(gw / gl), 2) if gl > 0 else None,
        "trades_per_month": round(len(tr) / len(res) / max(bars / 180, 1e-9), 1),
        "median_months_to_pass": round(float(np.median(pb)) / 180, 1) if pb else None,
    }


def row(lab, r):
    pf = f"{r['profit_factor']:>5.2f}" if r["profit_factor"] else "    -"
    mt = f"{r['median_months_to_pass']:>5.1f}" if r["median_months_to_pass"] else "    -"
    return (f"  {lab:<34s} {r['pass_pct']:>5.1f}% [{r['pass_lo']:>4.1f}-{r['pass_hi']:>4.1f}] "
            f"{r['breach_dd_pct']:>5.1f}% {r['breach_daily_pct']:>5.1f}% "
            f"{r['trade_win_pct']:>5.1f}% {pf} {r['trades_per_month']:>5.1f} {mt}")


HDR = (f"  {'config':<34s} {'PASS':>6s} {'  [80% CI]':>12s} {'ddBr':>6s} "
       f"{'dyBr':>6s} {'win%':>6s} {'PF':>5s} {'t/mo':>5s} {'mo2p':>5s}")


def main():
    d = load_4h()
    ind = build_indicators(d)
    sig = signals(d, ind, engine="keltner", allow_short=True)
    print("=" * 110)
    print("FUTURES PROP (ask #6) -- 4H Keltner engine, keyless Yahoo data")
    print("=" * 110)
    print(f"  panel: {d['close'].shape[0]} 4H bars x {len(d['symbols'])} "
          f"({d['symbols']})")
    print(f"  span : {datetime.fromtimestamp(d['ts'][0], tz=timezone.utc).date()} -> "
          f"{datetime.fromtimestamp(d['ts'][-1], tz=timezone.utc).date()}")

    res = {}
    for pname, prof in PROFILES.items():
        print("\n" + "-" * 110)
        print(f"  {pname}: ${prof['account']:,.0f} target ${prof['target_usd']:,.0f} "
              f"maxDD ${prof['max_dd_usd']:,.0f} "
              f"({'TRAILING from equity high' if prof['trailing'] else 'STATIC'}) "
              f"daily {prof['daily_loss_pct']}%")
        print("-" * 110)
        print(HDR)
        print("-" * 110)
        rows = {}
        for lab, kw in (("risk0.25 rr1.25", dict(risk_pct=0.25, rr=1.25)),
                        ("risk0.50 rr1.25", dict(risk_pct=0.5, rr=1.25)),
                        ("risk0.50 rr1.5", dict(risk_pct=0.5, rr=1.5)),
                        ("risk0.75 rr1.5", dict(risk_pct=0.75, rr=1.5)),
                        ("risk0.50 rr2.0", dict(risk_pct=0.5, rr=2.0)),
                        ("risk0.35 rr1.25", dict(risk_pct=0.35, rr=1.25))):
            r = evaluate(d, ind, sig, prof, **kw)
            rows[lab] = r
            print(row(lab, r))
        best = max(rows, key=lambda k: rows[k]["pass_lo"])
        print(f"\n  -> best: {best}  pass {rows[best]['pass_pct']}%  "
              f"win {rows[best]['trade_win_pct']}%  PF {rows[best]['profit_factor']}")
        res[pname] = rows

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(
        {"profiles": PROFILES, "symbols": d["symbols"],
         "bars": int(d["close"].shape[0]),
         "rules_status": "REPRESENTATIVE Topstep-style, NOT confirmed -- no firm named",
         "results": res}, indent=2))
    print(f"\nsaved: experiments/futures_prop/results.json")


if __name__ == "__main__":
    main()
