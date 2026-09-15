"""
Which signals actually picked the winners early?

The task says to use the 2022-2026 top performers to determine the optimal
signals. Done literally that is circular: pick the winners, notice the winners
had high growth, then "discover" that high growth predicts winning. The result
is a backtest that cannot lose and a strategy that cannot work.

So the winners are used here only to frame the question, and the ANSWER comes
from a cross-sectional test that the winners cannot rig:

    At each month end, rank every name on a signal using only data filed by
    that date. Does that ranking predict the NEXT period's returns?

That is the information coefficient -- the rank correlation between the signal
today and the return afterwards, averaged over ~55 monthly cross-sections. A
signal that merely describes the winners scores zero here, because it is being
asked to sort names before the returns happen, over and over, in every regime
along the way.

Three things are reported for each signal, and the third matters most:
  IC        mean rank correlation with forward return
  t-stat    whether that mean is distinguishable from zero
  IC by year  whether it worked every year, or only in 2023

A signal with a good average and one dominant year is a signal that worked
once. The 2022-2026 window contains a bear market, a mania and a correction,
and a factor that only survives one of those is not a factor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_panel import FEATURES

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"
STUDY_START = "2022-01-01"


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 8:
        return np.nan
    x, y = a[ok], b[ok]
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    den = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return float((rx * ry).sum() / den) if den > 0 else np.nan


def technicals(adj):
    """Price-based signals, all strictly backward-looking."""
    n, m = adj.shape
    out = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        def ret(k):
            r = np.full((n, m), np.nan)
            r[k:] = adj[k:] / adj[:-k] - 1.0
            return r
        out["mom_12m"] = ret(252)
        out["mom_6m"] = ret(126)
        out["mom_3m"] = ret(63)
        out["mom_1m"] = ret(21)
        # 12-1 momentum: the classic, skipping the mean-reverting last month.
        r12, r1 = ret(252), ret(21)
        out["mom_12_1"] = (1 + r12) / (1 + r1) - 1

        sma200 = np.full((n, m), np.nan)
        c = np.cumsum(np.nan_to_num(adj), axis=0)
        cnt = np.cumsum(np.isfinite(adj), axis=0)
        for t in range(200, n):
            s = c[t] - c[t - 200]
            k = cnt[t] - cnt[t - 200]
            sma200[t] = np.where(k >= 150, s / np.maximum(k, 1), np.nan)
        out["dist_200dma"] = adj / sma200 - 1.0

        lr = np.full((n, m), np.nan)
        lr[1:] = np.log(adj[1:] / adj[:-1])
        vol = np.full((n, m), np.nan)
        for t in range(63, n):
            w = lr[t - 63:t]
            vol[t] = np.nanstd(w, axis=0) * np.sqrt(252)
        out["vol_3m"] = vol
        out["mom_over_vol"] = out["mom_6m"] / np.maximum(vol, 1e-6)
    return out


def main():
    z = np.load(ROOT / "data" / "panel.npz", allow_pickle=True)
    dates = [str(x) for x in z["dates"]]
    syms = [str(x) for x in z["symbols"]]
    adj = z["adjclose"]
    spy = z["bench_SPY"]
    n, m = adj.shape

    sig = {f: z[f"feat_{f}"] for f in FEATURES}
    sig.update(technicals(adj))

    # ---------------------------------------------------------- winners --
    i0 = min(i for i, dd in enumerate(dates) if dd >= STUDY_START)
    tot = np.full(m, np.nan)
    for j in range(m):
        col = adj[i0:, j]
        ok = np.where(np.isfinite(col))[0]
        if len(ok) > 200:
            tot[j] = col[ok[-1]] / col[ok[0]] - 1.0
    bench = spy[np.isfinite(spy)][-1] / spy[i0] - 1.0

    order = np.argsort(-np.nan_to_num(tot, nan=-9))
    print("=" * 100)
    print(f"REALISED RETURNS {STUDY_START} -> {dates[-1]}   (SPY {100*bench:+.0f}%)")
    print("=" * 100)
    print("  top 12                              bottom 12")
    for r in range(12):
        a, b = order[r], order[-(r + 1)]
        print(f"  {r+1:>2d}. {syms[a]:<6s} {100*tot[a]:>+8.0f}%"
              f"          {syms[b]:<6s} {100*tot[b]:>+8.0f}%")
    print("\n  NOTE: this table frames the question. It is NOT used to fit "
          "anything --\n  every number below comes from ranking names BEFORE "
          "the returns happened.")

    # ------------------------------------------------- monthly IC study --
    # Month-end rebalance dates.
    reb = [i for i in range(1, n)
           if dates[i][:7] != dates[i - 1][:7] and dates[i] >= STUDY_START]
    horizons = {"1m": 21, "3m": 63, "6m": 126}

    results = {}
    print("\n" + "=" * 100)
    print("INFORMATION COEFFICIENT -- rank the cross-section, then wait")
    print("=" * 100)
    print(f"  {len(reb)} monthly cross-sections, {m} names\n")
    print(f"  {'signal':<16s} " + "".join(f"{h:>20s}" for h in horizons))
    print(f"  {'':<16s} " + "".join(f"{'IC    t   n':>20s}" for _ in horizons))
    print("  " + "-" * 76)

    for name, S in sig.items():
        row, rec = "", {}
        for h, k in horizons.items():
            ics = []
            for i in reb:
                if i + k >= n:
                    continue
                fwd = adj[i + k] / adj[i] - 1.0
                ic = spearman(S[i], fwd)
                if np.isfinite(ic):
                    ics.append(ic)
            if len(ics) < 8:
                row += f"{'-':>20s}"
                continue
            a = np.array(ics)
            t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
            rec[h] = {"ic": round(float(a.mean()), 4), "t": round(float(t), 2),
                      "n": len(a)}
            row += f"{a.mean():>+8.3f}{t:>6.1f}{len(a):>6d}"
        results[name] = rec
        print(f"  {name:<16s} {row}")

    # ------------------------------------------------------ IC by year --
    print("\n" + "=" * 100)
    print("IC BY YEAR (3-month horizon) -- did it work every year, or once?")
    print("=" * 100)
    years = sorted({dates[i][:4] for i in reb})
    print(f"  {'signal':<16s}" + "".join(f"{y:>9s}" for y in years) + "     verdict")
    print("  " + "-" * 78)
    stab = {}
    for name, S in sig.items():
        per, cells = {}, ""
        for y in years:
            ics = []
            for i in reb:
                if dates[i][:4] != y or i + 63 >= n:
                    continue
                ic = spearman(S[i], adj[i + 63] / adj[i] - 1.0)
                if np.isfinite(ic):
                    ics.append(ic)
            v = float(np.mean(ics)) if len(ics) >= 3 else np.nan
            per[y] = None if np.isnan(v) else round(v, 3)
            cells += f"{v:>+9.2f}" if np.isfinite(v) else f"{'-':>9s}"
        vals = [v for v in per.values() if v is not None]
        pos = sum(1 for v in vals if v > 0)
        verdict = (f"{pos}/{len(vals)} yrs positive" if vals else "-")
        stab[name] = {"by_year": per, "years_positive": pos, "years": len(vals)}
        print(f"  {name:<16s}{cells}     {verdict}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "eda_signals.json").write_text(json.dumps(
        {"study_start": STUDY_START, "spy_return": float(bench),
         "realised": {syms[j]: (None if np.isnan(tot[j]) else round(float(tot[j]), 4))
                      for j in range(m)},
         "ic": results, "stability": stab}, indent=2))
    print("\nsaved: experiments/eda_signals.json")


if __name__ == "__main__":
    main()
