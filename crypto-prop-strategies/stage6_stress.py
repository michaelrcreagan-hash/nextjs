"""
Stage 6 -- stress the finalists before believing them.

Stage 5's BTC winner asked for 2.0% risk per trade, which was the largest value
on the grid. A parameter that settles on the edge of its own search range has
not been optimized, it has been truncated: the sweep is still climbing and
simply ran out of room, so the reported figure may be the best of what was
offered rather than the best available. Three checks here, any of which can
disqualify a configuration that looked fine in stage 5.

  1. BOUNDARY. Extend risk past the grid edge. If performance keeps climbing,
     the stage 5 answer was an artifact of where the grid stopped. If it flattens
     or turns over, 2.0% sits on a plateau and can be trusted -- and a plateau is
     what you want anyway, because a peak means neighbouring parameters fail and
     live trading never lands exactly on the peak.

  2. NEIGHBOURHOOD. Move every parameter one grid step in each direction and
     report the spread. A configuration whose neighbours collapse was fitted to
     the sample, whatever its own number says. The honest figure to quote for a
     strategy is closer to its neighbourhood's worst than to its own best.

  3. COSTS. Rerun at double fees and double slippage. Backtested edges are
     routinely thinner than the cost assumption that produced them, and a
     4H strategy taking 4-17 trades a month at 2.0% risk is not cheap to run.
     A configuration that only works at the assumed cost is a configuration
     that works on paper.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import src.engine as E
from src.engine import PROFILES, make_signal
from stage3_prop import OUT, eval_window
from stage4_regime import SPLIT
from stage5_final import build

# The stage 5 minimax winners worth stressing.
FINAL = {
    "BTC combined classic_10k": ("BTC", "combined", "classic_10k",
                                 dict(risk_pct=2.0, atr_stop=1.5, rr=1.25,
                                      internal_daily_pct=1.5)),
    "BTC short classic_10k": ("BTC", "short", "classic_10k",
                              dict(risk_pct=1.5, atr_stop=1.25, rr=1.5,
                                   internal_daily_pct=1.5)),
    "ALT short classic_10k": ("ALT", "short", "classic_10k",
                              dict(risk_pct=0.5, atr_stop=1.25, rr=2.0,
                                   internal_daily_pct=1.5)),
    "ALT combined classic_10k": ("ALT", "combined", "classic_10k",
                                 dict(risk_pct=0.5, atr_stop=2.0, rr=1.25,
                                      internal_daily_pct=1.5)),
    "ALT short turbo_200k": ("ALT", "short", "turbo_200k",
                             dict(risk_pct=0.5, atr_stop=2.0, rr=1.5,
                                  internal_daily_pct=1.0)),
    "BTC combined turbo_200k": ("BTC", "combined", "turbo_200k",
                                dict(risk_pct=0.75, atr_stop=1.5, rr=1.5,
                                     internal_daily_pct=1.5)),
}

BOOKS = {}


def get(book):
    if book not in BOOKS:
        BOOKS[book] = build(book)
    return BOOKS[book]


def score(book, side, pname, params):
    d, ind, mc, sigs, _ = get(book)
    n = d["close"].shape[0]; cut = int(n * SPLIT)
    kw = dict(params, max_concurrent=mc)
    w = {k: eval_window(d, ind, sigs[side], PROFILES[pname], *v, 30, **kw)
         for k, v in (("bull", (1300, cut)), ("bear", (cut, n)))}
    if any(x is None for x in w.values()):
        return None
    return {"bull": w["bull"], "bear": w["bear"],
            "worst_pass": min(w[k]["pass"] for k in w),
            "worst_lo": min(w[k]["pass_lo"] for k in w),
            "worst_breach": max(w[k]["breach"] for k in w)}


def line(lab, s):
    if not s:
        return f"    {lab:<34s}  (no result)"
    return (f"    {lab:<34s} bull {s['bull']['pass']:>5.1f}%/{s['bull']['breach']:>4.1f}b  "
            f"bear {s['bear']['pass']:>5.1f}%/{s['bear']['breach']:>4.1f}b  "
            f"WORST pass {s['worst_pass']:>5.1f}% lo {s['worst_lo']:>5.1f}% "
            f"breach {s['worst_breach']:>5.1f}%")


def main():
    out = {}

    print("=" * 122)
    print("TEST 1 -- BOUNDARY: does performance keep climbing past the grid edge?")
    print("=" * 122)
    for lab, (book, side, pname, p) in FINAL.items():
        if p["risk_pct"] < 1.5:
            continue
        print(f"\n  {lab}   (stage 5 chose risk {p['risk_pct']})")
        seq = {}
        for r in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0):
            s = score(book, side, pname, dict(p, risk_pct=r))
            seq[r] = s
            mark = "  <-- stage 5" if r == p["risk_pct"] else ""
            print(line(f"risk {r}", s) + mark)
        out.setdefault("boundary", {})[lab] = seq
        best = max(seq, key=lambda r: (seq[r]["worst_lo"] if seq[r] else -1))
        print(f"    -> peak worst-case lower bound at risk {best}; "
              f"{'PLATEAU, grid edge was not binding' if best <= p['risk_pct'] else 'STILL CLIMBING -- stage 5 was truncated'}")

    print("\n" + "=" * 122)
    print("TEST 2 -- NEIGHBOURHOOD: one grid step in each direction")
    print("=" * 122)
    STEPS = {"atr_stop": [1.25, 1.5, 2.0], "rr": [1.0, 1.25, 1.5, 2.0],
             "internal_daily_pct": [1.0, 1.5]}
    for lab, (book, side, pname, p) in FINAL.items():
        base = score(book, side, pname, p)
        print(f"\n  {lab}")
        print(line("BASE", base))
        nb = {}
        for k, vals in STEPS.items():
            i = vals.index(p[k]) if p[k] in vals else None
            for j in ({i - 1, i + 1} & set(range(len(vals)))) if i is not None else ():
                s = score(book, side, pname, dict(p, **{k: vals[j]}))
                nb[f"{k}={vals[j]}"] = s
                print(line(f"{k} -> {vals[j]}", s))
        vals = [v["worst_lo"] for v in nb.values() if v]
        brs = [v["worst_breach"] for v in nb.values() if v]
        if vals:
            med = float(np.median(vals))
            # "A neighbour collapses" was too lenient a test: it passed a
            # configuration whose every neighbour halved, so long as none hit
            # zero. What matters is whether the base result is representative
            # of its neighbourhood or is a spike standing above it, so the
            # median neighbour is compared against the base, and a neighbour
            # that breaches heavily disqualifies regardless of pass rate.
            ratio = med / base["worst_lo"] if base["worst_lo"] > 0 else 0.0
            tag = ("FRAGILE -- base is a spike, median neighbour is "
                   f"{100*ratio:.0f}% of it" if ratio < 0.60 else
                   "FRAGILE -- a neighbour breaches heavily" if max(brs) > 25.0 else
                   "robust -- neighbourhood holds")
            print(f"    -> neighbourhood worst-case lower bound spans "
                  f"{min(vals):.1f}% to {max(vals):.1f}%, median {med:.1f}% "
                  f"(base {base['worst_lo']:.1f}%)  {tag}")
            nb["_summary"] = {"median": med, "ratio": round(ratio, 2),
                              "max_breach": max(brs), "verdict": tag}
        out.setdefault("neighbourhood", {})[lab] = {"base": base, "neighbours": nb}

    print("\n" + "=" * 122)
    print("TEST 3 -- COSTS: double fees and double slippage")
    print("=" * 122)
    t0, s0 = E.TAKER_PCT, E.SLIP_BPS
    for lab, (book, side, pname, p) in FINAL.items():
        print(f"\n  {lab}")
        row = {}
        for mult in (1.0, 2.0, 3.0):
            E.TAKER_PCT, E.SLIP_BPS = t0 * mult, s0 * mult
            s = score(book, side, pname, p)
            row[mult] = s
            print(line(f"costs x{mult:g}  "
                       f"({E.TAKER_PCT:.3f}% + {E.SLIP_BPS:.0f}bps)", s))
        E.TAKER_PCT, E.SLIP_BPS = t0, s0
        d2 = (row[2.0]["worst_lo"] - row[1.0]["worst_lo"]) if row[2.0] and row[1.0] else None
        if d2 is not None:
            print(f"    -> doubling costs moves the worst-case lower bound by "
                  f"{d2:+.1f}pp{'  SURVIVES' if row[2.0]['worst_lo'] > 0 else '  DIES'}")
        out.setdefault("costs", {})[lab] = row

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage6_stress.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nsaved: experiments/stage6_stress.json")


if __name__ == "__main__":
    main()
