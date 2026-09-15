"""
Stage 3b -- reselect the gates on R per MONTH, not R per trade.

Stage 3 exposed a selection error made back in stage 2. Gates were carried
forward on the bootstrap lower bound of average R *per trade*, which rewards
rarity: the strictest gate posts the best number per trade precisely because it
only fires on the clearest setups. That is the right criterion for an unlevered
book with no deadline. It is the wrong one here.

A prop evaluation is a race. The account has to cover a fixed percentage target
before a fixed loss budget runs out, and -- as stage 3 measured -- it also has
to do it before the operator gives up waiting. At 1.3 trades a month a
six-month run gets about eight trades, and eight trades at 0.75% risk cannot
add up to 10% however good each one is. Stage 3's headline failures were not
strategies losing money; 83-97% of them simply never finished. Expectancy per
unit of TIME is what the eval pays for:

    R per month  =  avg R per trade  x  trades per month

So this stage reranks every gate that survived stage 2 on out-of-sample R per
month and sweeps the winners. The looser gates that stage 2's ranking discarded
-- "any regime", "no ema200" -- get their proper hearing here, and the question
becomes whether their thinner per-trade edge survives being traded often enough
to matter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.engine import (ALTS, BTC, indicators, load, load_with_btc_context)
from stage3_prop import OUT, rank, sweep

TOP_GATES = 3


def main():
    st2 = json.loads((OUT / "stage2_robust.json").read_text())["all"]

    btc = load(BTC); btc_ind = indicators(btc)
    alt = load_with_btc_context(ALTS); alt_ind = indicators(alt)
    panels = {"btc_long": (btc, btc_ind, +1, 1),
              "btc_short": (btc, btc_ind, -1, 1),
              "alt_long": (alt, alt_ind, +1, 3),
              "alt_short": (alt, alt_ind, -1, 3)}

    print("=" * 130)
    print("STAGE 3b -- GATES RESELECTED ON OUT-OF-SAMPLE R PER MONTH")
    print("=" * 130)

    picks = {}
    for cohort, rows in st2.items():
        scored = []
        for lab, v in rows.items():
            if not v["carry"]:
                continue
            rmo_oos = v["oos"]["avg_r"] * v["oos"]["t_mo"]
            rmo_is = v["is"]["r_lo"] * v["is"]["t_mo"]
            scored.append((lab, round(rmo_oos, 2), round(rmo_is, 2), v))
        # Require the in-sample lower bound to be positive per month too, so a
        # gate cannot be selected purely on an out-of-sample run of luck.
        scored = [s for s in scored if s[2] > 0]
        scored.sort(key=lambda s: -min(s[1], s[2]))
        picks[cohort] = scored[:TOP_GATES]
        print(f"\n  {cohort}")
        for lab, ro, ri, v in scored:
            mark = "  <-- swept" if (lab, ro, ri, v) in picks[cohort] else ""
            print(f"    {lab:<36s} OOS R/mo {ro:>6.2f}  IS lo R/mo {ri:>6.2f}  "
                  f"(t/mo {v['oos']['t_mo']:>5.1f}, avgR {v['oos']['avg_r']:>6.3f}){mark}")

    out = {}
    for cohort, sel in picks.items():
        d, ind, direction, mc = panels[cohort]
        out[cohort] = {}
        for lab, _, _, v in sel:
            kwg = {k: (tuple(x) if isinstance(x, list) else x)
                   for k, x in v["gates"].items()}
            out[cohort][lab] = {}
            for pname in ("classic_10k", "turbo_200k"):
                out[cohort][lab][pname] = sweep(
                    cohort, d, ind, direction, kwg, lab, pname, mc)

    (OUT / "stage3b_freq.json").write_text(json.dumps(out, indent=2))

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
                  f"PF {o['pf']} t/mo {o['t_mo']} mo2pass {o['mo_to_pass']}")
    (OUT / "stage3b_best.json").write_text(json.dumps(best, indent=2))
    print("\nsaved: experiments/stage3b_freq.json, experiments/stage3b_best.json")


if __name__ == "__main__":
    main()
