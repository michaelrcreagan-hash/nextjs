"""
Stage 4 -- reverse the split, then run both directions as one book.

WHY THIS STAGE EXISTS
---------------------
Stage 3b concluded that shorts pass and longs do not. Checking the panel's
dates shows why that conclusion could not be trusted as stated:

    IS  2024-04-01 -> 2025-06-15   BTC +51.1%,  XRP +254%
    OOS 2025-06-15 -> 2026-08-27   BTC -23.5%,  every alt negative,
                                   AVAX -60%, DOGE -49%, LTC -41%

The out-of-sample window is a bear market. A short book passing 70% of
evaluations there and a long book failing is close to a tautology, and it says
nothing about whether either rule generalizes. Worse, the long strategies were
SELECTED in a bull window and JUDGED in a bear one, which is the least
favourable arrangement possible -- their failure is partly an artifact of the
split's orientation, not evidence about the rules.

TEST 1 -- REVERSE THE SPLIT. Select on the bear window, judge on the bull
window. If longs now pass and shorts now fail, then neither direction is
"better": each works in its own regime, and any single-direction result from
one split orientation is a measurement of the test period. If shorts pass in
BOTH orientations, shorting really is the more robust edge in this asset class.

TEST 2 -- RUN THEM TOGETHER. The two engines are mutually exclusive by
construction: a long needs EMA21 > EMA50 and a short needs EMA21 < EMA50, so no
symbol can signal both ways on the same bar. That makes a combined book a
legitimate strategy rather than a blend of overlapping bets -- the market
decides which engine is live, so the account does not need a regime forecast.
If the combined book passes in both windows where each single direction passes
in only one, then the deliverable is the pair, not the better half.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.engine import (ALTS, BTC, PROFILES, indicators, load,
                        load_with_btc_context, make_signal)
from stage3_prop import HORIZON, MAX_BREACH, OUT, RISK, STOP, RR, DAILY, eval_window, rank

SPLIT = 0.60

GATE = {  # label -> kwargs, one leading gate per cohort from stage 3b
    "btc_long": ("no ema200 + normal/expansion",
                 dict(require_ema200=False, regimes=(1, 2))),
    "btc_short": ("ema200 + any regime",
                  dict(require_ema200=True, regimes=(0, 1, 2, 3))),
    "alt_long": ("no ema200 + normal/expansion",
                 dict(require_ema200=False, regimes=(1, 2))),
    "alt_short": ("no ema200 + normal/expansion",
                  dict(require_ema200=False, regimes=(1, 2))),
}


def sweep(d, ind, sig, profile, sel, jud, mc, top=5):
    """Select params on window `sel`, report them on window `jud`."""
    cand = []
    for r in RISK:
        for s in STOP:
            for rr in RR:
                for dl in DAILY:
                    kw = dict(risk_pct=r, atr_stop=s, rr=rr, max_concurrent=mc,
                              internal_daily_pct=dl)
                    a = eval_window(d, ind, sig, profile, *sel, 30, **kw)
                    if a:
                        cand.append((kw, a))
    cand.sort(key=lambda x: rank(x[1]))
    rows = []
    for kw, a in cand[:top]:
        b = eval_window(d, ind, sig, profile, *jud, 30, **kw)
        if b:
            rows.append({"params": kw, "sel": a, "jud": b})
    rows.sort(key=lambda r: rank(r["jud"]))
    return rows


def show(title, rows):
    print(f"\n  {title}")
    print(f"    {'risk':>5s} {'stop':>5s} {'rr':>5s} {'dly':>4s} | "
          f"{'SEL pass':>9s} {'brch':>6s} | {'JUDGE pass':>11s} {'lo':>6s} "
          f"{'brch':>6s} {'t/o':>6s} {'win%':>6s} {'PF':>6s} {'t/mo':>5s} {'mo2p':>5s}")
    print("    " + "-" * 116)
    for r in rows:
        p, a, b = r["params"], r["sel"], r["jud"]
        print(f"    {p['risk_pct']:>5.2f} {p['atr_stop']:>5.2f} {p['rr']:>5.2f} "
              f"{p['internal_daily_pct']:>4.1f} | {a['pass']:>8.1f}% {a['breach']:>5.1f}% | "
              f"{b['pass']:>10.1f}% {b['pass_lo']:>5.1f}% {b['breach']:>5.1f}% "
              f"{b['timeout']:>5.1f}% {b['win']:>5.1f}% {(b['pf'] or 0):>6.2f} "
              f"{b['t_mo']:>5.1f} {(b['mo_to_pass'] or 0):>5.1f}")


def main():
    btc = load(BTC); btc_ind = indicators(btc)
    alt = load_with_btc_context(ALTS); alt_ind = indicators(alt)
    n = alt["close"].shape[0]
    cut = int(n * SPLIT)
    BULL = (1300, cut)         # 2024-04 -> 2025-06
    BEAR = (cut, n)            # 2025-06 -> 2026-08
    panels = {"btc_long": (btc, btc_ind, +1, 1), "btc_short": (btc, btc_ind, -1, 1),
              "alt_long": (alt, alt_ind, +1, 3), "alt_short": (alt, alt_ind, -1, 3)}

    print("=" * 128)
    print("STAGE 4 -- TEST 1: REVERSE THE SPLIT (select on BEAR, judge on BULL)")
    print("  If the winner flips with the split, the stage 3b result was a "
          "measurement of the test period.")
    print("=" * 128)

    rev = {}
    for cohort, (glab, gkw) in GATE.items():
        d, ind, direction, mc = panels[cohort]
        sig = make_signal(d, ind, direction, **gkw)
        for pname in ("classic_10k", "turbo_200k"):
            rows = sweep(d, ind, sig, PROFILES[pname], BEAR, BULL, mc)
            rev[f"{cohort}|{pname}"] = {"gate": glab, "rows": rows}
            show(f"{cohort} / {pname} / {glab}   [select BEAR -> judge BULL]", rows)

    print("\n" + "=" * 128)
    print("STAGE 4 -- TEST 2: LONG AND SHORT AS ONE BOOK")
    print("  The engines are mutually exclusive by construction (EMA21>EMA50 vs "
          "EMA21<EMA50),")
    print("  so the market decides which side is live and no regime forecast is "
          "required.")
    print("=" * 128)

    comb = {}
    for name, (d, ind, mc) in (("BTC", (btc, btc_ind, 1)), ("ALT", (alt, alt_ind, 3))):
        lk = GATE[f"{name.lower().replace('alt','alt')}_long"][1] if name == "ALT" else GATE["btc_long"][1]
        sk = GATE["alt_short"][1] if name == "ALT" else GATE["btc_short"][1]
        sl = make_signal(d, ind, +1, **lk)
        ss = make_signal(d, ind, -1, **sk)
        overlap = int(((sl != 0) & (ss != 0)).sum())
        sig = (sl + ss).astype(np.int8)
        print(f"\n  {name}: long bars {int((sl!=0).sum())}, short bars "
              f"{int((ss!=0).sum())}, overlap {overlap} "
              f"({'disjoint as expected' if overlap == 0 else 'OVERLAP -- not disjoint'})")
        for pname in ("classic_10k", "turbo_200k"):
            for lab, sel, jud in (("select BULL -> judge BEAR", BULL, BEAR),
                                  ("select BEAR -> judge BULL", BEAR, BULL)):
                rows = sweep(d, ind, sig, PROFILES[pname], sel, jud, mc)
                comb[f"{name}|{pname}|{lab}"] = rows
                show(f"{name} COMBINED / {pname}   [{lab}]", rows)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage4_regime.json").write_text(json.dumps(
        {"reverse": rev, "combined": comb,
         "windows": {"bull": BULL, "bear": BEAR}}, indent=2))
    print("\nsaved: experiments/stage4_regime.json")


if __name__ == "__main__":
    main()
