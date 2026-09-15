"""
Build the point-in-time panel: what was knowable about each company each day.

This is the module where a fundamental backtest is usually quietly ruined, so
the rules it enforces are written out rather than assumed.

RULE 1 -- A FACT EXISTS ONLY AFTER IT IS FILED.
Every observation is stamped with the SEC `filed` date, never the fiscal period
end. On any trading day the model sees the most recent observation whose filed
date is strictly on or before that day. NVDA's July-2026 quarter enters the
panel on 2026-08-26, not 2026-07-26.

RULE 2 -- ORIGINAL REPORTS, NOT RESTATEMENTS.
The same fiscal period is re-reported in later filings, sometimes revised. For
each period the fact with the EARLIEST filed date is kept, because that is what
the market actually saw. Using the final restated value would leak knowledge
that arrived years later. (Consequence: the panel deliberately contains figures
later revised. That is the correct choice, and it is a limitation of realism
only in the sense that reality had it too.)

RULE 3 -- Q4 MUST BE DERIVED, AND DERIVING IT COSTS A FILING DATE.
Most filers never report a standalone fiscal Q4; the 10-K states the full year.
Q4 is therefore computed as FY minus Q1+Q2+Q3, and -- this is the part that
matters -- it is stamped with the 10-K's filing date, which is when it became
knowable. Stamping it with the quarter end would grant two to three months of
lookahead precisely at the year's most important print.

RULE 4 -- A FISCAL QUARTER IS 80-100 DAYS.
Filers tag 6-month and 9-month cumulative durations with the same concepts.
Anything outside the quarterly window is classified by duration, not trusted by
label, and cumulative periods are used only to derive Q4.

WHAT COMES OUT
--------------
`panel.npz` holds daily-aligned arrays of shape (n_days, n_tickers): the
as-known value of every fundamental feature, plus prices and forward returns.
Because fundamentals only change on filing dates, the daily arrays are step
functions -- which is exactly what a portfolio rebalancing on any given day
would have seen.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.universe import BENCH, LAYER_OF, TICKERS

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "fundamentals" / "raw"
PX = ROOT / "data" / "prices"
OUT = ROOT / "data"

FLOW = ["revenue", "gross_profit", "operating_income", "net_income", "rnd", "eps_diluted"]
STOCK = ["inventory", "backlog_rpo", "deferred_rev"]


def d(s):
    return date.fromisoformat(s)


def dur(f):
    return (d(f["end"]) - d(f["start"])).days if f.get("start") else None


def dedupe_earliest(facts, keyfn):
    """Keep, per period, the fact that was filed first -- the original report."""
    best = {}
    for f in facts:
        k = keyfn(f)
        if k not in best or f["filed"] < best[k]["filed"]:
            best[k] = f
    return best


def quarterly(facts):
    """
    Return {period_end: (value, filed)} for true fiscal quarters, with Q4
    derived from the annual figure where the filer reports only a full year.
    """
    q = dedupe_earliest([f for f in facts if dur(f) and 80 <= dur(f) <= 100],
                        lambda f: f["end"])
    out = {k: (v["val"], v["filed"]) for k, v in q.items()}

    # Annual facts, used only to back out an unreported Q4.
    ann = dedupe_earliest([f for f in facts if dur(f) and 350 <= dur(f) <= 380],
                          lambda f: f["end"])
    for end, a in ann.items():
        if end in out:
            continue                      # a real standalone Q4 was reported
        fy_start = d(a["start"])
        # The three quarters that fall inside this fiscal year.
        inner = [(k, v) for k, v in out.items() if fy_start < d(k) < d(end)]
        if len(inner) != 3:
            continue
        val = a["val"] - sum(v[0] for _, v in inner)
        # Knowable on the 10-K's filing date, never before.
        out[end] = (val, a["filed"])
    return out


def instant(facts):
    """Balance-sheet style facts: an instant, no duration."""
    inst = dedupe_earliest([f for f in facts if not f.get("start")],
                           lambda f: f["end"])
    return {k: (v["val"], v["filed"]) for k, v in inst.items()}


def observations(tk):
    """
    Collapse one company's facts into a list of dated observations:
        [{filed, period_end, revenue, gross_profit, ...}, ...]
    keyed by fiscal period, each carrying the date it became public.
    """
    f = RAW / f"{tk}.json"
    if not f.exists():
        return []
    facts = json.loads(f.read_text())["facts"]

    series = {}
    for c in FLOW:
        series[c] = quarterly(facts.get(c, []))
    for c in STOCK:
        series[c] = instant(facts.get(c, []))

    periods = sorted({p for s in series.values() for p in s})
    rows = []
    for p in periods:
        rec = {"period_end": p}
        filed = None
        for c, s in series.items():
            if p in s:
                rec[c] = s[p][0]
                # An observation is knowable only once its LAST component is.
                filed = s[p][1] if filed is None else max(filed, s[p][1])
            else:
                rec[c] = np.nan
        if filed is None or np.isnan(rec.get("revenue", np.nan)):
            continue
        rec["filed"] = filed
        rows.append(rec)
    rows.sort(key=lambda r: r["period_end"])
    return rows


def _pick(avail, target, tol):
    """The observation whose period end is nearest `target`, within `tol` days."""
    best, bd = None, None
    for q in avail:
        gap = abs((d(q["period_end"]) - target).days)
        if gap <= tol and (bd is None or gap < bd):
            best, bd = q, gap
    return best


def features(rows):
    """
    Derived fundamentals, computed so that each observation's feature set is
    FIXED at its own filing date and can never change afterwards.

    Two bugs lived here and were caught by the truncation test (T3), not by
    inspection -- both would have silently inflated every result downstream.

    1. POSITIONAL LAGS ARE NOT TRUNCATION-INVARIANT. Year-over-year used
       rows[i-4] on a list sorted by period end. Filers sometimes first tag an
       old period in a much later document (the filing-lag distribution here has
       a 90th percentile of 402 days), so adding later history INSERTS rows into
       the middle of that sequence and silently changes what "four quarters ago"
       refers to. Comparisons are now matched by DATE -- nearest period end to
       one year back, within a tolerance -- so they do not depend on how many
       rows happen to exist.

    2. A COMPARISON MUST ITSELF HAVE BEEN PUBLISHED. Even a correctly matched
       prior quarter is unusable if it was not public when this quarter was
       filed. Each observation may look only at prior periods whose own filed
       date is on or before its own, which is what makes the feature set stable
       once stamped.
    """
    rows = sorted(rows, key=lambda r: r["period_end"])
    for i, r in enumerate(rows):
        # Only prior periods that were already public when THIS one was filed.
        avail = [q for q in rows[:i] if q["filed"] <= r["filed"]]
        pe = d(r["period_end"])
        prev4 = _pick(avail, pe - timedelta(days=365), 45)
        prev1 = _pick(avail, pe - timedelta(days=91), 30)
        prev5 = _pick(avail, pe - timedelta(days=456), 45)
        rev = r.get("revenue", np.nan)

        def yoy(field, back=prev4):
            if not back:
                return np.nan
            a, b = r.get(field, np.nan), back.get(field, np.nan)
            if a is None or b is None or np.isnan(a) or np.isnan(b) or b == 0:
                return np.nan
            # Sign-flip growth (negative base) is not interpretable as growth.
            return (a - b) / abs(b) if b > 0 else np.nan

        r["rev_yoy"] = yoy("revenue")
        r["eps_yoy"] = yoy("eps_diluted")
        r["backlog_yoy"] = yoy("backlog_rpo")

        # Revenue ACCELERATION: the change in the YoY rate. This is the closest
        # thing in reported data to "earnings momentum" that does not depend on
        # analyst estimates, whose point-in-time vintages are not available here.
        prev_yoy = np.nan
        if prev1 and prev5:
            a, b = prev1.get("revenue", np.nan), prev5.get("revenue", np.nan)
            if not (a is None or b is None or np.isnan(a) or np.isnan(b) or b <= 0):
                prev_yoy = (a - b) / b
        r["rev_accel"] = (r["rev_yoy"] - prev_yoy
                          if not (np.isnan(r["rev_yoy"]) or np.isnan(prev_yoy))
                          else np.nan)

        gp, oi = r.get("gross_profit", np.nan), r.get("operating_income", np.nan)
        r["gross_margin"] = gp / rev if rev and not np.isnan(gp) and rev > 0 else np.nan
        r["op_margin"] = oi / rev if rev and not np.isnan(oi) and rev > 0 else np.nan
        r["rnd_intensity"] = (r.get("rnd", np.nan) / rev
                              if rev and rev > 0 else np.nan)

        # Margin EXPANSION year over year -- level tells you the business model,
        # change tells you whether pricing power is improving right now.
        if prev4:
            pgm = (prev4.get("gross_profit", np.nan) / prev4["revenue"]
                   if prev4.get("revenue") else np.nan)
            pom = (prev4.get("operating_income", np.nan) / prev4["revenue"]
                   if prev4.get("revenue") else np.nan)
            r["gm_delta"] = r["gross_margin"] - pgm
            r["om_delta"] = r["op_margin"] - pom
        else:
            r["gm_delta"] = r["om_delta"] = np.nan

        # Backlog coverage: RPO relative to trailing-twelve-month revenue.
        # TTM is built from date-matched prior quarters that were public when
        # this one was filed, for the same reason the growth rates are.
        q = [r] + [x for x in (prev1,
                               _pick(avail, pe - timedelta(days=182), 30),
                               _pick(avail, pe - timedelta(days=273), 30))
                   if x is not None]
        ttm = (np.nansum([x.get("revenue", np.nan) for x in q])
               if len(q) == 4 else np.nan)
        bl = r.get("backlog_rpo", np.nan)
        r["backlog_cover"] = (bl / ttm if ttm and not np.isnan(bl) and ttm > 0
                              else np.nan)
        r["ttm_rev"] = ttm
    return rows


FEATURES = ["rev_yoy", "rev_accel", "eps_yoy", "gross_margin", "op_margin",
            "gm_delta", "om_delta", "rnd_intensity", "backlog_yoy",
            "backlog_cover"]


def load_prices(sym):
    f = PX / f"{sym}.csv"
    if not f.exists():
        return None
    out = {}
    for r in csv.DictReader(f.open()):
        out[r["date"]] = (float(r["close"]), float(r["adjclose"]), float(r["volume"]))
    return out


def main():
    syms = [t for t in TICKERS if t != "PSTG"]

    # Trading calendar from SPY -- the union of tickers would include days a
    # thinly traded name printed but the market did not.
    spy = load_prices("SPY")
    dates = sorted(spy)
    di = {x: i for i, x in enumerate(dates)}
    n, m = len(dates), len(syms)
    print("=" * 100)
    print(f"PANEL -- {n} trading days x {m} tickers, {dates[0]} -> {dates[-1]}")
    print("=" * 100)

    px = np.full((n, m), np.nan)
    adj = np.full((n, m), np.nan)
    vol = np.full((n, m), np.nan)
    feat = {k: np.full((n, m), np.nan) for k in FEATURES}
    stale = np.full((n, m), np.nan)          # days since the fact was filed

    cover = {}
    for j, t in enumerate(syms):
        p = load_prices(t)
        if p:
            for ds, (c, a, v) in p.items():
                if ds in di:
                    px[di[ds], j], adj[di[ds], j], vol[di[ds], j] = c, a, v

        rows = features(observations(t))
        cover[t] = {"observations": len(rows),
                    "first_filed": rows[0]["filed"] if rows else None,
                    "last_filed": rows[-1]["filed"] if rows else None}
        if not rows:
            continue

        # Step-function fill: walk the calendar, admitting each observation only
        # once its filing date has passed.
        #
        # `cur` must track the most recent FISCAL PERIOD among everything filed
        # so far -- not simply the most recently filed row. Filers sometimes tag
        # an old period for the first time in a much later document, and taking
        # the last-filed row would let a two-year-old quarter overwrite the
        # current one, marching the company's apparent fundamentals backwards.
        rows.sort(key=lambda r: r["filed"])
        k = 0
        cur = None
        for i, ds in enumerate(dates):
            while k < len(rows) and rows[k]["filed"] <= ds:
                if cur is None or rows[k]["period_end"] > cur["period_end"]:
                    cur = rows[k]
                k += 1
            if cur is None:
                continue
            for f in FEATURES:
                v = cur.get(f, np.nan)
                feat[f][i, j] = v if v is not None else np.nan
            stale[i, j] = (d(ds) - d(cur["filed"])).days

    # Benchmarks on the same calendar.
    bench = {}
    for b in BENCH:
        p = load_prices(b)
        arr = np.full(n, np.nan)
        if p:
            for ds, (_, a, _) in p.items():
                if ds in di:
                    arr[di[ds]] = a
        bench[b] = arr

    np.savez_compressed(
        OUT / "panel.npz",
        dates=np.array(dates), symbols=np.array(syms),
        layers=np.array([LAYER_OF[t] for t in syms]),
        close=px, adjclose=adj, volume=vol, staleness=stale,
        **{f"feat_{k}": v for k, v in feat.items()},
        **{f"bench_{b}": v for b, v in bench.items()})

    print(f"\n  price coverage : {100*np.isfinite(adj).mean():.1f}% of cells")
    for f in FEATURES:
        c = 100 * np.isfinite(feat[f]).mean()
        names = int((np.isfinite(feat[f]).any(axis=0)).sum())
        print(f"  {f:<16s} {c:>5.1f}% of cells, {names:>2d}/{m} names")

    thin = [t for t, c in cover.items() if c["observations"] < 12]
    print(f"\n  fewer than 12 quarterly observations: {len(thin)}  {thin}")
    (OUT / "panel_coverage.json").write_text(json.dumps(cover, indent=2))
    print(f"\nsaved: data/panel.npz  ({(OUT/'panel.npz').stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
