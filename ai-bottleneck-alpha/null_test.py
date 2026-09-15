"""
Is the signal real, or is it just "own ten of these and hold on"?

The long-only book returned +1,942% while the equal-weight universe returned
+403%, which looks decisive until you notice what the strategy actually does:
it concentrates 61 names down to 10, inside a universe where the top name did
+1,975% and the median did far less. Concentration alone raises both the mean
and the variance of the outcome. A portfolio of ten names drawn at RANDOM from
this universe would also beat the equal-weight index a large fraction of the
time, purely because the return distribution is so skewed.

So the benchmark is not the index. It is the distribution of what random
selection would have produced under the identical rules -- same universe, same
rebalance dates, same position count, same costs, same tradeability mask. If
the strategy's result sits comfortably inside that distribution, the ranking
adds nothing and the honest description of the book is "ten AI names, equally
weighted."

This is the test that separates a stock-picking signal from a beta story, and
it is reported as a percentile: the share of 2,000 random books the strategy
beat. Anything under ~95 is not evidence of skill.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import (COST_BPS, FUND, OOS_START, STUDY_START, TECH, composite,
                      run)
from build_panel import FEATURES
from eda_signals import technicals

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"
N_TRIALS = 2000


def random_book(adj, reb, rng, n_long=10, hold=1, cost_bps=COST_BPS,
                mask=None):
    """Same mechanics as the strategy, but the ranking is replaced by a coin."""
    eq = 1.0
    prev = set()
    picks = []
    for s in range(0, len(reb) - hold, hold):
        i, k = reb[s], reb[s + hold]
        ok = np.isfinite(adj[i]) & np.isfinite(adj[k])
        if mask is not None:
            ok &= mask[i]
        idx = np.where(ok)[0]
        if len(idx) < n_long:
            continue
        L = rng.choice(idx, n_long, replace=False)
        r = adj[k] / adj[i] - 1.0
        turn = len(set(L.tolist()) ^ prev)
        cost = (cost_bps / 1e4) * turn / n_long
        eq *= (1 + float(np.mean(r[L])) - cost)
        prev = set(L.tolist())
        picks.append((i, k, L))
    return eq - 1.0, picks


def main():
    z = np.load(ROOT / "data" / "panel.npz", allow_pickle=True)
    dates = [str(x) for x in z["dates"]]
    syms = [str(x) for x in z["symbols"]]
    adj = z["adjclose"]
    n, m = adj.shape

    sigs = {f: z[f"feat_{f}"] for f in FEATURES}
    sigs.update(technicals(adj))

    # Equal-weight universe, and a buy-and-hold EW as a cross-check on it.
    rets = np.full((n, m), np.nan)
    rets[1:] = adj[1:] / adj[:-1] - 1.0
    ew = np.ones(n)
    for i in range(1, n):
        r = rets[i][np.isfinite(rets[i])]
        ew[i] = ew[i - 1] * (1 + (r.mean() if len(r) else 0.0))

    reb_all = [i for i in range(1, n)
               if dates[i][:7] != dates[i - 1][:7] and dates[i] >= STUDY_START]

    windows = {"FULL 2022-2026": reb_all,
               "IS   2022-2024": [i for i in reb_all if dates[i] < OOS_START],
               "OOS  2025-2026": [i for i in reb_all if dates[i] >= OOS_START]}

    combos = {"fundamental only": FUND, "technical only": TECH,
              "fundamental + technical": FUND + TECH}

    # A random book may pick any name with a price. The strategy may only pick
    # names it can SCORE, which is a smaller set -- scored names skew toward
    # larger, better-covered filers. To keep the comparison fair the null is
    # also run restricted to the scoreable set, which is the stricter test.
    print("=" * 112)
    print(f"RANDOM-BOOK NULL -- {N_TRIALS} trials, 10 names, same rules and costs")
    print("=" * 112)

    out = {}
    for wname, reb in windows.items():
        if len(reb) < 6:
            continue
        b_ew = ew[reb[-1]] / ew[reb[0]] - 1
        print(f"\n{wname}   equal-weight universe {100*b_ew:+.0f}%")
        print(f"  {'strategy':<26s} {'return':>9s} | {'random p5':>10s} "
              f"{'median':>9s} {'p95':>9s} {'p99':>9s} | {'pctile':>7s}  verdict")
        print("  " + "-" * 104)

        for cname, names in combos.items():
            eq, di, pk = run(adj, sigs, reb, names, long_only=True)
            strat = float(eq[-1] - 1)

            # Scoreable mask: names the composite can actually rank that month.
            mask = np.zeros((n, m), dtype=bool)
            for i in reb:
                mask[i] = np.isfinite(composite(sigs, i, names))

            rng = np.random.default_rng(20260827)
            sims = np.array([random_book(adj, reb, rng, mask=mask)[0]
                             for _ in range(N_TRIALS)])
            pct = 100.0 * float((sims < strat).mean())
            q = np.percentile(sims, [5, 50, 95, 99])
            verdict = ("SKILL" if pct >= 95 else
                       "weak" if pct >= 80 else "INDISTINGUISHABLE FROM RANDOM")
            print(f"  {cname:<26s} {100*strat:>+8.0f}% | {100*q[0]:>+9.0f}% "
                  f"{100*q[1]:>+8.0f}% {100*q[2]:>+8.0f}% {100*q[3]:>+8.0f}% | "
                  f"{pct:>6.1f}%  {verdict}")
            out[f"{wname}|{cname}"] = {
                "strategy": strat, "percentile": pct,
                "random_p5": float(q[0]), "random_median": float(q[1]),
                "random_p95": float(q[2]), "random_p99": float(q[3]),
                "ew_universe": float(b_ew)}

    # How often does a RANDOM 10-name book beat the equal-weight index? If that
    # number is high, "beat the index" was never evidence of anything.
    print("\n" + "-" * 112)
    for wname, reb in windows.items():
        if len(reb) < 6:
            continue
        b_ew = ew[reb[-1]] / ew[reb[0]] - 1
        rng = np.random.default_rng(7)
        sims = np.array([random_book(adj, reb, rng)[0] for _ in range(N_TRIALS)])
        print(f"  {wname}: a RANDOM 10-name book beat the equal-weight universe "
              f"{100*(sims > b_ew).mean():.0f}% of the time")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "null_test.json").write_text(json.dumps(out, indent=2))
    print("\nsaved: experiments/null_test.json")


if __name__ == "__main__":
    main()
