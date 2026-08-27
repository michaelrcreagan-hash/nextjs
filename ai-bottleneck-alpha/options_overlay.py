"""
Should the signal be expressed in options instead of shares?

WHAT THIS CAN AND CANNOT ANSWER -- READ FIRST
---------------------------------------------
There is no historical option-quote data available in this environment, so
implied volatility is MODELLED, not observed. That single assumption drives the
entire answer, because an option buyer's profit is roughly the gap between the
volatility they paid and the volatility that arrived.

Modelling it honestly means confronting the variance risk premium: implied
volatility exceeds subsequent realised volatility most of the time, in most
names, as compensation to the seller. Empirically the premium on liquid US
single names runs around 1.0-1.3x realised, and it is WIDEST exactly where this
strategy shops -- high-momentum semiconductor and power names into earnings,
where 3-month implieds of 60-90% were routine over this window.

So instead of picking one number and presenting a result, the IV premium is
swept from 0.9x to 1.5x realised. The output is not "options make X%" -- it is
the break-even premium above which the overlay stops working. That number is
checkable against real quotes, which the reader can do and this study cannot.

STRUCTURES TESTED
-----------------
  stock          the baseline, 1x notional
  ATM call       maximum delta per premium dollar, most exposed to IV
  10% OTM call   cheaper, needs a bigger move, more convex
  call spread    long ATM / short 20% OTM -- caps the tail but pays much less
                 volatility premium, which is the point

All are held to expiry at the rebalance horizon, so no early-exercise or
path-dependent management is modelled. Position sizing spends a fixed
percentage of capital on premium, so a total loss on one expiry is bounded.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import FUND, OOS_START, STUDY_START, TECH, composite
from build_panel import FEATURES
from eda_signals import technicals
from robustness import ew_index

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments"

SIGNALS = ["eps_yoy", "om_delta", "mom_12m"]     # a robust mid-list config
N_LONG, HOLD = 5, 2
RF = 0.045
PREMIUM_BUDGET = 0.20        # 20% of capital into premium, 80% held in cash


def ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(S, K, T, sigma, r=RF):
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)


def realised_vol(adj, i, lookback=63):
    lo = max(1, i - lookback)
    lr = np.log(adj[lo:i + 1, :] / adj[lo - 1:i, :])
    with np.errstate(invalid="ignore"):
        return np.nanstd(lr, axis=0) * math.sqrt(252)


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

    windows = {"FULL 2022-2026": reb,
               "IS   2022-2024": [i for i in reb if dates[i] < OOS_START],
               "OOS  2025-2026": [i for i in reb if dates[i] >= OOS_START]}

    print("=" * 116)
    print(f"OPTIONS OVERLAY -- signal {'+'.join(SIGNALS)}, top {N_LONG}, "
          f"{HOLD}-month expiry, {int(100*PREMIUM_BUDGET)}% of capital in premium")
    print("  implied vol is MODELLED as a multiple of trailing realised vol; "
          "that multiple is swept")
    print("=" * 116)

    results = {}
    for wname, rb in windows.items():
        if len(rb) < HOLD + 2:
            continue
        print(f"\n{wname}")
        print(f"  {'structure':<26s} {'IVx':>5s} {'total':>9s} {'CAGR':>9s} "
              f"{'hit%':>7s} {'PF':>7s} {'maxDD':>8s}   note")
        print("  " + "-" * 108)

        # Stock baseline, same picks.
        eq_s, picks_s = [1.0], []
        for s in range(0, len(rb) - HOLD, HOLD):
            i, k = rb[s], rb[s + HOLD]
            sc = composite(sigs, i, SIGNALS)
            ok = np.isfinite(sc) & np.isfinite(adj[i]) & np.isfinite(adj[k])
            sc = np.where(ok, sc, np.nan)
            v = [j for j in np.argsort(-np.nan_to_num(sc, nan=-1e9))
                 if np.isfinite(sc[j])][:N_LONG]
            if len(v) < N_LONG:
                continue
            r = float(np.mean(adj[k][v] / adj[i][v] - 1.0))
            eq_s.append(eq_s[-1] * (1 + r))
            b = ew[k] / ew[i] - 1.0
            picks_s += [float(adj[k][j] / adj[i][j] - 1.0 - b) for j in v]
        report("stock (baseline)", None, eq_s, picks_s, HOLD, "")
        results[f"{wname}|stock"] = pack(eq_s, picks_s, HOLD)

        for structure in ("ATM call", "10% OTM call", "ATM/+20% call spread"):
            for ivx in (0.9, 1.0, 1.15, 1.3, 1.5):
                eq, picks = [1.0], []
                for s in range(0, len(rb) - HOLD, HOLD):
                    i, k = rb[s], rb[s + HOLD]
                    sc = composite(sigs, i, SIGNALS)
                    ok = np.isfinite(sc) & np.isfinite(adj[i]) & np.isfinite(adj[k])
                    sc = np.where(ok, sc, np.nan)
                    v = [j for j in np.argsort(-np.nan_to_num(sc, nan=-1e9))
                         if np.isfinite(sc[j])][:N_LONG]
                    if len(v) < N_LONG:
                        continue
                    rv = realised_vol(adj, i)
                    T = (k - i) / 252.0
                    rets = []
                    for j in v:
                        S0, S1 = adj[i, j], adj[k, j]
                        sig = rv[j]
                        if not np.isfinite(sig) or sig <= 0:
                            continue
                        iv = sig * ivx
                        if structure == "ATM call":
                            K = S0
                            prem = bs_call(S0, K, T, iv)
                            pay = max(0.0, S1 - K)
                        elif structure == "10% OTM call":
                            K = S0 * 1.10
                            prem = bs_call(S0, K, T, iv)
                            pay = max(0.0, S1 - K)
                        else:
                            K1, K2 = S0, S0 * 1.20
                            prem = bs_call(S0, K1, T, iv) - bs_call(S0, K2, T, iv)
                            pay = max(0.0, S1 - K1) - max(0.0, S1 - K2)
                        if prem <= 0:
                            continue
                        rets.append(pay / prem - 1.0)
                    if not rets:
                        continue
                    # Fixed premium budget; the rest sits in cash earning RF.
                    port = (PREMIUM_BUDGET * (1 + float(np.mean(rets)))
                            + (1 - PREMIUM_BUDGET) * (1 + RF * T))
                    eq.append(eq[-1] * port)
                    picks += rets
                note = ""
                if ivx == 1.15:
                    note = "<- typical single-name premium"
                report(structure, ivx, eq, picks, HOLD, note)
                results[f"{wname}|{structure}|{ivx}"] = pack(eq, picks, HOLD)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "options_overlay.json").write_text(json.dumps(results, indent=2,
                                                        default=float))
    print("\n" + "=" * 116)
    print("  READ THE IVx COLUMN, NOT THE HEADLINE. The overlay's viability is "
          "entirely a\n  function of what you actually pay for volatility. "
          "Compare the break-even\n  multiple below against real quoted "
          "implieds before acting on any of it.")
    print("\nsaved: experiments/options_overlay.json")


def pack(eq, picks, hold):
    eq = np.array(eq)
    if len(eq) < 3:
        return None
    yrs = (len(eq) - 1) * hold / 12.0
    p = np.array(picks) if picks else np.array([0.0])
    win, loss = p[p > 0].sum(), -p[p <= 0].sum()
    peak = np.maximum.accumulate(eq)
    return {"total": float(eq[-1] - 1),
            "cagr": float(eq[-1] ** (1 / yrs) - 1) if yrs > 0 else None,
            "hit": float(100 * (p > 0).mean()),
            "pf": float(win / loss) if loss > 0 else None,
            "maxdd": float((eq / peak - 1).min())}


def report(label, ivx, eq, picks, hold, note):
    d = pack(eq, picks, hold)
    if not d:
        print(f"  {label:<26s} {'-':>5s}   (insufficient)")
        return
    iv = f"{ivx:>5.2f}" if ivx else f"{'-':>5s}"
    print(f"  {label:<26s} {iv} {100*d['total']:>+8.0f}% "
          f"{100*(d['cagr'] or 0):>+8.1f}% {d['hit']:>6.1f}% "
          f"{(d['pf'] or 0):>7.2f} {100*d['maxdd']:>7.1f}%   {note}")


if __name__ == "__main__":
    main()
