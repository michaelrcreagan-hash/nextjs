"""
Breakout prop optimizer -- maximize P(pass before breach).

WHY PASS RATE IS THE OBJECTIVE, NOT RETURN OR TRADE WIN RATE
-------------------------------------------------------------
The author confirmed the static drawdown floor DOES NOT RESET AFTER A PAYOUT.
A funded account therefore contains a fixed number of dollars of loss, forever.
It is a finite resource, not a compounding vehicle. The right objective is the
probability of reaching the target before breaching, and the expected number of
payouts a single account yields is:

        E[payouts] = p / (1 - p)          for pass probability p

    p = 0.50 -> 1.0 payouts      p = 0.70 -> 2.3 payouts
    p = 0.60 -> 1.5 payouts      p = 0.80 -> 4.0 payouts

Every point of pass rate compounds into account lifetime. Ten points of return
does not. Trade-level win rate is reported because it was asked for, but it is
NOT optimized against: a 90%-win-rate rule that risks 5R to make 0.2R passes
nothing. Win rate is an output, pass rate is the target.

METHOD
------
Each configuration is replayed from N start dates spaced across the panel.
Overlapping windows are not independent, so a bootstrap CI over start dates is
reported alongside the point estimate, and configs are ranked by the LOWER
bound rather than the point estimate -- ranking on the point estimate of 40
overlapping windows is how you select noise.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.h4_engine import (BARS_PER_MONTH, build_indicators, load, signals,
                           simulate, vol_regime)

OUT = Path(__file__).resolve().parent / "experiments" / "h4_prop"

PROFILES = {
    "classic_10k": dict(account=10_000.0, target_usd=1_000.0,
                        max_dd_usd=600.0, daily_loss_pct=3.0),
    "turbo_200k": dict(account=200_000.0, target_usd=18_000.0,
                       max_dd_usd=6_000.0, daily_loss_pct=3.0),
}

N_STARTS = 60
WARMUP = 1300          # 200-EMA + 1y ATR baseline need room


def evaluate(d, ind, sig, profile, n_starts=N_STARTS, **kw):
    n = d["close"].shape[0]
    last = n - 400
    starts = np.linspace(WARMUP, last, n_starts).astype(int)
    res = [simulate(d, ind, sig, profile, start_bar=int(b), **kw) for b in starts]

    outcomes = [r["outcome"] for r in res]
    n_pass = outcomes.count("PASS")
    passes = np.array([o == "PASS" for o in outcomes], dtype=float)

    # Bootstrap CI over start dates. Windows overlap so this UNDERSTATES the
    # true uncertainty, but it still separates "50% +/- 6" from "50% +/- 20".
    rng = np.random.default_rng(0)
    boot = np.array([rng.choice(passes, size=len(passes), replace=True).mean()
                     for _ in range(2000)])
    lo, hi = np.percentile(boot, [10, 90])

    all_tr = [t for r in res for t in r["trades"]]
    wins = [t for t in all_tr if t["pnl"] > 0]
    pnl = np.array([t["pnl"] for t in all_tr]) if all_tr else np.array([0.0])
    gw = pnl[pnl > 0].sum()
    gl = -pnl[pnl <= 0].sum()
    bars = np.mean([r["bars"] for r in res])
    pass_bars = [r["bars"] for r in res if r["outcome"] == "PASS"]

    return {
        "pass_pct": round(100 * n_pass / len(res), 1),
        "pass_lo": round(100 * lo, 1),
        "pass_hi": round(100 * hi, 1),
        "breach_dd_pct": round(100 * outcomes.count("breach_dd") / len(res), 1),
        "breach_daily_pct": round(100 * outcomes.count("breach_daily") / len(res), 1),
        "unresolved_pct": round(100 * outcomes.count("open") / len(res), 1),
        "trade_win_pct": round(100 * len(wins) / max(len(all_tr), 1), 1),
        "profit_factor": round(float(gw / gl), 2) if gl > 0 else None,
        "avg_r": round(float(np.mean([t["r"] for t in all_tr])), 3) if all_tr else 0.0,
        "trades_per_month": round(len(all_tr) / len(res) / max(bars / BARS_PER_MONTH, 1e-9), 1),
        "median_months_to_pass": round(float(np.median(pass_bars)) / BARS_PER_MONTH, 1) if pass_bars else None,
        "n_trades": len(all_tr),
    }


def fmt_row(label, r):
    pf = f"{r['profit_factor']:>5.2f}" if r["profit_factor"] else "    -"
    mt = f"{r['median_months_to_pass']:>5.1f}" if r["median_months_to_pass"] else "    -"
    return (f"  {label:<38s} {r['pass_pct']:>5.1f}% [{r['pass_lo']:>4.1f}-{r['pass_hi']:>4.1f}] "
            f"{r['breach_dd_pct']:>5.1f}% {r['breach_daily_pct']:>5.1f}% "
            f"{r['trade_win_pct']:>5.1f}% {pf} {r['avg_r']:>6.2f} "
            f"{r['trades_per_month']:>5.1f} {mt}")


HDR = (f"  {'config':<38s} {'PASS':>6s} {'  [80% CI]':>12s} "
       f"{'ddBr':>6s} {'dyBr':>6s} {'win%':>6s} {'PF':>5s} {'avgR':>6s} "
       f"{'t/mo':>5s} {'mo2p':>5s}")


def main():
    d = load()
    print("=" * 118)
    print("BREAKOUT PROP OPTIMIZER -- 4H engine, objective = P(pass before breach)")
    print("=" * 118)
    print(f"  panel: {d['close'].shape[0]} 4H bars x {len(d['symbols'])} symbols "
          f"({d['symbols']})")
    print(f"  static floor NEVER resets after payout -> E[payouts] = p/(1-p)")

    ind = build_indicators(d)
    reg = vol_regime(ind)
    print(f"  vol regime: compression {100*(reg==0).mean():.0f}%  "
          f"normal {100*(reg==1).mean():.0f}%  expansion {100*(reg==2).mean():.0f}%  "
          f"extreme {100*(reg==3).mean():.0f}%")

    results = {}

    # ---------------- Stage 1: which engine? ----------------
    print("\n" + "-" * 118)
    print("  STAGE 1 -- engine selection (Classic $10k, risk 0.5%, 2ATR stop, 2R target)")
    print("-" * 118)
    print(HDR)
    print("-" * 118)
    stage1 = {}
    for eng in ("keltner", "pullback", "donchian"):
        for shorts in (True, False):
            s = signals(d, ind, engine=eng, allow_short=shorts)
            if s.any():
                r = evaluate(d, ind, s, PROFILES["classic_10k"])
                lab = f"{eng}{' L/S' if shorts else ' long-only'}"
                stage1[lab] = r
                print(fmt_row(lab, r))
    results["stage1_engine"] = stage1

    best_eng_label = max(stage1, key=lambda k: stage1[k]["pass_lo"])
    eng = best_eng_label.split()[0]
    shorts = "long-only" not in best_eng_label
    print(f"\n  -> best by CI lower bound: {best_eng_label}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage1.json").write_text(json.dumps(
        {"panel_bars": int(d["close"].shape[0]), "symbols": d["symbols"],
         "results": stage1, "winner": best_eng_label}, indent=2))
    return d, ind, eng, shorts, results


if __name__ == "__main__":
    main()
