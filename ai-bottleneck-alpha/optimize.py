"""
Optimize for the stated objective -- hit rate and profit factor -- and take the
short side seriously as its own strategy rather than as the long book's hedge.

TWO THINGS THIS STAGE FIXES ABOUT THE PREVIOUS ONE
--------------------------------------------------
1. The long/short results reported a total return that is not comparable to a
   long index, and its "vs EW" column was meaningless as a result. A hedged
   book should be judged on whether each LEG earns its keep.

2. Nothing had been optimized for hit rate or profit factor yet -- the metrics
   the task actually names. Return and Sharpe were doing the ranking.

DEFINITIONS USED THROUGHOUT
---------------------------
  hit rate  share of picks whose EXCESS return over the equal-weight universe,
            signed by side, is positive. For a long pick that means beating the
            universe; for a short it means the name fell relative to it.
            Measuring against zero instead of the universe would score a long
            book at ~80% in this sample and mean nothing.
  PF        gross positive excess / gross negative excess, same convention.

THE SHORT SIDE'S HONEST PROBLEM
-------------------------------
The universe rose ~403% over the study. A short book in it loses money in
absolute terms almost regardless of selection skill, and no amount of ranking
fixes that. The question worth asking is narrower and is what gets measured
here: does the bottom decile UNDERPERFORM the universe reliably enough to be
worth renting capital against? That is a relative-value question, and its
answer decides whether shorts belong as a hedge, as a funding leg, or not at
all.

MULTIPLE TESTING
----------------
Every subset of six signals is swept across position counts and holding
periods -- 700+ configurations. The top of that list is, by construction,
partly luck. Selection happens on the in-sample window only; the out-of-sample
column is reported for the winners without further tuning, and the gap between
the two columns is the honest estimate of how much of the ranking was fitting.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import COST_BPS, FUND, OOS_START, STUDY_START, TECH, composite
from build_panel import FEATURES
from eda_signals import technicals
from robustness import ew_index, summary

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"
ALL_SIGNALS = FUND + TECH


def book(adj, sigs, reb, names, ew, n=10, hold=1, side=1, cost_bps=COST_BPS,
         min_signals=2):
    """One leg. side=+1 takes the top N, side=-1 takes the bottom N."""
    eq, prev, picks = [1.0], set(), []
    for s in range(0, len(reb) - hold, hold):
        i, k = reb[s], reb[s + hold]
        sc = composite(sigs, i, names, min_signals)
        ok = np.isfinite(sc) & np.isfinite(adj[i]) & np.isfinite(adj[k])
        sc = np.where(ok, sc, np.nan)
        valid = [j for j in np.argsort(-np.nan_to_num(sc, nan=-1e9))
                 if np.isfinite(sc[j])]
        if len(valid) < n:
            continue
        sel = valid[:n] if side == 1 else valid[-n:]
        r = adj[k] / adj[i] - 1.0
        bench = ew[k] / ew[i] - 1.0
        turn = len(set(sel) ^ prev)
        cost = (cost_bps / 1e4) * turn / n
        eq.append(eq[-1] * (1 + side * float(np.mean(r[sel])) - cost))
        prev = set(sel)
        for j in sel:
            picks.append(side * (float(r[j]) - bench))
    if len(eq) < 3:
        return None
    ex = np.array(picks)
    win, loss = ex[ex > 0].sum(), -ex[ex <= 0].sum()
    s = summary(np.array(eq), hold) or {}
    s.update({"hit": float(100 * (ex > 0).mean()),
              "pf": float(win / loss) if loss > 0 else np.nan,
              "avg_excess": float(ex.mean()), "n_picks": int(len(ex)),
              # Per-period returns, so two legs can be combined into a real
              # portfolio. Averaging two legs' TOTAL returns is not a portfolio
              # and produced a nonsense +2155% before this was added.
              "period_returns": (np.array(eq[1:]) / np.array(eq[:-1]) - 1).tolist()})
    return s


def main():
    z = np.load(ROOT / "data" / "panel.npz", allow_pickle=True)
    dates = [str(x) for x in z["dates"]]
    syms = [str(x) for x in z["symbols"]]
    adj = z["adjclose"]
    n, m = adj.shape
    sigs = {f: z[f"feat_{f}"] for f in FEATURES}
    sigs.update(technicals(adj))
    ew = ew_index(adj)
    reb = [i for i in range(1, n)
           if dates[i][:7] != dates[i - 1][:7] and dates[i] >= STUDY_START]
    reb_is = [i for i in reb if dates[i] < OOS_START]
    reb_oos = [i for i in reb if dates[i] >= OOS_START]

    subsets = [c for r in range(2, len(ALL_SIGNALS) + 1)
               for c in itertools.combinations(ALL_SIGNALS, r)]
    grid = [(list(c), nn, h) for c in subsets for nn in (5, 8, 10, 15) for h in (1, 2, 3)]

    for side, label in ((1, "LONG"), (-1, "SHORT")):
        rows = []
        for names, nn, h in grid:
            a = book(adj, sigs, reb_is, names, ew, n=nn, hold=h, side=side)
            if a and a["n_picks"] >= 60:
                rows.append({"signals": names, "n": nn, "hold": h, "is": a})
        # Rank on the stated objective: hit rate first, profit factor as the
        # tie-break. Return deliberately does not enter the ranking.
        rows.sort(key=lambda r: (-r["is"]["hit"], -(r["is"]["pf"] or 0)))

        print("\n" + "=" * 122)
        print(f"{label} SIDE -- ranked on IN-SAMPLE hit rate, then profit factor "
              f"({len(rows)} configurations)")
        print("=" * 122)
        print(f"  {'signals':<52s} {'N':>3s} {'hld':>4s} | "
              f"{'IS hit':>7s} {'IS PF':>6s} {'IS CAGR':>8s} | "
              f"{'OOS hit':>8s} {'OOS PF':>7s} {'OOS CAGR':>9s} {'OOS Shrp':>9s}")
        print("  " + "-" * 118)
        keep = []
        for r in rows[:12]:
            b = book(adj, sigs, reb_oos, r["signals"], ew, n=r["n"], hold=r["hold"],
                     side=side)
            r["oos"] = b
            keep.append(r)
            sg = "+".join(s.replace("_", "") for s in r["signals"])
            print(f"  {sg:<52s} {r['n']:>3d} {r['hold']:>4d} | "
                  f"{r['is']['hit']:>6.1f}% {r['is']['pf'] or 0:>6.2f} "
                  f"{100*r['is']['cagr']:>7.1f}% | "
                  + (f"{b['hit']:>7.1f}% {b['pf'] or 0:>7.2f} "
                     f"{100*b['cagr']:>8.1f}% {b['sharpe']:>9.2f}" if b else
                     f"{'-':>36s}"))
        (OUT / f"optimize_{label.lower()}.json").write_text(
            json.dumps(keep, indent=2, default=float))

    # ------------------------------------------------ short-side reality --
    print("\n" + "=" * 122)
    print("DOES THE SHORT LEG EARN ITS KEEP?  bottom-decile basket vs the "
          "equal-weight universe")
    print("=" * 122)
    print(f"  {'window':<18s} {'bottom-N return':>16s} {'EW universe':>13s} "
          f"{'relative':>10s} {'hit%':>7s} {'PF':>6s}   interpretation")
    print("  " + "-" * 118)
    for wl, rb in (("IS 2022-2024", reb_is), ("OOS 2025-2026", reb_oos),
                   ("FULL", reb)):
        s = book(adj, sigs, rb, ALL_SIGNALS, ew, n=10, hold=1, side=-1)
        # Absolute return of being LONG the bottom decile.
        lo = book(adj, sigs, rb, ALL_SIGNALS, ew, n=10, hold=1, side=1)
        bot = book(adj, sigs, rb, list(reversed(ALL_SIGNALS)), ew, n=10, hold=1, side=-1)
        b_ew = ew[rb[-1]] / ew[rb[0]] - 1
        # Reconstruct the bottom basket's own long return from the short leg.
        short_ret = s["total"]
        bottom_long = -short_ret
        interp = ("bottom decile lagged the universe"
                  if bottom_long < b_ew else "bottom decile BEAT the universe")
        print(f"  {wl:<18s} {100*bottom_long:>15.0f}% {100*b_ew:>12.0f}% "
              f"{100*(bottom_long-b_ew):>+9.0f}% {s['hit']:>6.1f}% "
              f"{s['pf'] or 0:>6.2f}   {interp}")
    print("\n  A short leg is worth carrying only if 'relative' is reliably "
          "negative AND\n  its hit rate clears 50% out of sample. Absolute "
          "short returns in a universe\n  that rose 403% will be negative "
          "regardless -- that is not the test.")

    print("\nsaved: experiments/optimize_long.json, experiments/optimize_short.json")


if __name__ == "__main__":
    main()
