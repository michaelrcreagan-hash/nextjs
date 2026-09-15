"""
Stage 3 -- the prop sweep, on the gates that survived stage 2.

Stage 2 established which rules have an edge. This stage asks the different
question the prop account actually poses: starting on an arbitrary day with a
fixed, non-resetting loss budget, what is P(reach the target before breaching)?

That is not the same as maximizing expectancy, and the distinction drives every
result in this project. The drawdown floor is STATIC and never resets, so the
account is a finite resource. Under a fixed loss budget the reward-to-risk
ratio that maximizes expectancy is not the one that maximizes survival: a 2R
target wins more per trade but loses more often, and every loss permanently
consumes budget you can never earn back. Smaller, likelier targets win.

TWO DEFECTS IN THE FIRST VERSION OF THIS FILE, BOTH FIXED HERE
--------------------------------------------------------------
1. THE SPLIT WAS FAKE. simulate() runs from start_bar to the end of whatever
   panel it is handed, so varying only the start does not confine a run to the
   in-sample region -- an "IS" run beginning at bar 1300 traded straight through
   the out-of-sample data it was later judged on. Each window now gets a
   genuinely truncated panel, so an IS run cannot see an OOS bar.

2. RANKING ON BREACH RATE SELECTED FOR DOING NOTHING. Breach-first ranking
   handed the shortlist to the smallest risk setting on the board, which never
   breaches for the same reason it never passes: 80-100% of its runs ended
   unresolved. A configuration that cannot reach the target is not safe, it is
   useless, and scoring it as a zero-breach success is how a sweep talks itself
   into a strategy that does not trade.

   Both are now handled by a HARD HORIZON. Every run gets 1,080 bars (six
   months) and no more, so the three outcomes -- pass, breach, ran out of time
   -- are mutually exclusive and exhaustive, and "unresolved" is a failure with
   its own column rather than a hiding place. Ranking is on the bootstrap lower
   bound of the pass rate, among configurations whose breach rate clears a hard
   ceiling. That ordering says what the account economics say: breaching is
   worse than failing, but failing to fire is not a win.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.engine import (ALTS, BARS_PER_MONTH, BTC, PROFILES, indicators, load,
                        load_with_btc_context, make_signal, simulate)

OUT = Path(__file__).resolve().parent / "experiments"
SPLIT = 0.60
HORIZON = 1080           # 6 months of 4H bars -- the eval deadline
MAX_BREACH = 10.0        # a config breaching more than this is not considered


def sub(d, ind, sig, lo, hi):
    """Truncated panel [lo, hi). Nothing after `hi` is visible to the run."""
    sd = {k: v for k, v in d.items() if not isinstance(v, np.ndarray)}
    sd["symbols"] = d["symbols"]
    for k, v in d.items():
        if isinstance(v, np.ndarray) and v.shape[0] == d["close"].shape[0]:
            sd[k] = np.ascontiguousarray(v[lo:hi])
    si = {k: np.ascontiguousarray(v[lo:hi]) for k, v in ind.items()
          if isinstance(v, np.ndarray)}
    return sd, si, np.ascontiguousarray(sig[lo:hi])


def eval_window(d, ind, sig, profile, lo, hi, n_starts=30, **kw):
    """
    Starts are spread over [lo, hi - HORIZON]; each run sees only its own
    HORIZON bars. Every run therefore resolves as pass, breach, or timeout
    within a fixed, identical budget of time.
    """
    last = hi - HORIZON
    if last <= lo:
        return None
    starts = np.unique(np.linspace(lo, last, n_starts).astype(int))
    res = []
    for b in starts:
        sd, si, ss = sub(d, ind, sig, int(b), int(b) + HORIZON)
        res.append(simulate(sd, si, ss, profile, start_bar=0, **kw))
    oc = [r["outcome"] for r in res]
    tr = [t for r in res for t in r["trades"]]
    pnl = np.array([t["pnl"] for t in tr]) if tr else np.array([0.0])
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    pb = [r["bars"] for r in res if r["outcome"] == "PASS"]
    rng = np.random.default_rng(11)
    p = np.array([o == "PASS" for o in oc], dtype=float)
    boot = np.array([rng.choice(p, len(p), replace=True).mean() for _ in range(2000)])
    br = 100 * (oc.count("breach_dd") + oc.count("breach_daily")) / len(res)
    return {
        "n_starts": len(res),
        "pass": round(100 * oc.count("PASS") / len(res), 1),
        "pass_lo": round(100 * float(np.percentile(boot, 10)), 1),
        "breach": round(br, 1),
        "timeout": round(100 * oc.count("open") / len(res), 1),
        "win": round(100 * float((pnl > 0).mean()), 1) if tr else 0.0,
        "pf": round(float(gw / gl), 2) if gl > 0 else None,
        "t_mo": round(len(tr) / len(res) /
                      max(float(np.mean([r["bars"] for r in res])) / BARS_PER_MONTH, 1e-9), 1),
        "mo_to_pass": round(float(np.median(pb)) / BARS_PER_MONTH, 1) if pb else None,
    }


RISK = [0.25, 0.5, 0.75, 1.0, 1.5]
STOP = [1.25, 1.5, 2.0]
RR = [1.0, 1.25, 1.5, 2.0]
DAILY = [1.0, 1.5]


def rank(r):
    """Lower is better. Breach ceiling first, then the pass lower bound."""
    return (0 if r["breach"] <= MAX_BREACH else 1, -r["pass_lo"], -r["pass"], r["breach"])


def sweep(cohort, d, ind, direction, gate_kw, gate_lab, profile_name,
          max_concurrent, top=6):
    prof = PROFILES[profile_name]
    n = d["close"].shape[0]
    cut = int(n * SPLIT)
    sig = make_signal(d, ind, direction, **gate_kw)

    cand = []
    for r in RISK:
        for s in STOP:
            for rr in RR:
                for dl in DAILY:
                    kw = dict(risk_pct=r, atr_stop=s, rr=rr,
                              max_concurrent=max_concurrent,
                              internal_daily_pct=dl)
                    a = eval_window(d, ind, sig, prof, 1300, cut, 30, **kw)
                    if a:
                        cand.append((kw, a))

    cand.sort(key=lambda x: rank(x[1]))
    short = cand[:top]

    print(f"\n  {cohort} / {profile_name} / gate: {gate_lab}")
    print(f"    {'risk':>5s} {'stop':>5s} {'rr':>5s} {'dly':>4s} | "
          f"{'IS pass':>8s} {'lo':>6s} {'brch':>6s} {'t/o':>6s} | "
          f"{'OOS pass':>9s} {'lo':>6s} {'brch':>6s} {'t/o':>6s} "
          f"{'win%':>6s} {'PF':>6s} {'t/mo':>5s} {'mo2p':>5s}")
    print("    " + "-" * 122)

    rows = []
    for kw, a in short:
        b = eval_window(d, ind, sig, prof, cut, n, 30, **kw)
        if not b:
            continue
        rows.append({"params": kw, "is": a, "oos": b})
        print(f"    {kw['risk_pct']:>5.2f} {kw['atr_stop']:>5.2f} {kw['rr']:>5.2f} "
              f"{kw['internal_daily_pct']:>4.1f} | {a['pass']:>7.1f}% {a['pass_lo']:>5.1f}% "
              f"{a['breach']:>5.1f}% {a['timeout']:>5.1f}% | "
              f"{b['pass']:>8.1f}% {b['pass_lo']:>5.1f}% {b['breach']:>5.1f}% "
              f"{b['timeout']:>5.1f}% {b['win']:>5.1f}% "
              f"{(b['pf'] or 0):>6.2f} {b['t_mo']:>5.1f} "
              f"{(b['mo_to_pass'] if b['mo_to_pass'] else 0):>5.1f}")

    rows.sort(key=lambda r: rank(r["oos"]))
    return rows


def main():
    carry = json.loads((OUT / "stage2_robust.json").read_text())["carry"]

    btc = load(BTC); btc_ind = indicators(btc)
    alt = load_with_btc_context(ALTS); alt_ind = indicators(alt)
    panels = {"btc_long": (btc, btc_ind, +1, 1),
              "btc_short": (btc, btc_ind, -1, 1),
              "alt_long": (alt, alt_ind, +1, 3),
              "alt_short": (alt, alt_ind, -1, 3)}

    print("=" * 130)
    print(f"STAGE 3 -- PROP SWEEP   horizon {HORIZON} bars (6 months), "
          f"disjoint IS/OOS panels, breach ceiling {MAX_BREACH}%")
    print("=" * 130)

    out = {}
    for cohort, gates in carry.items():
        d, ind, direction, mc = panels[cohort]
        out[cohort] = {}
        for gate_lab, meta in gates.items():
            kwg = {k: (tuple(v) if isinstance(v, list) else v)
                   for k, v in meta["gates"].items()}
            out[cohort][gate_lab] = {}
            for pname in ("classic_10k", "turbo_200k"):
                out[cohort][gate_lab][pname] = sweep(
                    cohort, d, ind, direction, kwg, gate_lab, pname, mc)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage3_prop.json").write_text(json.dumps(out, indent=2))

    print("\n" + "=" * 130)
    print("  BEST BY COHORT AND PROFILE (breach ceiling, then OOS pass lower bound)")
    print("=" * 130)
    best = {}
    for cohort, gates in out.items():
        for pname in ("classic_10k", "turbo_200k"):
            pool = [(g, r) for g, ps in gates.items() for r in ps[pname]]
            if not pool:
                continue
            pool.sort(key=lambda x: rank(x[1]["oos"]))
            g, r = pool[0]
            best[f"{cohort}|{pname}"] = {"gate": g, **r}
            p, o = r["params"], r["oos"]
            print(f"  {cohort:<11s} {pname:<12s} {g:<34s} "
                  f"risk {p['risk_pct']} stop {p['atr_stop']} rr {p['rr']} "
                  f"dly {p['internal_daily_pct']} -> OOS pass {o['pass']}% "
                  f"[lo {o['pass_lo']}%] breach {o['breach']}% t/o {o['timeout']}% "
                  f"PF {o['pf']} t/mo {o['t_mo']}")
    (OUT / "stage3_best.json").write_text(json.dumps(best, indent=2))
    print("\nsaved: experiments/stage3_prop.json, experiments/stage3_best.json")


if __name__ == "__main__":
    main()
