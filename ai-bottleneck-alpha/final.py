"""
Final configuration, chosen for stability rather than for rank.

627 configurations were swept. The top of that list is partly luck, and picking
it is how a study reports a number it cannot reproduce. So the recommended
configuration is required to clear three bars instead of one:

  1. Every component signal was positive in at least four of five calendar
     years in the EDA -- no signal is carried on its average alone.
  2. The neighbourhood holds. Position count and holding period are moved one
     step in each direction; if the result only exists at one setting it is a
     fit, not a strategy.
  3. Out-of-sample hit rate and profit factor clear the in-sample ones, or come
     close. A large IS/OOS gap is the signature of selection bias.

The chosen long configuration is NOT the highest-ranked one. `mom_12m +
mom_over_vol` scored higher in sample but is two collinear momentum signals
with no fundamental input, which makes it a pure trend bet that happens to have
been measured through a historic trend. The recommendation carries two
fundamentals and one technical so that it can disagree with price.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import OOS_START, STUDY_START
from build_panel import FEATURES
from eda_signals import technicals
from optimize import book
from robustness import ew_index

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"

LONG_SIG = ["eps_yoy", "om_delta", "mom_12m"]
SHORT_SIG = ["dist_200dma", "mom_over_vol"]
N, HOLD = 5, 2


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
    W = {"IS 2022-2024": [i for i in reb if dates[i] < OOS_START],
         "OOS 2025-2026": [i for i in reb if dates[i] >= OOS_START],
         "FULL 2022-2026": reb}

    out = {}
    for side, name, sg in ((1, "LONG", LONG_SIG), (-1, "SHORT", SHORT_SIG)):
        print("=" * 108)
        print(f"{name}  --  {' + '.join(sg)}   top {N}, {HOLD}-month hold")
        print("=" * 108)
        print(f"  {'window':<16s} {'hit%':>7s} {'PF':>7s} {'avg excess':>12s} "
              f"{'CAGR':>9s} {'Sharpe':>8s} {'maxDD':>8s} {'picks':>7s}")
        print("  " + "-" * 104)
        for w, rb in W.items():
            r = book(adj, sigs, rb, sg, ew, n=N, hold=HOLD, side=side)
            if not r:
                continue
            out[f"{name}|{w}"] = r
            print(f"  {w:<16s} {r['hit']:>6.1f}% {r['pf'] or 0:>7.2f} "
                  f"{100*r['avg_excess']:>11.1f}% {100*r['cagr']:>8.1f}% "
                  f"{r['sharpe']:>8.2f} {100*r['maxdd']:>7.1f}% {r['n_picks']:>7d}")

        print(f"\n  neighbourhood (OOS hit% / PF) -- does it survive moving one step?")
        print(f"      {'':<10s}" + "".join(f"{'hold '+str(h):>16s}" for h in (1, 2, 3)))
        for nn in (3, 5, 8, 10):
            row = f"      top {nn:<6d}"
            for h in (1, 2, 3):
                r = book(adj, sigs, W["OOS 2025-2026"], sg, ew, n=nn, hold=h, side=side)
                row += (f"{r['hit']:>9.1f}%/{r['pf'] or 0:<5.2f}" if r
                        else f"{'-':>16s}")
            print(row)
        print()

    # ------------------------------------------------- combined book --
    print("=" * 108)
    print("MARKET-NEUTRAL COMBINATION  (long top 5 / short bottom 5, "
          "50% gross each side)")
    print("=" * 108)
    print(f"  {'window':<16s} {'return':>9s} {'CAGR':>9s} {'Sharpe':>8s} "
          f"{'maxDD':>8s}   vs SPY")
    print("  " + "-" * 104)
    spy = z["bench_SPY"]
    for w, rb in W.items():
        L = book(adj, sigs, rb, LONG_SIG, ew, n=N, hold=HOLD, side=1)
        S = book(adj, sigs, rb, SHORT_SIG, ew, n=N, hold=HOLD, side=-1)
        if not (L and S):
            continue
        # Combine PERIOD BY PERIOD -- 50% gross in each leg, rebalanced each
        # period. Averaging the two legs' total returns is not a portfolio.
        lp, sp = np.array(L["period_returns"]), np.array(S["period_returns"])
        k = min(len(lp), len(sp))
        comb = 0.5 * lp[:k] + 0.5 * sp[:k]
        eqc = np.cumprod(1 + comb)
        tot = float(eqc[-1] - 1)
        yrs = k * HOLD / 12.0
        cagr = (1 + tot) ** (1 / yrs) - 1
        shp = (comb.mean() / comb.std(ddof=1) * np.sqrt(12 / HOLD)
               if comb.std(ddof=1) > 0 else float("nan"))
        peak = np.maximum.accumulate(eqc)
        mdd = float((eqc / peak - 1).min())
        b = spy[rb[-1]] / spy[rb[0]] - 1
        print(f"  {w:<16s} {100*tot:>+8.0f}% {100*cagr:>+8.1f}% "
              f"{shp:>8.2f} {100*mdd:>7.1f}%   {100*(tot-b):>+7.0f}%")
        out[f"NEUTRAL|{w}"] = {"total": tot, "cagr": float(cagr),
                               "sharpe": float(shp), "maxdd": mdd,
                               "vs_spy": float(tot - b)}

    (OUT / "final.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nsaved: experiments/final.json")


if __name__ == "__main__":
    main()
