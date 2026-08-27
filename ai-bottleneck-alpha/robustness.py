"""
Five ways this result could still be wrong, tested.

The null test established the ranking is not concentration luck. That leaves
the assumptions baked into the setup, and the first one is the most dangerous
thing in the whole study.

A -- UNIVERSE HINDSIGHT. The universe was written in 2026. Calling NVDA, ASML
     or ANET an "AI bottleneck" was possible in January 2022. Calling POWL
     (switchgear), MOD (vehicle thermal management) or VRT's power business an
     AI bottleneck was NOT obvious then -- the electrical-supply constraint only
     became consensus around 2024, and those names returned +1,975%, +1,692%
     and +987%. If the strategy's edge disappears once the universe is
     restricted to what was identifiable in 2022, then the study is a story
     about universe selection wearing a factor model as a disguise.

B -- EXECUTION LAG. Signals are computed from the close and positions are taken
     at that same close. That is standard for monthly rebalancing but it is
     still a same-bar assumption. Re-run trading at the NEXT day's close.

C -- POSITION COUNT. Ten names is a choice. If the result only exists at ten,
     it is a fit.

D -- HOLDING PERIOD. Monthly is a choice, and a costly one at ~50% turnover.

E -- COSTS. 10bps per side is optimistic for names like POWL and CRDO in 2022.
     Test 25 and 50.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import FUND, OOS_START, STUDY_START, TECH, run
from build_panel import FEATURES
from eda_signals import technicals
from src.universe import LAYER_OF

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"

# Layers whose role in an AI buildout was arguable in January 2022. The
# electrical/power thesis was not consensus until roughly 2024.
LATE_THESIS_LAYERS = {"power_electrical", "power_generation", "datacenter_reit"}

SIGNALS = FUND + TECH


def ew_index(adj):
    n, m = adj.shape
    r = np.full((n, m), np.nan)
    r[1:] = adj[1:] / adj[:-1] - 1.0
    ew = np.ones(n)
    for i in range(1, n):
        v = r[i][np.isfinite(r[i])]
        ew[i] = ew[i - 1] * (1 + (v.mean() if len(v) else 0.0))
    return ew


def summary(eq, hold=1):
    """
    `hold` is the number of MONTHS per step. It is required, because each
    element of `eq` is one rebalance period rather than one month -- annualizing
    a 6-month step as if it were monthly produced a 4,449% CAGR in the first run
    of this file, which is how the bug announced itself.
    """
    if len(eq) < 3:
        return None
    steps = len(eq) - 1
    yrs = steps * hold / 12.0
    per = eq[1:] / eq[:-1] - 1
    peak = np.maximum.accumulate(eq)
    ppy = 12.0 / hold                      # periods per year
    return {"total": float(eq[-1] - 1),
            "cagr": float(eq[-1] ** (1 / yrs) - 1) if yrs > 0 else np.nan,
            "sharpe": float(per.mean() / per.std(ddof=1) * np.sqrt(ppy))
            if per.std(ddof=1) > 0 else np.nan,
            "maxdd": float((eq / peak - 1).min()),
            "months": steps * hold}


def main():
    z = np.load(ROOT / "data" / "panel.npz", allow_pickle=True)
    dates = [str(x) for x in z["dates"]]
    syms = [str(x) for x in z["symbols"]]
    adj = z["adjclose"]
    n, m = adj.shape
    sigs = {f: z[f"feat_{f}"] for f in FEATURES}
    sigs.update(technicals(adj))
    reb = [i for i in range(1, n)
           if dates[i][:7] != dates[i - 1][:7] and dates[i] >= STUDY_START]
    reb_oos = [i for i in reb if dates[i] >= OOS_START]
    ew = ew_index(adj)
    out = {}

    def line(lab, eq, ref_reb, hold=1):
        s = summary(eq, hold)
        if not s:
            print(f"  {lab:<42s}  (insufficient)")
            return None
        b = ew[ref_reb[-1]] / ew[ref_reb[0]] - 1
        print(f"  {lab:<42s} {100*s['total']:>+8.0f}% {100*s['cagr']:>+8.1f}% "
              f"{s['sharpe']:>6.2f} {100*s['maxdd']:>7.1f}% "
              f"{100*(s['total']-b):>+9.0f}%")
        return s

    HDR = (f"  {'variant':<42s} {'total':>9s} {'CAGR':>9s} {'Shrp':>6s} "
           f"{'maxDD':>8s} {'vs EW':>10s}")

    # ------------------------------------------------------------------ A --
    print("=" * 96)
    print("A  UNIVERSE HINDSIGHT -- restrict to names identifiable as AI "
          "infrastructure in Jan 2022")
    print("=" * 96)
    early = np.array([LAYER_OF[s] not in LATE_THESIS_LAYERS for s in syms])
    late = ~early
    print(f"  early-thesis names ({early.sum()}): "
          f"{', '.join(np.array(syms)[early][:18])}...")
    print(f"  late-thesis names  ({late.sum()}): "
          f"{', '.join(np.array(syms)[late])}\n")
    print(HDR)
    print("  " + "-" * 92)

    adj_early = adj.copy()
    adj_early[:, late] = np.nan          # remove them from the tradeable set
    ew_e = ew_index(adj_early)

    for lab, a, ref in (("full universe (61)", adj, ew),
                        ("early-thesis only (%d)" % early.sum(), adj_early, ew_e)):
        eq, di, pk = run(a, sigs, reb, SIGNALS, long_only=True)
        s = summary(eq)
        b = ref[reb[-1]] / ref[reb[0]] - 1
        print(f"  {lab:<42s} {100*s['total']:>+8.0f}% {100*s['cagr']:>+8.1f}% "
              f"{s['sharpe']:>6.2f} {100*s['maxdd']:>7.1f}% "
              f"{100*(s['total']-b):>+9.0f}%")
        out[f"A|{lab}"] = dict(s, ew=float(b))
    print(f"\n  the late-thesis layers held the 1st, 3rd and 4th best performers "
          f"(POWL, MOD, VRT).\n  if the edge survives their removal it is not a "
          f"universe-selection artifact.")

    # ------------------------------------------------------------------ B --
    print("\n" + "=" * 96)
    print("B  EXECUTION LAG -- trade at the next close instead of the signal close")
    print("=" * 96)
    print(HDR)
    print("  " + "-" * 92)
    for lag in (0, 1, 2):
        rb = [i + lag for i in reb if i + lag < n]
        # Signals still read at `reb`; only the fills move. Emulated by shifting
        # the price matrix backwards so adj[i] is the price `lag` days later.
        a = np.full_like(adj, np.nan)
        if lag == 0:
            a = adj
        else:
            a[:-lag] = adj[lag:]
        eq, di, pk = run(a, sigs, reb, SIGNALS, long_only=True)
        out[f"B|lag{lag}"] = line(f"fill at close + {lag} day(s)", eq, reb)

    # ------------------------------------------------------------------ C --
    print("\n" + "=" * 96)
    print("C  POSITION COUNT")
    print("=" * 96)
    print(HDR)
    print("  " + "-" * 92)
    for k in (5, 8, 10, 15, 20, 30):
        eq, di, pk = run(adj, sigs, reb, SIGNALS, n_long=k, long_only=True)
        out[f"C|n{k}"] = line(f"top {k} names", eq, reb)

    # ------------------------------------------------------------------ D --
    print("\n" + "=" * 96)
    print("D  HOLDING PERIOD")
    print("=" * 96)
    print(HDR)
    print("  " + "-" * 92)
    for h in (1, 2, 3, 6):
        eq, di, pk = run(adj, sigs, reb, SIGNALS, hold=h, long_only=True)
        out[f"D|hold{h}"] = line(f"rebalance every {h} month(s)", eq, reb, hold=h)

    # ------------------------------------------------------------------ E --
    print("\n" + "=" * 96)
    print("E  TRANSACTION COSTS")
    print("=" * 96)
    print(HDR)
    print("  " + "-" * 92)
    for c in (10, 25, 50, 100):
        eq, di, pk = run(adj, sigs, reb, SIGNALS, long_only=True, cost_bps=c)
        out[f"E|cost{c}"] = line(f"{c} bps per side", eq, reb)

    # ---------------------------------------------------------------- OOS --
    print("\n" + "=" * 96)
    print("OOS 2025-2026 under the same stresses (the honest headline numbers)")
    print("=" * 96)
    print(HDR)
    print("  " + "-" * 92)
    eq, _, _ = run(adj_early, sigs, reb_oos, SIGNALS, long_only=True)
    out["OOS|early-thesis"] = line("early-thesis universe only", eq, reb_oos)
    eq, _, _ = run(adj, sigs, reb_oos, SIGNALS, long_only=True, cost_bps=50)
    out["OOS|cost50"] = line("full universe, 50bps costs", eq, reb_oos)
    a = np.full_like(adj, np.nan); a[:-1] = adj[1:]
    eq, _, _ = run(a, sigs, reb_oos, SIGNALS, long_only=True)
    out["OOS|lag1"] = line("full universe, next-day fills", eq, reb_oos)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "robustness.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nsaved: experiments/robustness.json")


if __name__ == "__main__":
    main()
