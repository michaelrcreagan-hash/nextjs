"""
Daily adjusted prices for the bottleneck universe, from Yahoo's keyless endpoint.

SOURCE CHOICE
-------------
FMP is the fundamentals source for this project (it exposes filingDate, which
is the whole point -- see fetch_fundamentals.py), but its historical price
endpoints are gated behind a higher plan tier on this account: every chart call
with a date range returns ACCESS DENIED. Yahoo's chart endpoint needs no key and
serves decades of daily bars, so prices come from there.

ADJUSTMENT
----------
Yahoo's `adjclose` series is split- AND dividend-adjusted. That is the correct
series for computing returns. It is NOT correct for anything that compares a
price against a historical nominal level, so only returns are derived from it.
Both `close` and `adjclose` are stored so that distinction stays auditable.

Everything is cached to CSV on first fetch. An undocumented endpoint can change
or disappear without notice, and a backtest that already ran should not be
invalidated by an outage weeks later.
"""

from __future__ import annotations

import csv
import json
import socket
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.universe import BENCH, END, LATE_LISTINGS, START, TICKERS

socket.setdefaulttimeout(30)
OUT = Path(__file__).resolve().parent / "data" / "prices"
Y = "https://query1.finance.yahoo.com/v8/finance/chart"


def fetch(symbol, start, end, retries=4):
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp())
    url = (f"{Y}/{urllib.parse.quote(symbol)}?period1={p1}&period2={p2}"
           f"&interval=1d&events=div%2Csplit")
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read())
            res = j["chart"]["result"][0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
            rows = []
            for i, t in enumerate(ts):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c) or adj[i] is None:
                    continue           # Yahoo emits null bars on halts/holidays
                rows.append((t, o, h, l, c, adj[i], (q.get("volume") or [0])[i] or 0))
            return rows
        except Exception as e:
            last = e
            if a < retries - 1:
                time.sleep(2 ** a)
    raise last


def save(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "adjclose", "volume"])
        for t, o, h, l, c, a, v in rows:
            w.writerow([datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
                        o, h, l, c, a, v])


def main():
    syms = TICKERS + BENCH
    print("=" * 92)
    print(f"PRICES -- {len(syms)} symbols, {START} -> {END} (Yahoo, keyless)")
    print("=" * 92)
    meta, missing = {}, []
    for s in syms:
        f = OUT / f"{s}.csv"
        if f.exists():
            n = sum(1 for _ in f.open()) - 1
            meta[s] = {"bars": n, "cached": True}
            print(f"  {s:<6s} cached ({n} bars)")
            continue
        try:
            rows = fetch(s, START, END)
        except Exception as e:
            print(f"  {s:<6s} FAIL {type(e).__name__}: {e}")
            missing.append(s)
            continue
        if not rows:
            print(f"  {s:<6s} EMPTY")
            missing.append(s)
            continue
        # Enforce the listing date rather than trusting the vendor. Yahoo serves
        # pre-merger SPAC-shell history under the post-merger ticker, which is
        # not a price anyone could have traded for this company.
        flag = ""
        if s in LATE_LISTINGS:
            cut = LATE_LISTINGS[s]
            before = len(rows)
            rows = [r for r in rows
                    if datetime.fromtimestamp(r[0], tz=timezone.utc).date().isoformat() >= cut]
            dropped = before - len(rows)
            flag = f"  <- listed {cut}" + (f", dropped {dropped} pre-listing bars"
                                           if dropped else ", clean")
            if not rows:
                print(f"  {s:<6s} EMPTY after listing-date cut")
                missing.append(s)
                continue

        save(rows, f)
        first = datetime.fromtimestamp(rows[0][0], tz=timezone.utc).date().isoformat()
        last = datetime.fromtimestamp(rows[-1][0], tz=timezone.utc).date().isoformat()
        meta[s] = {"bars": len(rows), "first": first, "last": last,
                   "listing_enforced": LATE_LISTINGS.get(s)}
        print(f"  {s:<6s} {len(rows):>5d} bars  {first} -> {last}{flag}")
        time.sleep(0.35)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_meta.json").write_text(json.dumps(
        {"source": "Yahoo Finance chart endpoint (keyless)",
         "fetched": datetime.now(timezone.utc).isoformat(),
         "start": START, "end": END, "series": meta, "missing": missing}, indent=2))
    print(f"\n  {len(meta)} fetched, {len(missing)} missing"
          + (f": {missing}" if missing else ""))


if __name__ == "__main__":
    main()
