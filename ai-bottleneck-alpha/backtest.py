"""
Cross-sectional long/short backtest on the bottleneck universe.

THE CONTROL THAT MATTERS
------------------------
The AI bottleneck universe returned roughly +200% equal-weighted while SPY did
about +90%. So ANY strategy that holds these names beats the market, and
"outperformed SPY" measures the universe definition, not the signal. Every
result below is therefore reported against TWO benchmarks:

    SPY            did we beat the market?          (the task's question)
    EW universe    did the SIGNAL add anything?     (the honest question)

A strategy that beats SPY but loses to its own equal-weighted universe has
discovered nothing except that AI infrastructure went up, and would be more
cheaply expressed by buying all 61 names and going away.

WHAT THE EDA ESTABLISHED
------------------------
Two signal families survived a five-year stability screen, and both showed the
same structure: LEVELS do not predict, CHANGES do.

    gross margin LEVEL    IC -0.010      gross margin CHANGE   IC +0.102
    backlog LEVEL         IC +0.026      backlog GROWTH        IC +0.109

Signals carried forward are the ones positive in all five calendar years:
eps_yoy, om_delta, backlog_yoy (fundamental); dist_200dma, mom_12m,
mom_over_vol (technical). rev_accel is dropped despite being the task's
"earnings momentum" candidate -- IC +0.009, t=0.4, indistinguishable from noise.

SELECTION-BIAS NOTE
-------------------
Eighteen signals were screened at three horizons. Picking the best of 54 tests
and reporting its t-statistic overstates significance. The guards are: a
stability filter (every year, not on average), an out-of-sample split, and an
equal-weight combination rather than fitted weights -- no coefficient in this
strategy was optimized on returns.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_panel import FEATURES
from eda_signals import technicals

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"

FUND = ["eps_yoy", "om_delta", "backlog_yoy"]
TECH = ["dist_200dma", "mom_12m", "mom_over_vol"]

COST_BPS = 10.0          # round-trip slippage+commission on each side traded
STUDY_START = "2022-01-01"
OOS_START = "2025-01-01"


def zscore(v):
    """Cross-sectional z-score, winsorized. NaN stays NaN."""
    ok = np.isfinite(v)
    if ok.sum() < 8:
        return np.full_like(v, np.nan)
    x = v.copy()
    lo, hi = np.nanpercentile(x[ok], [5, 95])
    x = np.clip(x, lo, hi)
    mu, sd = np.nanmean(x[ok]), np.nanstd(x[ok])
    out = np.full_like(v, np.nan)
    if sd > 0:
        out[ok] = (x[ok] - mu) / sd
    return out


def composite(sigs, i, names, min_signals=2):
    """
    Average the available z-scores. A name scores only if at least
    `min_signals` of its inputs are present, so a company with one lucky
    non-NaN field cannot outrank a fully-covered one on thin evidence.
    """
    zs = [zscore(sigs[k][i]) for k in names]
    stack = np.vstack(zs)
    cnt = np.isfinite(stack).sum(axis=0)
    with np.errstate(invalid="ignore"):
        avg = np.nanmean(stack, axis=0)
    avg[cnt < min_signals] = np.nan
    return avg


def run(adj, sigs, reb, names, n_long=10, n_short=10, hold=1,
        long_only=False, min_signals=2, cost_bps=COST_BPS):
    """
    Equal-weight top/bottom N, rebalanced every `hold` months.
    Returns the equity path and per-pick outcomes.
    """
    n, m = adj.shape
    eq, dates_i = [1.0], [reb[0]]
    picks, prev_long, prev_short = [], set(), set()

    for s in range(0, len(reb) - hold, hold):
        i, k = reb[s], reb[s + hold]
        sc = composite(sigs, i, names, min_signals)
        tradeable = np.isfinite(sc) & np.isfinite(adj[i]) & np.isfinite(adj[k])
        sc = np.where(tradeable, sc, np.nan)
        if np.isfinite(sc).sum() < n_long + n_short:
            continue
        order = np.argsort(-np.nan_to_num(sc, nan=-1e9))
        valid = [j for j in order if np.isfinite(sc[j])]
        L = valid[:n_long]
        S = [] if long_only else valid[-n_short:]

        r = adj[k] / adj[i] - 1.0
        rl = float(np.mean(r[L]))
        rs = float(np.mean(r[S])) if S else 0.0
        gross = rl if long_only else 0.5 * (rl - rs)

        turn = len(set(L) ^ prev_long) + len(set(S) ^ prev_short)
        cost = (cost_bps / 1e4) * turn / max(len(L) + len(S), 1)
        eq.append(eq[-1] * (1 + gross - cost))
        dates_i.append(k)
        prev_long, prev_short = set(L), set(S)

        for j in L:
            picks.append({"i": i, "k": k, "j": int(j), "side": 1, "ret": float(r[j])})
        for j in S:
            picks.append({"i": i, "k": k, "j": int(j), "side": -1, "ret": float(r[j])})

    return np.array(eq), dates_i, picks


def stats(eq, dates_i, picks, adj, spy, ew, dates, label):
    if len(eq) < 3:
        return None
    yrs = (len(eq) - 1) / 12.0
    cagr = eq[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    per = eq[1:] / eq[:-1] - 1
    sharpe = per.mean() / per.std(ddof=1) * np.sqrt(12) if per.std(ddof=1) > 0 else np.nan
    peak = np.maximum.accumulate(eq)
    mdd = float((eq / peak - 1).min())

    # Benchmarks over the identical dates.
    b_spy = spy[dates_i[-1]] / spy[dates_i[0]] - 1
    b_ew = ew[dates_i[-1]] / ew[dates_i[0]] - 1

    # Hit rate: a LONG pick "wins" if it beat the equal-weight universe over the
    # same holding period -- beating a rising tide is the relevant test, not
    # merely being positive.
    wins, tot, prof, loss = 0, 0, 0.0, 0.0
    for p in picks:
        bench = ew[p["k"]] / ew[p["i"]] - 1.0
        excess = p["side"] * (p["ret"] - bench)
        tot += 1
        if excess > 0:
            wins += 1
            prof += excess
        else:
            loss -= excess
    hit = 100 * wins / max(tot, 1)
    pf = prof / loss if loss > 0 else np.nan

    print(f"  {label:<30s} {100*(eq[-1]-1):>+8.0f}% {100*cagr:>+7.1f}% "
          f"{sharpe:>6.2f} {100*mdd:>7.1f}% {hit:>7.1f}% {pf:>6.2f} "
          f"{100*(eq[-1]-1-b_spy):>+8.0f}% {100*(eq[-1]-1-b_ew):>+8.0f}%")
    return {"total": float(eq[-1] - 1), "cagr": float(cagr), "sharpe": float(sharpe),
            "maxdd": mdd, "hit_rate": hit, "profit_factor": None if np.isnan(pf) else float(pf),
            "vs_spy": float(eq[-1] - 1 - b_spy), "vs_ew": float(eq[-1] - 1 - b_ew),
            "n_picks": tot, "months": len(eq) - 1}


HDR = (f"  {'strategy':<30s} {'total':>9s} {'CAGR':>8s} {'Shrp':>6s} "
       f"{'maxDD':>8s} {'hit%':>8s} {'PF':>6s} {'vs SPY':>9s} {'vs EW':>9s}")


def main():
    z = np.load(ROOT / "data" / "panel.npz", allow_pickle=True)
    dates = [str(x) for x in z["dates"]]
    syms = [str(x) for x in z["symbols"]]
    adj = z["adjclose"]
    n, m = adj.shape

    sigs = {f: z[f"feat_{f}"] for f in FEATURES}
    sigs.update(technicals(adj))

    # Equal-weight universe index, rebalanced daily on available names --
    # the honest benchmark for a stock-picking signal.
    rets = np.full((n, m), np.nan)
    rets[1:] = adj[1:] / adj[:-1] - 1.0
    ew = np.ones(n)
    for i in range(1, n):
        r = rets[i][np.isfinite(rets[i])]
        ew[i] = ew[i - 1] * (1 + (r.mean() if len(r) else 0.0))
    spy = z["bench_SPY"]
    spy = np.where(np.isfinite(spy), spy, np.nan)

    reb_all = [i for i in range(1, n)
               if dates[i][:7] != dates[i - 1][:7] and dates[i] >= STUDY_START]
    oos_i = min(i for i in reb_all if dates[i] >= OOS_START)

    windows = {
        "FULL 2022-2026": reb_all,
        "IS   2022-2024": [i for i in reb_all if dates[i] < OOS_START],
        "OOS  2025-2026": [i for i in reb_all if dates[i] >= OOS_START],
    }
    combos = {
        "fundamental only": FUND,
        "technical only": TECH,
        "fundamental + technical": FUND + TECH,
    }

    allres = {}
    for wname, reb in windows.items():
        if len(reb) < 6:
            continue
        b_spy = spy[reb[-1]] / spy[reb[0]] - 1
        b_ew = ew[reb[-1]] / ew[reb[0]] - 1
        print("\n" + "=" * 118)
        print(f"{wname}   ({len(reb)} months)   SPY {100*b_spy:+.0f}%   "
              f"equal-weight universe {100*b_ew:+.0f}%")
        print("=" * 118)
        print(HDR)
        print("  " + "-" * 114)
        for cname, names in combos.items():
            for mode, lo in (("long-short", False), ("long-only", True)):
                eq, di, pk = run(adj, sigs, reb, names, long_only=lo)
                r = stats(eq, di, pk, adj, spy, ew, dates, f"{cname} / {mode}")
                if r:
                    allres[f"{wname}|{cname}|{mode}"] = r

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "backtest_base.json").write_text(json.dumps(allres, indent=2))
    print("\nsaved: experiments/backtest_base.json")
    print("\n  hit% = share of picks beating the EQUAL-WEIGHT UNIVERSE over the "
          "holding period\n  PF   = gross excess-vs-universe gains / losses")


if __name__ == "__main__":
    main()
