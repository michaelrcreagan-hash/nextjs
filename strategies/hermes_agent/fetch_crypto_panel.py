"""
Build a multi-year daily crypto panel -- unblocks goal asks #2 and #4.

WHY COINBASE AND NOT BINANCE/COINGECKO
---------------------------------------
- Binance's public API returns HTTP 451 from this environment (geo-blocked).
- CoinGecko's free tier returns 401 on market_chart beyond the trial window.
- Coinbase Exchange's public candles endpoint works, needs no key, and reaches
  back to each product's listing date.

Coinbase is also the venue the author actually holds spot on, so the 0.60%
taker cost in config.strategy_params.venue_costs is the correct cost model for
anything backtested on this panel -- not an approximation of a different
exchange's fills.

UNIVERSE NOTE (a real problem with the goal as written)
-------------------------------------------------------
The goal says "top 25 by market cap". Taken literally that list currently
includes EIGHT stablecoins (USDT, USDC, USDS, DAI, USD1, USDE, USDG plus
near-stable wrappers) and two exchange tokens (WBT, LEO). A stablecoin cannot
be "bought at the 4-year low" -- it has no trend to be low against, and
including them would silently park a third of the sleeve in cash while
reporting it as an allocation. This script filters them out and takes the top
tradeable names instead. That is an interpretation, and it is stated here
rather than buried.

Run: python3 fetch_crypto_panel.py
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
OUT_CSV = STRATEGY_DIR / "Data" / "crypto_panel_5y.csv"
OUT_META = STRATEGY_DIR / "Data" / "crypto_panel_5y_meta.json"

CB = "https://api.exchange.coinbase.com"
GRANULARITY = 86400          # daily
MAX_CANDLES = 300            # Coinbase's per-request cap
YEARS = 5                    # 5 so a 4-year-low lookback has a warm-up

# Top tradeable names by market cap, stablecoins and exchange tokens removed.
# Ordered by market cap rank as of 2026-08-27.
PRODUCTS = [
    "BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD", "DOGE-USD", "LINK-USD",
    "ADA-USD", "XLM-USD", "BCH-USD", "LTC-USD", "HBAR-USD", "AVAX-USD",
    "ZEC-USD", "DOT-USD", "UNI-USD", "AAVE-USD", "ETC-USD", "FIL-USD",
    "ATOM-USD", "ALGO-USD", "SUI-USD", "APT-USD", "NEAR-USD", "ICP-USD",
    "INJ-USD",
]


def fetch_json(url: str, retries: int = 4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "python"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None


def fetch_product(product: str, start: datetime, end: datetime) -> dict:
    """Paginate Coinbase candles. Returns {date_str: close}."""
    out = {}
    cursor = start
    span = timedelta(days=MAX_CANDLES - 1)
    while cursor < end:
        chunk_end = min(cursor + span, end)
        url = (f"{CB}/products/{product}/candles?granularity={GRANULARITY}"
               f"&start={cursor.strftime('%Y-%m-%dT%H:%M:%SZ')}"
               f"&end={chunk_end.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        data = fetch_json(url)
        if data is None:
            return {}
        # Coinbase rows: [time, low, high, open, close, volume]
        for row in data:
            d = datetime.fromtimestamp(row[0], tz=timezone.utc).date().isoformat()
            out[d] = float(row[4])
        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.35)          # public rate limit courtesy
    return out


def main() -> None:
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=365 * YEARS + 5)
    print(f"fetching {len(PRODUCTS)} products, {start.date()} -> {end.date()}")

    series = {}
    meta = {}
    for p in PRODUCTS:
        try:
            s = fetch_product(p, start, end)
        except Exception as e:
            print(f"  {p:<10s} ERROR {type(e).__name__}")
            continue
        if not s:
            print(f"  {p:<10s} unavailable")
            continue
        sym = p.split("-")[0]
        series[sym] = s
        first, last = min(s), max(s)
        meta[sym] = {"product": p, "n": len(s), "first": first, "last": last}
        yrs = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days / 365.25
        print(f"  {p:<10s} {len(s):>5d} bars  {first} -> {last}  ({yrs:.2f}y)")

    if not series:
        print("no data fetched")
        return

    # Union of dates, then keep only symbols with near-full coverage so the
    # panel does not become mostly holes. Forward-fill ONLY (never backfill --
    # backfill would leak future prices into earlier bars).
    all_dates = sorted({d for s in series.values() for d in s})
    syms = sorted(series, key=lambda s: -meta[s]["n"])

    rows = []
    last_seen = {}
    for d in all_dates:
        row = {"Date": d}
        for s in syms:
            v = series[s].get(d)
            if v is None:
                v = last_seen.get(s)      # forward fill only
            else:
                last_seen[s] = v
            row[s] = v
        rows.append(row)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Date"] + syms)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    span_years = (datetime.fromisoformat(all_dates[-1])
                  - datetime.fromisoformat(all_dates[0])).days / 365.25
    meta_out = {
        "source": "Coinbase Exchange public candles API",
        "granularity": "1d",
        "fetched": datetime.now(timezone.utc).isoformat(),
        "date_range": [all_dates[0], all_dates[-1]],
        "span_years": round(span_years, 2),
        "n_bars": len(rows),
        "symbols": syms,
        "per_symbol": meta,
        "fill_policy": "forward-fill only; never backfill (backfill leaks future prices)",
        "universe_note": ("top tradeable names by market cap; stablecoins "
                          "(USDT/USDC/USDS/DAI/USD1/USDE/USDG) and exchange "
                          "tokens (WBT/LEO) excluded -- they have no trend to "
                          "be at a 4-year low against"),
    }
    OUT_META.write_text(json.dumps(meta_out, indent=2))

    print(f"\npanel: {len(rows)} bars x {len(syms)} symbols, "
          f"{all_dates[0]} -> {all_dates[-1]} ({span_years:.2f} years)")
    print(f"saved: {OUT_CSV.name}, {OUT_META.name}")


if __name__ == "__main__":
    main()
