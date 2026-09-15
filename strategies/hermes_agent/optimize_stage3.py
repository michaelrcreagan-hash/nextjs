"""
Stage 3 -- combine the plateau, then try hard to break it.

Stage 2 produced two configurations at 100% pass across 60 start windows
(risk 0.75%, and stop 1.5 ATR). A 100% result on overlapping windows is a
claim to be attacked, not a finding to be reported. This stage does the
attacking, in five ways:

  1. COMBINE   -- do the two winners stack, or was each borrowing the other's
                  effect?
  2. OOS SPLIT -- fit on the first 60% of the panel, verify on the last 40%.
                  The panel is 2023-08 -> 2026-08, so the holdout is a
                  genuinely different market.
  3. TURBO     -- rerun on the $200k / 3% floor profile. Half the drawdown
                  buffer of Classic; if a config only survives on Classic, say
                  so rather than implying it generalizes.
  4. COSTS     -- 3x the fee and slippage assumption. A result that evaporates
                  under realistic execution was never real.
  5. START GRID-- re-evaluate at 120 and 240 start dates. If the pass rate
                  moves materially with the number of (overlapping) windows,
                  the 60-window estimate was an artifact of the spacing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import src.h4_engine as eng
from optimize_prop import HDR, PROFILES, WARMUP, evaluate, fmt_row
from src.h4_engine import build_indicators, load, signals, simulate

OUT = Path(__file__).resolve().parent / "experiments" / "h4_prop"

# The Stage-2 plateau, combined.
CHAMPION = dict(risk_pct=0.75, atr_stop=1.5, rr=2.0, max_concurrent=3,
                internal_daily_pct=1.0, trail_after_r=None)
# Highest trade-level win rate variant (the user asked for win rate explicitly).
HIGH_WINRATE = dict(risk_pct=0.75, atr_stop=1.5, rr=1.5, max_concurrent=3,
                    internal_daily_pct=1.0, trail_after_r=None)


def sub_panel(d, lo, hi):
    out = {"ts": d["ts"][lo:hi], "symbols": d["symbols"]}
    for k in ("open", "high", "low", "close", "volume"):
        out[k] = np.ascontiguousarray(d[k][lo:hi])
    return out


def main():
    d = load()
    ind = build_indicators(d)
    sig = signals(d, ind, engine="keltner", allow_short=True)
    n = d["close"].shape[0]
    res = {}

    print("=" * 118)
    print("STAGE 3 -- combine the plateau, then attack it")
    print("=" * 118)

    # ---- 1. combine ----
    print("\n" + "-" * 118)
    print("  3a. do the two Stage-2 winners stack?  (Classic $10k)")
    print("-" * 118)
    print(HDR)
    print("-" * 118)
    combos = [
        ("baseline risk0.5 stop2.0", dict(risk_pct=0.5, atr_stop=2.0)),
        ("risk 0.75 only", dict(risk_pct=0.75, atr_stop=2.0)),
        ("stop 1.5 only", dict(risk_pct=0.5, atr_stop=1.5)),
        ("CHAMPION risk0.75 + stop1.5", CHAMPION),
        ("HIGH-WINRATE (RR 1.5)", HIGH_WINRATE),
    ]
    a = {}
    for lab, kw in combos:
        r = evaluate(d, ind, sig, PROFILES["classic_10k"], **kw)
        a[lab] = r
        print(fmt_row(lab, r))
    res["3a_combine"] = a

    # ---- 2. OOS split ----
    print("\n" + "-" * 118)
    print("  3b. IN-SAMPLE (first 60%) vs OUT-OF-SAMPLE (last 40%)")
    print("-" * 118)
    print(HDR)
    print("-" * 118)
    cut = int(n * 0.6)
    b = {}
    for name, kw in (("CHAMPION", CHAMPION), ("HIGH-WINRATE", HIGH_WINRATE)):
        for part, (lo, hi) in (("IS", (0, cut)), ("OOS", (cut - WARMUP, n))):
            dd = sub_panel(d, lo, hi)
            ii = build_indicators(dd)
            ss = signals(dd, ii, engine="keltner", allow_short=True)
            r = evaluate(dd, ii, ss, PROFILES["classic_10k"], n_starts=40, **kw)
            b[f"{name} {part}"] = r
            print(fmt_row(f"{name} {part}", r))
    res["3b_oos"] = b

    # ---- 3. Turbo profile ----
    print("\n" + "-" * 118)
    print("  3c. TURBO $200k -- 3% floor, half the buffer of Classic")
    print("-" * 118)
    print(HDR)
    print("-" * 118)
    c = {}
    for lab, kw in (("CHAMPION on Turbo", CHAMPION),
                    ("Turbo @ risk 0.5%", {**CHAMPION, "risk_pct": 0.5}),
                    ("Turbo @ risk 0.35%", {**CHAMPION, "risk_pct": 0.35}),
                    ("Turbo @ risk 0.25%", {**CHAMPION, "risk_pct": 0.25})):
        r = evaluate(d, ind, sig, PROFILES["turbo_200k"], **kw)
        c[lab] = r
        print(fmt_row(lab, r))
    res["3c_turbo"] = c

    # ---- 4. cost stress ----
    print("\n" + "-" * 118)
    print("  3d. COST STRESS -- 1x / 2x / 3x fees+slippage")
    print("-" * 118)
    print(HDR)
    print("-" * 118)
    base_t, base_s = eng.TAKER_PCT, eng.SLIP_BPS
    e = {}
    for mult in (1, 2, 3):
        eng.TAKER_PCT, eng.SLIP_BPS = base_t * mult, base_s * mult
        r = evaluate(d, ind, sig, PROFILES["classic_10k"], **CHAMPION)
        e[f"{mult}x costs"] = r
        print(fmt_row(f"{mult}x costs "
                      f"({eng.TAKER_PCT:.3f}% + {eng.SLIP_BPS:.0f}bps)", r))
    eng.TAKER_PCT, eng.SLIP_BPS = base_t, base_s
    res["3d_costs"] = e

    # ---- 5. start-date density ----
    print("\n" + "-" * 118)
    print("  3e. START-DATE DENSITY -- does the estimate move with window count?")
    print("-" * 118)
    print(HDR)
    print("-" * 118)
    f = {}
    for ns in (30, 60, 120, 240):
        r = evaluate(d, ind, sig, PROFILES["classic_10k"], n_starts=ns, **CHAMPION)
        f[f"{ns} starts"] = r
        print(fmt_row(f"{ns} start dates", r))
    res["3e_density"] = f

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage3.json").write_text(json.dumps(
        {"champion": CHAMPION, "high_winrate": HIGH_WINRATE, "results": res},
        indent=2))
    print("\nsaved: experiments/h4_prop/stage3.json")


if __name__ == "__main__":
    main()
