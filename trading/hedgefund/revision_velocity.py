"""Analyst Revision Velocity — daily/weekly early-signal scan.

Mirrors lib/revisions.ts in the Next.js app:

    velocity      = sum(rating_change * weight)
    weight        = analyst_success * recency_decay
    recency_decay = 0.5 ** (age_days / half_life)

The normalized score (velocity / sum-of-weights) is a weighted average of
recent upgrades/downgrades; the half-life makes the freshest revisions
dominate so upward inflections surface before consensus catches up.

Data: FMP grades feed when FMP_API_KEY is set, else Yahoo Finance
upgradeDowngradeHistory (keyless, cookie+crumb). Writes
state/revision_velocity.json with per-symbol scores + bucket rollups.

Usage:
    python -m hedgefund.revision_velocity            # default watchlist
    python -m hedgefund.revision_velocity NVDA AGI   # explicit tickers
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

STATE_DIR = os.path.join(os.path.dirname(__file__), "state")
OUT_PATH = os.path.join(STATE_DIR, "revision_velocity.json")

DEFAULT_HALF_LIFE_DAYS = 30
DEFAULT_WINDOW_DAYS = 120
DEFAULT_FIRM_SUCCESS = 0.5

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Buckets: ai-bottlenecks | macro | sector-rotation | individual-stocks
TRACKED_ANALYSTS = [
    {
        "name": "Michael Siperco", "firm": "rbc capital", "bucket": "individual-stocks",
        "success": 0.65,  # TipRanks live 2026-07-08: rank #5, avg 1y +64.7%
        "coverage": ["NGD", "SA", "SSRM", "PAAS", "CGAU", "HL", "SKE", "CDE",
                     "ORLA", "NG", "AGI", "EGO", "GMINF", "KNTNF", "TORXF"],
    },
    {
        "name": "Carey MacRury", "firm": "canaccord", "bucket": "individual-stocks",
        "success": 0.60,
        "coverage": ["AEM", "ABX", "B", "KGC", "BTG", "IAG", "OR", "FNV",
                     "WPM", "ELD", "LUG", "AGI"],
    },
    {
        "name": "Shane Nagle", "firm": "national bank", "bucket": "individual-stocks",
        "success": 0.58,
        "coverage": ["TECK", "FM", "HBM", "CS", "LUN", "ERO", "CCO", "IVN",
                     "NGEX", "ALTM"],
    },
    {
        "name": "Don DeMarco", "firm": "national bank", "bucket": "individual-stocks",
        "success": 0.62,
        "coverage": ["AGI", "PAAS", "FVI", "EDV", "OGC", "AYA", "DPM", "KNT",
                     "MAG", "SSRM"],
    },
    {
        "name": "Quinn Bolton", "firm": "needham", "bucket": "ai-bottlenecks",
        "success": 0.67,
        "coverage": ["NVDA", "AVGO", "MRVL", "CRDO", "ALAB", "AMBA", "SLAB",
                     "RMBS", "MTSI", "SITM", "AIP", "LSCC", "POET"],
    },
]

FIRM_PROFILES = [
    (["needham"], "ai-bottlenecks", 0.62),
    (["raymond james"], "ai-bottlenecks", 0.60),
    (["goldman sachs"], "ai-bottlenecks", 0.61),
    (["piper sandler"], "ai-bottlenecks", 0.58),
    (["rbc capital", "rbc"], "ai-bottlenecks", 0.59),
    (["morgan stanley"], "macro", 0.57),          # Mike Wilson equity strategy
    (["bca research", "bca"], "macro", 0.55),
    (["fundstrat", "fs insight"], "macro", 0.60),  # Tom Lee
    (["duquesne"], "macro", 0.65),                 # Druckenmiller via 13F
    (["lseg starmine", "starmine", "refinitiv"], "sector-rotation", 0.60),
    (["canaccord genuity", "canaccord"], "individual-stocks", 0.56),
    (["national bank"], "individual-stocks", 0.56),
]

RATING_SCORES = {
    "strong buy": 2, "top pick": 2, "conviction buy": 2,
    "buy": 1, "outperform": 1, "overweight": 1, "positive": 1,
    "accumulate": 1, "add": 1, "sector outperform": 1,
    "market outperform": 1, "speculative buy": 1,
    "hold": 0, "neutral": 0, "market perform": 0, "sector perform": 0,
    "equal-weight": 0, "equal weight": 0, "in-line": 0, "in line": 0,
    "peer perform": 0, "perform": 0, "sector weight": 0, "mixed": 0,
    "underperform": -1, "underweight": -1, "reduce": -1, "negative": -1,
    "sector underperform": -1,
    "sell": -2, "strong sell": -2,
}

WATCHLIST = [
    "NVDA", "AVGO", "MRVL", "CRDO", "ALAB", "COHR", "LITE", "AAOI", "MU",
    "VRT", "AGI", "PAAS", "SSRM", "AEM", "KGC", "TECK",
]


def _rating_score(grade):
    if not grade:
        return None
    return RATING_SCORES.get(grade.strip().lower())


def rating_change(action, from_grade, to_grade):
    frm, to = _rating_score(from_grade), _rating_score(to_grade)
    action = (action or "").lower()
    if action.startswith("up"):
        return (to - frm) if (frm is not None and to is not None and to > frm) else 1.0
    if action.startswith("down"):
        return (to - frm) if (frm is not None and to is not None and to < frm) else -1.0
    if action.startswith(("init", "resum", "reinstat")):
        return 0.75 * to if to is not None else 0.0
    if frm is not None and to is not None and to != frm:
        return float(to - frm)
    return 0.0


def classify(firm, symbol):
    """-> (success, bucket, analyst_name_or_None)"""
    key = (firm or "").strip().lower()
    for a in TRACKED_ANALYSTS:
        if a["firm"] in key and symbol.upper() in a["coverage"]:
            return a["success"], a["bucket"], a["name"]
    for aliases, bucket, success in FIRM_PROFILES:
        if any(key.startswith(al) or al in key for al in aliases):
            return success, bucket, None
    return DEFAULT_FIRM_SUCCESS, "other", None


_direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode())
    except Exception:
        # Egress proxies get rate-limited by Yahoo; retry direct.
        with _direct_opener.open(req, timeout=30) as res:
            return json.loads(res.read().decode())


def fetch_fmp(symbol):
    key = os.environ.get("FMP_API_KEY")
    if not key:
        return None
    url = (
        "https://financialmodelingprep.com/stable/grades?symbol="
        f"{urllib.parse.quote(symbol)}&apikey={key}"
    )
    rows = _http_json(url)
    if not isinstance(rows, list):
        return None
    return [
        {
            "date": r["date"], "firm": r["gradingCompany"], "action": r["action"],
            "from_grade": r.get("previousGrade"), "to_grade": r.get("newGrade"),
        }
        for r in rows
    ]


_yahoo_auth = {}


def _cookie_from_fc(opener):
    req = urllib.request.Request("https://fc.yahoo.com", headers={"User-Agent": UA})
    try:
        res = opener.open(req, timeout=15)
        return (res.headers.get("set-cookie") or "").split(";")[0]
    except urllib.error.HTTPError as e:
        # fc.yahoo.com 404s but still sets the session cookie
        return (e.headers.get("set-cookie") or "").split(";")[0]


def _yahoo_crumb():
    if _yahoo_auth.get("t", 0) > time.time() - 1800:
        return _yahoo_auth
    for opener in (urllib.request.build_opener(), _direct_opener):
        try:
            cookie = _cookie_from_fc(opener)
            if not cookie:
                continue
            crumb_req = urllib.request.Request(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                headers={"User-Agent": UA, "Cookie": cookie},
            )
            with opener.open(crumb_req, timeout=15) as res:
                crumb = res.read().decode().strip()
            if crumb and "Too Many" not in crumb:
                _yahoo_auth.update({"cookie": cookie, "crumb": crumb, "t": time.time()})
                return _yahoo_auth
        except Exception:
            continue
    return None


def fetch_yahoo(symbol):
    auth = None
    try:
        auth = _yahoo_crumb()
    except Exception:
        pass
    url = (
        "https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
        f"{urllib.parse.quote(symbol)}?modules=upgradeDowngradeHistory"
    )
    headers = {}
    if auth:
        url += "&crumb=" + urllib.parse.quote(auth["crumb"])
        headers["Cookie"] = auth["cookie"]
    data = _http_json(url, headers)
    hist = (
        (data.get("quoteSummary", {}).get("result") or [{}])[0]
        .get("upgradeDowngradeHistory", {})
        .get("history")
    )
    if not isinstance(hist, list):
        return None
    return [
        {
            "date": datetime.fromtimestamp(h["epochGradeDate"], tz=timezone.utc)
            .strftime("%Y-%m-%d"),
            "firm": h.get("firm", ""), "action": h.get("action", ""),
            "from_grade": h.get("fromGrade"), "to_grade": h.get("toGrade"),
        }
        for h in hist
    ]


def fetch_events(symbol):
    for provider, fn in (("fmp", fetch_fmp), ("yahoo", fetch_yahoo)):
        try:
            events = fn(symbol)
        except Exception:
            events = None
        if events:
            return events, provider
    return None, None


def compute_velocity(symbol, events, half_life=DEFAULT_HALF_LIFE_DAYS,
                     window=DEFAULT_WINDOW_DAYS, as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    velocity = weight_sum = 0.0
    upgrades = downgrades = count = 0
    buckets = {}
    tracked_hits = []

    for ev in events:
        try:
            dt = datetime.strptime(ev["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            continue
        age = (as_of - dt).total_seconds() / 86400.0
        if age < 0 or age > window:
            continue
        change = rating_change(ev.get("action"), ev.get("from_grade"), ev.get("to_grade"))
        success, bucket, analyst = classify(ev.get("firm", ""), symbol)
        decay = math.pow(0.5, age / half_life)
        w = success * decay
        velocity += change * w
        weight_sum += w
        count += 1
        upgrades += change > 0
        downgrades += change < 0
        b = buckets.setdefault(bucket, {"velocity": 0.0, "weight_sum": 0.0, "events": 0})
        b["velocity"] += change * w
        b["weight_sum"] += w
        b["events"] += 1
        if analyst and change != 0:
            tracked_hits.append({
                "analyst": analyst, "date": ev["date"], "action": ev.get("action"),
                "to_grade": ev.get("to_grade"), "contribution": round(change * w, 4),
            })

    wavg = velocity / weight_sum if weight_sum > 0 else 0.0
    signal = (
        "strong-up" if wavg >= 0.25 else "up" if wavg >= 0.08
        else "strong-down" if wavg <= -0.25 else "down" if wavg <= -0.08
        else "flat"
    )
    return {
        "symbol": symbol.upper(),
        "velocity": round(velocity, 4),
        "weighted_avg": round(wavg, 4),
        "weight_sum": round(weight_sum, 4),
        "events": count,
        "upgrades": upgrades,
        "downgrades": downgrades,
        "signal": signal,
        "buckets": {k: {**v, "velocity": round(v["velocity"], 4),
                        "weight_sum": round(v["weight_sum"], 4)}
                    for k, v in buckets.items()},
        "tracked_hits": tracked_hits,
    }


def run(symbols=None):
    symbols = symbols or WATCHLIST
    results, errors = [], []
    for sym in symbols:
        events, provider = fetch_events(sym)
        if not events:
            errors.append(sym)
            continue
        res = compute_velocity(sym, events)
        res["provider"] = provider
        results.append(res)
        time.sleep(0.3)  # be polite to keyless providers

    results.sort(key=lambda r: r["weighted_avg"], reverse=True)
    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "half_life_days": DEFAULT_HALF_LIFE_DAYS,
        "window_days": DEFAULT_WINDOW_DAYS,
        "results": results,
        "errors": errors,
    }
    os.makedirs(STATE_DIR, exist_ok=True)
    # Keep a rolling history so week-over-week velocity deltas are computable.
    history = []
    if os.path.exists(OUT_PATH):
        try:
            prev = json.load(open(OUT_PATH))
            history = prev.get("history", [])
            history.append({
                "as_of": prev.get("as_of"),
                "scores": {r["symbol"]: r["weighted_avg"] for r in prev.get("results", [])},
            })
            history = history[-30:]
        except Exception:
            pass
    payload["history"] = history
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


def report_lines(payload):
    lines = ["Analyst revision velocity (wtd avg of recent up/downgrades):"]
    for r in payload["results"][:8]:
        star = ""
        if r["tracked_hits"]:
            names = sorted({h["analyst"] for h in r["tracked_hits"]})
            star = " ★ " + ", ".join(names)
        lines.append(
            f"  {r['symbol']:<6} {r['weighted_avg']:+.3f} [{r['signal']}] "
            f"{r['upgrades']}up/{r['downgrades']}dn of {r['events']}{star}"
        )
    if payload["errors"]:
        lines.append("  no data: " + ", ".join(payload["errors"]))
    return lines


if __name__ == "__main__":
    args = [a.upper() for a in sys.argv[1:]] or None
    out = run(args)
    print("\n".join(report_lines(out)))
    print(f"\nwrote {OUT_PATH}")
