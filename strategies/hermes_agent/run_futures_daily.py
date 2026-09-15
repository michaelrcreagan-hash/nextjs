"""
Futures prop, second attempt: DAILY bars and a mean-reversion challenger.

The 4H run failed unambiguously -- profit factor 0.52-0.91 on every arm, i.e.
NEGATIVE EXPECTANCY, with 67-100% drawdown breaches. Notably the trailing and
static drawdown variants produced nearly identical results, which is itself
informative: when expectancy is below 1.0 the drawdown rule is irrelevant
because you lose either way. Risk rules cannot rescue a losing edge.

Two hypotheses for why the crypto champion did not transfer, tested here:

  H1 -- WRONG TIMEFRAME. Crypto trends intraday; index futures trend on daily
        and mean-revert intraday. The 4H expansion breakout may be sampling
        futures noise. Daily bars also give 10 YEARS of history here versus
        2.4 years at 4H, which is a far better test.

  H2 -- WRONG DIRECTION. Equity index futures are famous for buying dips, not
        breakouts. If breakout expectancy is negative, its mirror image may be
        positive. Testing the inverted rule is the cheapest possible check on
        whether there is any exploitable structure at all, and if BOTH sides
        lose then the answer is costs/noise rather than direction.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import src.h4_engine as E
from run_futures_prop import HDR, PROFILES, evaluate, row
from src.h4_engine import build_indicators, signals

FUT_DIR = Path(__file__).resolve().parent / "Data" / "futures"
OUT = Path(__file__).resolve().parent / "experiments" / "futures_prop"


def load_daily():
    raw = {}
    for f in sorted(FUT_DIR.glob("*_1d.csv")):
        sym = f.stem.split("_")[0]
        raw[sym] = {int(r["ts"]): (float(r["open"]), float(r["high"]),
                                   float(r["low"]), float(r["close"]),
                                   float(r["volume"]))
                    for r in csv.DictReader(f.open())}
    grid = sorted(set.intersection(*(set(v) for v in raw.values())))
    d = {"ts": np.array(grid, dtype=np.int64), "symbols": sorted(raw)}
    for k, i in (("open", 0), ("high", 1), ("low", 2), ("close", 3), ("volume", 4)):
        d[k] = np.ascontiguousarray(
            np.array([[raw[s][t][i] for s in d["symbols"]] for t in grid],
                     dtype=np.float64))
    return d


def main():
    d = load_daily()
    n = d["close"].shape[0]
    ind = build_indicators(d)
    sig = signals(d, ind, engine="keltner", allow_short=True)
    inverted = (-sig).astype(np.int8)          # H2: the mirror image

    print("=" * 110)
    print("FUTURES PROP -- DAILY bars (10y) + mean-reversion challenger")
    print("=" * 110)
    print(f"  panel: {n} daily bars x {len(d['symbols'])} ({d['symbols']})")
    print(f"  signals: {int((sig != 0).sum())} breakout bars, "
          f"{100 * (sig != 0).mean():.2f}% of cells")

    # Daily bars: 21/month, and the prop clock is calendar time either way.
    E_BARS_PER_MONTH = 21
    import run_futures_prop as RFP
    RFP.BARS_PER_DAY = 1

    prof = PROFILES["topstep50k_trailing"]
    print("\n" + "-" * 110)
    print(f"  H1 -- DAILY Keltner breakout (trailing DD, the real futures rule)")
    print("-" * 110)
    print(HDR)
    print("-" * 110)
    res = {}
    for lab, s, kw in (("breakout risk0.5 rr1.25", sig, dict(risk_pct=0.5, rr=1.25)),
                       ("breakout risk0.5 rr1.5", sig, dict(risk_pct=0.5, rr=1.5)),
                       ("breakout risk0.75 rr1.5", sig, dict(risk_pct=0.75, rr=1.5)),
                       ("breakout risk0.5 rr2.0", sig, dict(risk_pct=0.5, rr=2.0))):
        r = evaluate(d, ind, s, prof, n_starts=40, warmup=900, **kw)
        res[lab] = r
        print(row(lab, r))

    print("\n" + "-" * 110)
    print("  H2 -- INVERTED (mean-reversion): fade the same breakouts")
    print("-" * 110)
    print(HDR)
    print("-" * 110)
    for lab, kw in (("FADE risk0.5 rr1.25", dict(risk_pct=0.5, rr=1.25)),
                    ("FADE risk0.5 rr1.5", dict(risk_pct=0.5, rr=1.5)),
                    ("FADE risk0.75 rr1.5", dict(risk_pct=0.75, rr=1.5))):
        r = evaluate(d, ind, inverted, prof, n_starts=40, warmup=900, **kw)
        res[lab] = r
        print(row(lab, r))

    best = max(res, key=lambda k: (res[k]["profit_factor"] or 0))
    print(f"\n  best profit factor: {best} = {res[best]['profit_factor']}")
    pf = res[best]["profit_factor"] or 0
    print(f"  VERDICT: {'positive expectancy found' if pf > 1.1 else 'NO POSITIVE EXPECTANCY on futures in either direction'}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "daily_results.json").write_text(json.dumps(
        {"bars": n, "symbols": d["symbols"], "results": res,
         "best": best, "verdict": "positive" if pf > 1.1 else "none"}, indent=2))
    print("\nsaved: experiments/futures_prop/daily_results.json")


if __name__ == "__main__":
    main()
