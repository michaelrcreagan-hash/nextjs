"""
Keyless data fetcher -- macro gate inputs and futures.

WHY THIS EXISTS
---------------
Two long-standing blockers in this project, both of which turn out to be
solvable with no API key at all:

  1. THE REGIME ENGINE RAN ON PROXIES. BASELINE_REPORT.md's top recommendation
     was to wire the real macro series: the config points at
     macro_sector_dominance's model, which scores VIX, SMH, net liquidity, ISM
     and DXY -- none of which were in any panel, so src/regime.py substituted
     SPY vol, SPY DMAs and TLT trend. I flagged that as the single largest
     known defect. ^VIX, ^TNX and DX-Y.NYB are all fetchable here.

  2. ASK #6 (FUTURES PROP) WAS NEVER STARTED. Binance returns 451 from this
     environment, Stooq returns HTML rather than CSV, and CoinGecko is crypto
     only, so there was no futures, index or commodity history anywhere. ES=F,
     NQ=F, CL=F, GC=F and ZN=F are all fetchable here.

SOURCE NOTES
------------
Yahoo's chart endpoint needs no key and no registration. It is an undocumented
public endpoint, so it can change without notice -- everything it returns is
cached to CSV on first fetch so a later outage cannot invalidate a backtest
that already ran.

Tried and rejected: FRED's fredgraph.csv and data/*.txt endpoints both time out
from this environment; Stooq returns an HTML shell instead of CSV for every
symbol tested.

INTERVAL LIMITS: Yahoo serves 1h bars for ~730 days and 1d bars for decades.
The 4H strategy engine resamples the 1h series; macro gating runs on dailies.
"""

from __future__ import annotations

import csv
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

socket.setdefaulttimeout(20)

STRATEGY_DIR = Path(__file__).resolve().parent
MACRO_DIR = STRATEGY_DIR / "Data" / "macro"
FUT_DIR = STRATEGY_DIR / "Data" / "futures"

Y = "https://query1.finance.yahoo.com/v8/finance/chart"

# Macro gate inputs. Each maps to a component the ChatGPT report's macro table
# and macro_sector_dominance's regime_score_model actually specify.
MACRO = {
    "VIX": "^VIX",          # volatility -- the real thing, not SPY realized vol
    "DXY": "DX-Y.NYB",      # dollar
    "TNX": "^TNX",          # 10y yield
    "IRX": "^IRX",          # 13w bill -> yield curve with TNX
    "SMH": "SMH",           # semis (the report's trend-quality proxy)
    "HYG": "HYG",           # high yield credit
    "LQD": "LQD",           # IG credit -> HYG/LQD = credit spread proxy
    "SPY": "SPY",
    "GLD": "GLD",
}

# Futures for ask #6: indices, rates, energy, metals.
FUTURES = {
    "ES": "ES=F",    # S&P 500
    "NQ": "NQ=F",    # Nasdaq 100
    "YM": "YM=F",    # Dow
    "RTY": "RTY=F",  # Russell 2000
    "CL": "CL=F",    # WTI crude
    "GC": "GC=F",    # gold
    "SI": "SI=F",    # silver
    "HG": "HG=F",    # copper
    "ZN": "ZN=F",    # 10y note
    "NG": "NG=F",    # natural gas
}


def fetch(symbol, rng="5y", interval="1d", retries=3):
    url = f"{Y}/{urllib.parse.quote(symbol)}?range={rng}&interval={interval}"
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read())
            res = j["chart"]["result"][0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            rows = []
            for i, t in enumerate(ts):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                v = (q.get("volume") or [None] * len(ts))[i]
                if None in (o, h, l, c):
                    continue          # Yahoo emits null bars on holidays
                rows.append((t, o, h, l, c, v or 0))
            return rows
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2 ** a)
    return []


def save(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "datetime", "open", "high", "low", "close", "volume"])
        for t, o, h, l, c, v in rows:
            w.writerow([t, datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                        o, h, l, c, v])


def grab(mapping, out_dir, rng, interval, label):
    print(f"\n{label}  (range={rng} interval={interval})")
    meta = {}
    for name, sym in mapping.items():
        f = out_dir / f"{name}_{interval}.csv"
        if f.exists():
            n = sum(1 for _ in f.open()) - 1
            print(f"  {name:<5s} cached ({n} bars)")
            meta[name] = {"symbol": sym, "bars": n, "cached": True}
            continue
        try:
            rows = fetch(sym, rng, interval)
        except Exception as e:
            print(f"  {name:<5s} FAIL {type(e).__name__}")
            continue
        if not rows:
            print(f"  {name:<5s} empty")
            continue
        save(rows, f)
        span = (rows[-1][0] - rows[0][0]) / 86400 / 365.25
        meta[name] = {"symbol": sym, "bars": len(rows), "years": round(span, 2),
                      "first": datetime.fromtimestamp(rows[0][0], tz=timezone.utc).date().isoformat(),
                      "last": datetime.fromtimestamp(rows[-1][0], tz=timezone.utc).date().isoformat()}
        print(f"  {name:<5s} {len(rows):>6d} bars  {span:.2f}y  "
              f"{meta[name]['first']} -> {meta[name]['last']}")
        time.sleep(0.4)
    (out_dir / f"meta_{interval}.json").write_text(json.dumps(
        {"source": "Yahoo Finance chart endpoint (keyless, undocumented)",
         "fetched": datetime.now(timezone.utc).isoformat(),
         "interval": interval, "series": meta}, indent=2))
    return meta


def main():
    print("=" * 78)
    print("KEYLESS FETCH -- Yahoo chart endpoint (no key, no registration)")
    print("=" * 78)
    grab(MACRO, MACRO_DIR, "10y", "1d", "MACRO GATE INPUTS (daily, 10y)")
    grab(FUTURES, FUT_DIR, "10y", "1d", "FUTURES (daily, 10y)")
    grab(FUTURES, FUT_DIR, "730d", "1h", "FUTURES (hourly, 730d -> resampled to 4H)")
    print("\nsaved to Data/macro/ and Data/futures/")


if __name__ == "__main__":
    main()
