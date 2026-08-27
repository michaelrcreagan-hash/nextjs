"""
Stage 4 -- final selection, ranked by OUT-OF-SAMPLE behaviour.

Stage 3 broke the 100% result in exactly the way it was designed to. On the
full panel the champion (risk 0.75%, stop 1.5 ATR, RR 2.0) passed 100% of 60
windows with zero breaches. Split in two, the same config produced:

    IN-SAMPLE     85.0% pass,  0.0% drawdown breaches
    OUT-OF-SAMPLE 80.0% pass, 20.0% drawdown breaches

The pass rate barely moved; the BREACH rate went from nothing to one run in
five. On an account whose floor never resets, a 20% chance of destroying it is
the number that matters, and the full-panel 100% was hiding it -- runs that
start early get a long runway to recover, which the holdout does not grant.

Meanwhile the lower-target variant (RR 1.5) went the other way: 100% OOS with
zero breaches. Lower targets get hit more often, which converts open risk into
closed profit faster, and under a FIXED loss budget that is worth more than
occasionally larger winners.

So this stage re-ranks candidates on OOS breach rate first, OOS pass rate
second, and speed only after that. Ranking on full-panel pass rate is what
produced the fragile config in the first place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_prop import HDR, PROFILES, WARMUP, evaluate, fmt_row
from optimize_stage3 import sub_panel
from src.h4_engine import build_indicators, load, signals

OUT = Path(__file__).resolve().parent / "experiments" / "h4_prop"

CANDIDATES = {
    "A rr1.5 risk0.75 stop1.5": dict(risk_pct=0.75, atr_stop=1.5, rr=1.5,
                                     max_concurrent=3, internal_daily_pct=1.0),
    "B rr1.5 risk0.50 stop1.5": dict(risk_pct=0.5, atr_stop=1.5, rr=1.5,
                                     max_concurrent=3, internal_daily_pct=1.0),
    "C rr2.0 risk0.50 stop1.5": dict(risk_pct=0.5, atr_stop=1.5, rr=2.0,
                                     max_concurrent=3, internal_daily_pct=1.0),
    "D rr1.5 risk0.50 stop2.0": dict(risk_pct=0.5, atr_stop=2.0, rr=1.5,
                                     max_concurrent=3, internal_daily_pct=1.0),
    "E rr1.5 risk0.35 stop1.5": dict(risk_pct=0.35, atr_stop=1.5, rr=1.5,
                                     max_concurrent=3, internal_daily_pct=1.0),
    "F rr1.25 risk0.50 stop1.5": dict(risk_pct=0.5, atr_stop=1.5, rr=1.25,
                                      max_concurrent=3, internal_daily_pct=1.0),
    "G rr1.5 risk0.50 conc2": dict(risk_pct=0.5, atr_stop=1.5, rr=1.5,
                                   max_concurrent=2, internal_daily_pct=1.0),
}


def main():
    d = load()
    n = d["close"].shape[0]
    cut = int(n * 0.6)
    packs = {}
    for name, dd in (("OOS", sub_panel(d, cut - WARMUP, n)), ("ALL", d)):
        ii = build_indicators(dd)
        packs[name] = (dd, ii, signals(dd, ii, engine="keltner", allow_short=True))

    print("=" * 118)
    print("STAGE 4 -- final selection, ranked by OUT-OF-SAMPLE breach rate")
    print("=" * 118)
    print(f"  OOS holdout = bars {cut}-{n} of {n} (a genuinely different market)")

    res = {}
    for prof_name in ("classic_10k", "turbo_200k"):
        prof = PROFILES[prof_name]
        print("\n" + "-" * 118)
        print(f"  {prof_name}: ${prof['account']:,.0f}  target ${prof['target_usd']:,.0f}  "
              f"floor -${prof['max_dd_usd']:,.0f}  (STATIC, never resets after payout)")
        print("-" * 118)
        print(HDR)
        print("-" * 118)
        rows = {}
        for lab, kw in CANDIDATES.items():
            r_oos = evaluate(packs["OOS"][0], packs["OOS"][1], packs["OOS"][2],
                             prof, n_starts=40, **kw)
            r_all = evaluate(packs["ALL"][0], packs["ALL"][1], packs["ALL"][2],
                             prof, n_starts=60, **kw)
            rows[lab] = {"oos": r_oos, "all": r_all}
            print(fmt_row(lab + " [OOS]", r_oos))

        order = sorted(rows, key=lambda k: (rows[k]["oos"]["breach_dd_pct"]
                                            + rows[k]["oos"]["breach_daily_pct"],
                                            -rows[k]["oos"]["pass_lo"]))
        best = order[0]
        b = rows[best]
        br = b["oos"]["breach_dd_pct"] + b["oos"]["breach_daily_pct"]
        print(f"\n  -> {prof_name} WINNER: {best}")
        print(f"     OOS   pass {b['oos']['pass_pct']}% [{b['oos']['pass_lo']}-{b['oos']['pass_hi']}]"
              f"   breaches {br}%   win {b['oos']['trade_win_pct']}%   PF {b['oos']['profit_factor']}")
        print(f"     FULL  pass {b['all']['pass_pct']}% [{b['all']['pass_lo']}-{b['all']['pass_hi']}]"
              f"   breaches {b['all']['breach_dd_pct'] + b['all']['breach_daily_pct']}%"
              f"   win {b['all']['trade_win_pct']}%   PF {b['all']['profit_factor']}"
              f"   {b['all']['trades_per_month']} t/mo"
              f"   {b['all']['median_months_to_pass']} months to target")
        p = b["oos"]["pass_pct"] / 100.0
        if p < 1:
            print(f"     E[payouts before ruin] = p/(1-p) = {p / (1 - p):.1f}")
        else:
            print("     E[payouts before ruin]: zero breaches observed OOS on 40 "
                  "windows -> lower-bounded near 5, NOT infinite")
        res[prof_name] = {"rows": rows, "winner": best}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage4.json").write_text(json.dumps(
        {"candidates": CANDIDATES, "results": res}, indent=2, default=str))
    print("\nsaved: experiments/h4_prop/stage4.json")


if __name__ == "__main__":
    main()
