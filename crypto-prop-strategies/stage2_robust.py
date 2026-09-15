"""
Stage 2 -- is the stage 1 edge real, or is it 26 lucky trades?

Stage 1 handed back four positive cohorts, but BTC's best gate posted PF 4.51
on 26 trades in three years. That is roughly nine trades a year. A profit
factor computed on 26 samples has an enormous confidence interval, and picking
the best of eight gates and then quoting its point estimate is textbook
selection bias -- the number reported is the maximum of eight noisy draws, not
an estimate of the underlying edge.

Two tests, both of which the point estimate cannot survive on its own:

  1. TRADE-LEVEL BOOTSTRAP. Resample the realized R multiples with replacement
     and report the 10th percentile of average R. If the lower bound is at or
     below zero the edge is not distinguishable from noise at this sample size,
     whatever the point estimate says.

  2. IS/OOS SPLIT. First 60% of the panel to choose, last 40% to check. This is
     the discipline that caught a 100%-pass configuration in the prior repo
     that turned out to breach on 20% of out-of-sample starts.

A gate is carried forward only if the bootstrap lower bound on average R is
positive AND out-of-sample expectancy is positive. Ranking is by lower bound,
never by point estimate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.engine import (ALTS, BARS_PER_MONTH, BTC, indicators, load,
                        load_with_btc_context, make_signal, simulate)
from stage1_edge import RAW, kw_repr

OUT = Path(__file__).resolve().parent / "experiments"
SPLIT = 0.60


def trades_between(d, ind, sig, lo, hi, max_concurrent):
    """Raw trades opened inside [lo, hi). Costs and fills as in the prop run."""
    sub = {k: (v[lo:hi] if isinstance(v, np.ndarray) and v.ndim and v.shape[0] == d["close"].shape[0] else v)
           for k, v in d.items()}
    sub["symbols"] = d["symbols"]
    si = {k: v[lo:hi] for k, v in ind.items() if isinstance(v, np.ndarray)}
    r = simulate(sub, si, sig[lo:hi], RAW, risk_pct=0.5, atr_stop=1.5, rr=1.25,
                 max_concurrent=max_concurrent, start_bar=0,
                 internal_daily_pct=1e9)
    return r["trades"], r["bars"]


def stats(tr, bars, rng):
    if len(tr) < 5:
        return None
    rs = np.array([t["r"] for t in tr])
    pnl = np.array([t["pnl"] for t in tr])
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    boot = np.array([rng.choice(rs, len(rs), replace=True).mean()
                     for _ in range(4000)])
    return {"n": len(tr),
            "win": round(100 * float((pnl > 0).mean()), 1),
            "pf": round(float(gw / gl), 3) if gl > 0 else None,
            "avg_r": round(float(rs.mean()), 3),
            "r_lo": round(float(np.percentile(boot, 10)), 3),
            "r_hi": round(float(np.percentile(boot, 90)), 3),
            "t_mo": round(len(tr) / max(bars / BARS_PER_MONTH, 1e-9), 1)}


GATES = [
    ("ema200 + expansion", dict(require_ema200=True, regimes=(2,))),
    ("ema200 + expansion/extreme", dict(require_ema200=True, regimes=(2, 3))),
    ("ema200 + normal/expansion", dict(require_ema200=True, regimes=(1, 2))),
    ("ema200 + any regime", dict(require_ema200=True, regimes=(0, 1, 2, 3))),
    ("no ema200 + expansion", dict(require_ema200=False, regimes=(2,))),
    ("no ema200 + normal/expansion", dict(require_ema200=False, regimes=(1, 2))),
    ("no ema200 + any regime", dict(require_ema200=False, regimes=(0, 1, 2, 3))),
    ("ema200 + expansion, adx flat ok",
     dict(require_ema200=True, regimes=(2,), require_adx_rising=False)),
    ("ema200 + norm/exp, adx flat ok",
     dict(require_ema200=True, regimes=(1, 2), require_adx_rising=False)),
]
ALT_EXTRA = [
    ("ema200 + expansion + BTC agrees",
     dict(require_ema200=True, regimes=(2,), btc_filter=True)),
    ("ema200 + norm/exp + BTC agrees",
     dict(require_ema200=True, regimes=(1, 2), btc_filter=True)),
    ("ema200 + norm/exp + RS>0",
     dict(require_ema200=True, regimes=(1, 2), rs_min=0.0)),
]

HDR = (f"  {'gates':<36s} | {'n':>4s} {'avgR':>6s} {'[10-90]':>15s} {'PF':>6s} "
       f"| {'n':>4s} {'avgR':>6s} {'PF':>6s} {'win%':>6s} | verdict")


def cohort(name, d, ind, direction, max_concurrent):
    n = d["close"].shape[0]
    cut = int(n * SPLIT)
    rng = np.random.default_rng(7)
    gates = GATES + (ALT_EXTRA if "btc_prev" in ind else [])

    print("\n" + "=" * 118)
    print(f"  {name} {'LONG' if direction == 1 else 'SHORT'}"
          f"     IS bars 1300-{cut}   OOS bars {cut}-{n}")
    print("=" * 118)
    print(HDR.replace("| ", "|IS ", 1).replace("| ", "|OOS ", 1))
    print("-" * 118)

    rows = {}
    for lab, kw in gates:
        sig = make_signal(d, ind, direction, **kw)
        tr_is, b_is = trades_between(d, ind, sig, 1300, cut, max_concurrent)
        tr_oos, b_oos = trades_between(d, ind, sig, cut, n, max_concurrent)
        s_is, s_oos = stats(tr_is, b_is, rng), stats(tr_oos, b_oos, rng)
        if s_is is None or s_oos is None:
            print(f"  {lab:<36s} | too few trades")
            continue
        ok = s_is["r_lo"] > 0 and s_oos["avg_r"] > 0
        rows[lab] = {"is": s_is, "oos": s_oos, "carry": ok, "gates": kw_repr(kw)}
        print(f"  {lab:<36s} | {s_is['n']:>4d} {s_is['avg_r']:>6.3f} "
              f"[{s_is['r_lo']:>6.3f},{s_is['r_hi']:>6.3f}] "
              f"{(s_is['pf'] or 0):>6.2f} | {s_oos['n']:>4d} {s_oos['avg_r']:>6.3f} "
              f"{(s_oos['pf'] or 0):>6.2f} {s_oos['win']:>5.1f}% | "
              f"{'CARRY' if ok else 'drop'}")
    return rows


def main():
    print("=" * 118)
    print("STAGE 2 -- SIGNIFICANCE AND OUT-OF-SAMPLE SURVIVAL")
    print("  carry rule: IS bootstrap 10th-pct avg R > 0  AND  OOS avg R > 0")
    print("=" * 118)

    btc = load(BTC); btc_ind = indicators(btc)
    alt = load_with_btc_context(ALTS); alt_ind = indicators(alt)

    out = {
        "btc_long": cohort("BTC", btc, btc_ind, +1, 1),
        "btc_short": cohort("BTC", btc, btc_ind, -1, 1),
        "alt_long": cohort("ALTS", alt, alt_ind, +1, 3),
        "alt_short": cohort("ALTS", alt, alt_ind, -1, 3),
    }

    print("\n" + "=" * 118)
    print("  CARRIED FORWARD TO THE PROP SWEEP (ranked by IS lower bound)")
    print("=" * 118)
    carry = {}
    for c, rows in out.items():
        ok = {k: v for k, v in rows.items() if v["carry"]}
        ranked = sorted(ok, key=lambda k: -ok[k]["is"]["r_lo"])[:3]
        carry[c] = {k: ok[k] for k in ranked}
        if not ranked:
            print(f"  {c:<11s} NOTHING SURVIVES -- no tradeable edge in this cohort")
        for i, k in enumerate(ranked):
            v = ok[k]
            print(f"  {c if i == 0 else '':<11s} {i+1}. {k:<36s} "
                  f"IS lo {v['is']['r_lo']:>6.3f}  OOS avgR {v['oos']['avg_r']:>6.3f} "
                  f"(n={v['oos']['n']})")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage2_robust.json").write_text(json.dumps(
        {"split": SPLIT, "all": out, "carry": carry}, indent=2))
    print("\nsaved: experiments/stage2_robust.json")


if __name__ == "__main__":
    main()
