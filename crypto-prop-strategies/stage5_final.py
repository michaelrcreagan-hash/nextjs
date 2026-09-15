"""
Stage 5 -- final selection on the WORST of both regimes.

Stage 4 answered the two questions it was built to answer.

  1. The short book did not flip when the split was reversed. Selected on the
     bear window and judged on the bull one it still passed 80% with no
     breaches. That is a real result, with one caveat that has to travel with
     it: six of the eight assets fell in BOTH windows, so "bull" describes BTC
     and XRP, not the alt basket. The short edge has never been tested in a
     genuine altcoin bull market, because this panel does not contain one.

  2. Running both directions together fixed BTC. Alone, BTC long fired 0.7-2.2
     trades a month and timed out on 83-97% of evaluations -- not a losing
     strategy, an idle one. Combined with its short engine it fires 3.5-5.0 a
     month and passes. The constraint on BTC was never edge quality, it was
     trade supply, and a second engine is what supplies it.

WHAT THIS STAGE DOES DIFFERENTLY
--------------------------------
Every earlier stage picked parameters on one window and reported them on
another, which answers "does this generalize" but still leaves the final
choice fitted to whichever window did the picking. Stage 4 made that concrete:
the best ALT configuration selected on the bull window (stop 1.25, RR 2.0) is
not the one selected on the bear window (stop 2.0, RR 1.25). Reporting either
one alone would be reporting a regime.

So the final configuration is chosen by MINIMAX: score every configuration in
both windows independently and rank on the WORSE of the two. A configuration
wins here only by being acceptable in a bull tape and a bear tape alike, and
the number quoted for it is the weaker of its two results, never the better.
This gives up peak performance on purpose -- the minimax winner will lose to
the regime-fitted winner inside that regime, every time. What it buys is the
only property that matters when the drawdown floor never resets: the account
is still alive when the regime turns.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.engine import (ALTS, BTC, PROFILES, indicators, load,
                        load_with_btc_context, make_signal)
from stage3_prop import HORIZON, OUT, eval_window
from stage4_regime import GATE, SPLIT

RISK = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
STOP = [1.25, 1.5, 2.0]
RR = [1.0, 1.25, 1.5, 2.0]
DAILY = [1.0, 1.5]

BREACH_CEIL = 15.0      # worst-window breach a fundable config may show


def build(name):
    if name == "BTC":
        d = load(BTC); mc = 1
        lk, sk = GATE["btc_long"], GATE["btc_short"]
    else:
        d = load_with_btc_context(ALTS); mc = 3
        lk, sk = GATE["alt_long"], GATE["alt_short"]
    ind = indicators(d)
    sl = make_signal(d, ind, +1, **lk[1])
    ss = make_signal(d, ind, -1, **sk[1])
    assert int(((sl != 0) & (ss != 0)).sum()) == 0, "long/short overlap"
    return d, ind, mc, {"long": sl, "short": ss,
                        "combined": (sl + ss).astype(np.int8)}, (lk[0], sk[0])


def main():
    print("=" * 132)
    print("STAGE 5 -- FINAL SELECTION BY MINIMAX ACROSS BOTH REGIMES")
    print("  Each configuration is scored in the bull window and the bear window "
          "separately.")
    print("  It is ranked on the WORSE of the two, and the worse of the two is "
          "what gets reported.")
    print("=" * 132)

    results, best = {}, {}
    for book in ("BTC", "ALT"):
        d, ind, mc, sigs, gates = build(book)
        n = d["close"].shape[0]
        cut = int(n * SPLIT)
        WIN = {"bull": (1300, cut), "bear": (cut, n)}
        print(f"\n  {book}: long gate = {gates[0]}   short gate = {gates[1]}")

        for side in ("combined", "long", "short"):
            sig = sigs[side]
            for pname in ("classic_10k", "turbo_200k"):
                prof = PROFILES[pname]
                rows = []
                for r in RISK:
                    for s in STOP:
                        for rr in RR:
                            for dl in DAILY:
                                kw = dict(risk_pct=r, atr_stop=s, rr=rr,
                                          max_concurrent=mc, internal_daily_pct=dl)
                                w = {k: eval_window(d, ind, sig, prof, *v, 30, **kw)
                                     for k, v in WIN.items()}
                                if any(x is None for x in w.values()):
                                    continue
                                worst_pass = min(w[k]["pass_lo"] for k in w)
                                worst_breach = max(w[k]["breach"] for k in w)
                                rows.append({"params": kw, "win": w,
                                             "worst_pass_lo": worst_pass,
                                             "worst_breach": worst_breach})
                rows.sort(key=lambda x: (0 if x["worst_breach"] <= BREACH_CEIL else 1,
                                         -x["worst_pass_lo"], x["worst_breach"]))
                results[f"{book}|{side}|{pname}"] = rows[:8]
                best[f"{book}|{side}|{pname}"] = rows[0] if rows else None

                print(f"\n    {book} {side.upper():<9s} {pname}")
                print(f"      {'risk':>5s} {'stop':>5s} {'rr':>5s} {'dly':>4s} | "
                      f"{'BULL pass':>10s} {'lo':>5s} {'brch':>5s} {'PF':>5s} | "
                      f"{'BEAR pass':>10s} {'lo':>5s} {'brch':>5s} {'PF':>5s} | "
                      f"{'WORST lo':>9s} {'wBrch':>6s} {'t/mo':>5s}")
                print("      " + "-" * 118)
                for x in rows[:5]:
                    p, bu, be = x["params"], x["win"]["bull"], x["win"]["bear"]
                    print(f"      {p['risk_pct']:>5.2f} {p['atr_stop']:>5.2f} "
                          f"{p['rr']:>5.2f} {p['internal_daily_pct']:>4.1f} | "
                          f"{bu['pass']:>9.1f}% {bu['pass_lo']:>4.1f}% {bu['breach']:>4.1f}% "
                          f"{(bu['pf'] or 0):>5.2f} | "
                          f"{be['pass']:>9.1f}% {be['pass_lo']:>4.1f}% {be['breach']:>4.1f}% "
                          f"{(be['pf'] or 0):>5.2f} | {x['worst_pass_lo']:>8.1f}% "
                          f"{x['worst_breach']:>5.1f}% "
                          f"{min(bu['t_mo'], be['t_mo']):>5.1f}")

    print("\n" + "=" * 132)
    print("  FINAL CONFIGURATIONS (worst-regime numbers; E[payouts] = p/(1-p) "
          "at the worst-regime pass rate)")
    print("=" * 132)
    for k, x in best.items():
        if not x:
            continue
        p = x["params"]
        wp = min(x["win"][w]["pass"] for w in ("bull", "bear")) / 100.0
        ep = round(wp / (1 - wp), 1) if wp < 1 else "inf"
        ok = x["worst_breach"] <= BREACH_CEIL and x["worst_pass_lo"] > 0
        print(f"  {k:<28s} risk {p['risk_pct']:<5} stop {p['atr_stop']:<5} "
              f"rr {p['rr']:<5} dly {p['internal_daily_pct']:<4} | "
              f"worst pass {100*wp:>5.1f}% (lo {x['worst_pass_lo']:>5.1f}%) "
              f"breach {x['worst_breach']:>5.1f}% | E[payouts] {str(ep):>5s} | "
              f"{'FUNDABLE' if ok else 'not fundable'}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage5_final.json").write_text(json.dumps(
        {"top": results, "best": best, "breach_ceiling": BREACH_CEIL,
         "horizon_bars": HORIZON}, indent=2, default=float))
    print("\nsaved: experiments/stage5_final.json")


if __name__ == "__main__":
    main()
