"""
Build a 4-HOUR OHLC panel from Coinbase hourly candles.

WHY THIS EXISTS
---------------
Two independent lines of evidence pointed at the same missing ingredient:

  1. My own daily-bar prop backtest produced 3-8 trades/month against the
     15-20+ the target arithmetic requires. I concluded the frequency wall was
     structural to DAILY BARS, not to the rule.
  2. The author's ChatGPT research report names a **4-hour Keltner breakout
     with MACD confirmation** as its champion strategy, and retires naked
     30m/1H breakouts as noise.

Coinbase Exchange serves 1h candles (granularity=3600) with no key. Resampling
1h -> 4h gives the exact resolution the champion strategy is specified on, and
roughly 6x the bar count of the daily panel.

OHLC, NOT JUST CLOSE
--------------------
The daily panel carries close only, which forced a close-to-close ATR proxy and
close-only stop fills. Keltner channels, true-range ATR and intrabar stop fills
all need high/low. This fetches full OHLCV.

BAR CONVENTION: a 4H bar is stamped with its OPEN time and aggregates
[t, t+4h). Signals are evaluated on CLOSED bars only -- the decision at bar t
uses bars <= t-1. No intrabar peeking.
"""

from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parent
OUT_DIR = STRATEGY_DIR / "Data" / "h4"

CB = "https://api.exchange.coinbase.com"
GRAN = 3600                 # 1 hour
MAX_CANDLES = 300           # Coinbase per-request cap -> 300h = 12.5 days
YEARS = 3

# Breakout's leverage tiers make BTC/ETH the only names worth heavy size, and
# the ChatGPT report scopes its champion to BTC with ETH secondary. Keep the
# fetch tight: majors plus the most liquid alts actually listed on Breakout.
PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
            "LINK-USD", "AVAX-USD", "LTC-USD"]


def fetch_json(url, retries=4):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "python"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if a == retries - 1:
                raise
            time.sleep(2 ** a)
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2 ** a)
    return None


def fetch_hourly(product, start, end):
    """Returns {epoch_sec: [low, high, open, close, volume]}."""
    out = {}
    cursor = start
    span = timedelta(hours=MAX_CANDLES - 1)
    while cursor < end:
        ce = min(cursor + span, end)
        url = (f"{CB}/products/{product}/candles?granularity={GRAN}"
               f"&start={cursor.strftime('%Y-%m-%dT%H:%M:%SZ')}"
               f"&end={ce.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        data = fetch_json(url)
        if data is None:
            return {}
        for row in data:
            out[int(row[0])] = row[1:6]
        cursor = ce + timedelta(hours=1)
        time.sleep(0.28)
    return out


def to_4h(hourly):
    """
    Aggregate 1h -> 4h on UTC boundaries 00/04/08/12/16/20.

    A bucket is emitted only if it has at least 3 of its 4 hours, so a partial
    bar at the edge of a gap does not masquerade as a full one.
    """
    buckets = {}
    for ts, (lo, hi, op, cl, vol) in hourly.items():
        b = ts - (ts % 14400)
        buckets.setdefault(b, []).append((ts, lo, hi, op, cl, vol))
    out = {}
    for b, rows in buckets.items():
        if len(rows) < 3:
            continue
        rows.sort()
        out[b] = {
            "open": rows[0][3],
            "high": max(r[2] for r in rows),
            "low": min(r[1] for r in rows),
            "close": rows[-1][4],
            "volume": sum(r[5] for r in rows),
        }
    return out


def main():
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=365 * YEARS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"fetching 1h -> 4h, {len(PRODUCTS)} products, "
          f"{start.date()} -> {end.date()}")

    meta = {}
    for p in PRODUCTS:
        sym = p.split("-")[0]
        f = OUT_DIR / f"{sym}_4h.csv"
        if f.exists():
            n = sum(1 for _ in f.open()) - 1
            print(f"  {sym:<6s} cached ({n} bars)")
            meta[sym] = {"bars": n, "cached": True}
            continue
        t0 = time.time()
        try:
            h = fetch_hourly(p, start, end)
        except Exception as e:
            print(f"  {sym:<6s} ERROR {type(e).__name__}")
            continue
        if not h:
            print(f"  {sym:<6s} unavailable")
            continue
        bars = to_4h(h)
        ks = sorted(bars)
        with f.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["ts", "datetime", "open", "high", "low", "close", "volume"])
            for k in ks:
                b = bars[k]
                w.writerow([k,
                            datetime.fromtimestamp(k, tz=timezone.utc).isoformat(),
                            b["open"], b["high"], b["low"], b["close"], b["volume"]])
        span = (ks[-1] - ks[0]) / 86400 / 365.25
        meta[sym] = {"bars": len(ks), "years": round(span, 2),
                     "first": datetime.fromtimestamp(ks[0], tz=timezone.utc).isoformat(),
                     "last": datetime.fromtimestamp(ks[-1], tz=timezone.utc).isoformat()}
        print(f"  {sym:<6s} {len(ks):>6d} 4H bars  {span:.2f}y  "
              f"({time.time() - t0:.0f}s)")

    (OUT_DIR / "meta.json").write_text(json.dumps(
        {"source": "Coinbase Exchange 1h candles resampled to 4h",
         "bar_convention": "stamped at OPEN time, aggregates [t, t+4h)",
         "min_hours_per_bar": 3,
         "fetched": datetime.now(timezone.utc).isoformat(),
         "symbols": meta}, indent=2))
    print(f"\nsaved to Data/h4/")


if __name__ == "__main__":
    main()
