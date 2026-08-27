"""
Stage 1 -- raw directional edge, before any prop-account rules.

The order matters. A prop simulation mixes two very different things: whether
the underlying rule makes money, and whether the account survives its drawdown
budget long enough to collect. If you sweep them together you cannot tell a
losing rule with lucky risk settings from a winning rule with unlucky ones. The
futures work in the prior repo made exactly that mistake worth avoiding: every
arm failed, and only the profit factor (0.52-0.91 across the board) revealed
that the drawdown rule was irrelevant because expectancy was negative either
way.

So stage 1 asks one question per cohort per direction:

    does this rule have positive expectancy at all?

Anything with PF <= 1.0 is dead and no risk setting will revive it. Only
survivors go to stage 2 for the prop sweep.

Implementation note: the raw run reuses simulate() with the target and the
drawdown floor set so far away that neither can bind, which keeps the fill
logic, the cost model and the stop-before-target tiebreak identical to the
prop run rather than reimplementing them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.engine import (ALTS, BARS_PER_MONTH, BTC, indicators, load,
                        load_with_btc_context, make_signal, simulate,
                        vol_regime)

OUT = Path(__file__).resolve().parent / "experiments"

RAW = dict(account=100_000.0, target_usd=1e15, max_dd_usd=1e15,
           daily_loss_pct=1e9)


def raw(d, ind, sig, risk_pct=0.5, atr_stop=1.5, rr=1.25, max_concurrent=3,
        warmup=1300):
    r = simulate(d, ind, sig, RAW, risk_pct=risk_pct, atr_stop=atr_stop, rr=rr,
                 max_concurrent=max_concurrent, start_bar=warmup,
                 internal_daily_pct=1e9)
    tr = r["trades"]
    if not tr:
        return None
    pnl = np.array([t["pnl"] for t in tr])
    rs = np.array([t["r"] for t in tr])
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    bars = r["bars"]
    return {"n": len(tr),
            "win": round(100 * float((pnl > 0).mean()), 1),
            "pf": round(float(gw / gl), 3) if gl > 0 else None,
            "avg_r": round(float(rs.mean()), 3),
            "exp_r_mo": round(float(rs.sum()) / (bars / BARS_PER_MONTH), 2),
            "t_mo": round(len(tr) / (bars / BARS_PER_MONTH), 1)}


def survey(name, d, ind, direction, max_concurrent):
    print("\n" + "=" * 104)
    print(f"  {name}   direction={'LONG' if direction == 1 else 'SHORT'}")
    print("=" * 104)
    print(f"  {'gates':<46s} {'sig%':>6s} {'n':>5s} {'win%':>6s} {'PF':>7s} "
          f"{'avgR':>7s} {'R/mo':>7s} {'t/mo':>6s}")
    print("-" * 104)

    rows = {}
    # Gate combinations. The prior repo established that er_min and adx_min do
    # essentially no work on their own (0.20/0.30/0.40 gave identical results),
    # so the interesting axes are the structural ones: whether the 200 EMA
    # stack is required, which volatility regimes are eligible, and -- for
    # alts -- whether BTC's own trend has to agree.
    gates = [
        ("ema200 + expansion", dict(require_ema200=True, regimes=(2,))),
        ("ema200 + expansion/extreme", dict(require_ema200=True, regimes=(2, 3))),
        ("ema200 + normal/expansion", dict(require_ema200=True, regimes=(1, 2))),
        ("ema200 + any regime", dict(require_ema200=True, regimes=(0, 1, 2, 3))),
        ("no ema200 + expansion", dict(require_ema200=False, regimes=(2,))),
        ("no ema200 + normal/expansion", dict(require_ema200=False, regimes=(1, 2))),
        ("no ema200 + any regime", dict(require_ema200=False, regimes=(0, 1, 2, 3))),
        ("ema200 + expansion, adx flat ok",
         dict(require_ema200=True, regimes=(2,), require_adx_rising=False)),
    ]
    if "btc_prev" in ind:
        gates += [
            ("ema200 + expansion + BTC agrees",
             dict(require_ema200=True, regimes=(2,), btc_filter=True)),
            ("ema200 + exp + BTC agrees + RS>0",
             dict(require_ema200=True, regimes=(2,), btc_filter=True, rs_min=0.0)),
            ("ema200 + expansion + RS>0",
             dict(require_ema200=True, regimes=(2,), rs_min=0.0)),
        ]

    for lab, kw in gates:
        sig = make_signal(d, ind, direction, **kw)
        pct = 100 * float((sig != 0).mean())
        r = raw(d, ind, sig, max_concurrent=max_concurrent)
        if r is None:
            print(f"  {lab:<46s} {pct:>5.2f}%     -      -       -       -       -      -")
            continue
        rows[lab] = dict(r, sig_pct=round(pct, 2), gates=kw_repr(kw))
        pf = f"{r['pf']:>7.3f}" if r["pf"] else "      -"
        print(f"  {lab:<46s} {pct:>5.2f}% {r['n']:>5d} {r['win']:>5.1f}% {pf} "
              f"{r['avg_r']:>7.3f} {r['exp_r_mo']:>7.2f} {r['t_mo']:>6.1f}")
    return rows


def kw_repr(kw):
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}


def main():
    print("=" * 104)
    print("STAGE 1 -- RAW DIRECTIONAL EDGE (no prop rules; PF <= 1.0 is fatal)")
    print("=" * 104)

    btc = load(BTC)
    btc_ind = indicators(btc)
    alt = load_with_btc_context(ALTS)
    alt_ind = indicators(alt)

    for lab, dd in (("BTC", btc), ("ALTS", alt)):
        reg = vol_regime(indicators(dd))
        share = [round(100 * float((reg == k).mean()), 1) for k in range(4)]
        print(f"  {lab:<5s} {dd['close'].shape[0]} bars x {len(dd['symbols'])} "
              f"({', '.join(dd['symbols'])})   regime mix "
              f"compress/normal/expand/extreme = {share}")

    out = {}
    out["btc_long"] = survey("BTC", btc, btc_ind, +1, max_concurrent=1)
    out["btc_short"] = survey("BTC", btc, btc_ind, -1, max_concurrent=1)
    out["alt_long"] = survey("ALTS", alt, alt_ind, +1, max_concurrent=3)
    out["alt_short"] = survey("ALTS", alt, alt_ind, -1, max_concurrent=3)

    print("\n" + "=" * 104)
    print("  SURVIVORS (PF > 1.0)")
    print("=" * 104)
    surv = {}
    for cohort, rows in out.items():
        ok = {k: v for k, v in rows.items() if (v["pf"] or 0) > 1.0}
        surv[cohort] = ok
        best = max(ok, key=lambda k: ok[k]["pf"]) if ok else None
        print(f"  {cohort:<12s} {len(ok)}/{len(rows)} gates positive"
              + (f"   best: {best} (PF {ok[best]['pf']})" if best else "   -- NO EDGE"))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage1_edge.json").write_text(json.dumps(
        {"all": out, "survivors": surv}, indent=2))
    print("\nsaved: experiments/stage1_edge.json")


if __name__ == "__main__":
    main()
