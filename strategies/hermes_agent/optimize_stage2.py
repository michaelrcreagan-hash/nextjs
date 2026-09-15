"""
Stage 2 -- parameter sweep on the Stage-1 winner (Keltner L/S).

Stage 1 established the engine. This finds the parameter plateau, per the
report's instruction to "choose parameter plateaus, not peaks": a config that
is best by a hair while its neighbours are poor is a fitting artifact, and on
60 OVERLAPPING start windows it is very easy to manufacture one.

Two things Stage 1 flagged that this sweep has to attack:
  - median 9.1 MONTHS to pass, with 18.3% of runs never resolving. The rule is
    too slow. Raising frequency without adding breaches is the main lever.
  - Stage-1 breach rate was 0.0%, meaning the risk envelope has slack in it.
    Slack is only useful if it buys frequency.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_prop import HDR, PROFILES, evaluate, fmt_row
from src.h4_engine import build_indicators, load, signals

OUT = Path(__file__).resolve().parent / "experiments" / "h4_prop"


def main():
    d = load()
    ind = build_indicators(d)
    base_sig = signals(d, ind, engine="keltner", allow_short=True)
    prof = PROFILES["classic_10k"]
    all_res = {}

    def block(title, variants, sig_fn=None):
        print("\n" + "-" * 118)
        print(f"  {title}")
        print("-" * 118)
        print(HDR)
        print("-" * 118)
        out = {}
        for lab, kw in variants:
            s = sig_fn(kw) if sig_fn else base_sig
            sim_kw = {k: v for k, v in kw.items() if k not in SIGNAL_KEYS}
            r = evaluate(d, ind, s, prof, **sim_kw)
            out[lab] = r
            print(fmt_row(lab, r))
        all_res[title] = out
        return out

    global SIGNAL_KEYS
    SIGNAL_KEYS = {"er_min", "adx_min", "require_adx_rising", "require_macd",
                   "require_ema_stack", "allow_short", "engine"}

    def make_sig(kw):
        sk = {k: v for k, v in kw.items() if k in SIGNAL_KEYS}
        return signals(d, ind, engine="keltner", allow_short=True, **sk)

    print("=" * 118)
    print("STAGE 2 -- parameter plateau on Keltner L/S  (Classic $10k)")
    print("=" * 118)

    # --- 2a. risk per trade -----------------------------------------------
    block("2a. risk per trade (the variable that dominated every earlier test)",
          [(f"risk {r}%", dict(risk_pct=r)) for r in (0.25, 0.5, 0.75, 1.0, 1.25)])

    # --- 2b. reward:risk ---------------------------------------------------
    block("2b. reward:risk target",
          [(f"RR {rr}", dict(rr=rr)) for rr in (1.5, 2.0, 2.5, 3.0, 4.0)])

    # --- 2c. stop width ----------------------------------------------------
    block("2c. ATR stop multiple",
          [(f"stop {s} ATR", dict(atr_stop=s)) for s in (1.5, 2.0, 2.5, 3.0)])

    # --- 2d. concurrency ---------------------------------------------------
    block("2d. max concurrent positions",
          [(f"max {n} concurrent", dict(max_concurrent=n)) for n in (1, 2, 3, 5, 8)])

    # --- 2e. the frequency levers (gate strictness) ------------------------
    block("2e. gate strictness -- the frequency lever",
          [("ER>=0.20 (looser)", dict(er_min=0.20)),
           ("ER>=0.30 (report spec)", dict(er_min=0.30)),
           ("ER>=0.40 (stricter)", dict(er_min=0.40)),
           ("ADX>=20 (looser)", dict(adx_min=20.0)),
           ("ADX>=25 (report spec)", dict(adx_min=25.0)),
           ("ADX>=30 (stricter)", dict(adx_min=30.0)),
           ("no ADX-rising req", dict(require_adx_rising=False)),
           ("no MACD req", dict(require_macd=False)),
           ("no EMA200 stack req", dict(require_ema_stack=False)),
           ("all filters off", dict(er_min=0.0, adx_min=0.0,
                                    require_adx_rising=False,
                                    require_macd=False,
                                    require_ema_stack=False))],
          sig_fn=make_sig)

    # --- 2f. internal daily stop ------------------------------------------
    block("2f. internal daily stop (firm's hard limit is 3%)",
          [(f"internal {p}%", dict(internal_daily_pct=p))
           for p in (0.75, 1.0, 1.5, 2.0, 3.0)])

    # --- 2g. breakeven trail ----------------------------------------------
    block("2g. move stop to breakeven after +XR",
          [("no trail", dict(trail_after_r=None)),
           ("BE at +0.5R", dict(trail_after_r=0.5)),
           ("BE at +1.0R", dict(trail_after_r=1.0)),
           ("BE at +1.5R", dict(trail_after_r=1.5))])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage2.json").write_text(json.dumps(all_res, indent=2))
    print(f"\nsaved: experiments/h4_prop/stage2.json")

    # Flatten and show the plateau
    flat = [(blk, lab, r) for blk, o in all_res.items() for lab, r in o.items()]
    flat.sort(key=lambda x: -x[2]["pass_lo"])
    print("\n" + "=" * 118)
    print("  TOP 10 BY CI LOWER BOUND (ranking on the point estimate selects noise)")
    print("=" * 118)
    print(HDR)
    for blk, lab, r in flat[:10]:
        print(fmt_row(lab, r))


if __name__ == "__main__":
    main()
