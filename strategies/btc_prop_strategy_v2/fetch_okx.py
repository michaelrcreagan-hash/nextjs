"""Fetch BTC-USDT 4H candles + BTC-USDT-SWAP funding history from OKX public API.

OKX pagination: /market/history-candles returns newest-first, `after` param pages
backward in time (returns records older than the given ts). 100 rows/request.
Rate limit 20 req/2s -- we sleep 0.15s between calls.
"""
import csv
import json
import time
import urllib.request

BASE = "https://www.okx.com"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "cbt-framework"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_candles(inst="BTC-USDT", bar="4H", out="Data/btc_ohlcv_4h_okx.csv"):
    rows, after = [], ""
    for i in range(600):  # safety cap
        path = f"/api/v5/market/history-candles?instId={inst}&bar={bar}&limit=100"
        if after:
            path += f"&after={after}"
        data = get(path)["data"]
        if not data:
            break
        rows.extend(data)
        after = data[-1][0]  # oldest ts in this page
        time.sleep(0.15)
        if i % 25 == 0:
            print(f"  candles page {i}, total {len(rows)}, oldest "
                  f"{time.strftime('%Y-%m-%d', time.gmtime(int(after) / 1000))}")
    rows.sort(key=lambda r: int(r[0]))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "date", "open", "high", "low", "close", "volume"])
        for r in rows:
            ts = int(r[0])
            w.writerow([ts, time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts / 1000)),
                        r[1], r[2], r[3], r[4], r[5]])
    print(f"candles: {len(rows)} rows -> {out}")
    return len(rows)


def fetch_funding(inst="BTC-USDT-SWAP", out="Data/funding_okx.csv"):
    rows, after = [], ""
    for i in range(300):
        path = f"/api/v5/public/funding-rate-history?instId={inst}&limit=100"
        if after:
            path += f"&after={after}"
        data = get(path)["data"]
        if not data:
            break
        rows.extend(data)
        after = data[-1]["fundingTime"]
        time.sleep(0.15)
        if i % 25 == 0:
            print(f"  funding page {i}, total {len(rows)}, oldest "
                  f"{time.strftime('%Y-%m-%d', time.gmtime(int(after) / 1000))}")
    rows.sort(key=lambda r: int(r["fundingTime"]))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "date", "funding_rate"])
        for r in rows:
            ts = int(r["fundingTime"])
            w.writerow([ts, time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts / 1000)),
                        r["realizedRate"]])
    print(f"funding: {len(rows)} rows -> {out}")
    return len(rows)


if __name__ == "__main__":
    n_c = fetch_candles()
    n_f = fetch_funding()
    print(f"DONE candles={n_c} funding={n_f}")
