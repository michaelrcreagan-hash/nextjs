#!/usr/bin/env python3
"""Read-only retrieval of missing Coinbase-derived 4-hour observations.

Never synthesize OHLCV; store raw 1-hour candle provenance. Source is Coinbase
Exchange public REST (BTC-USD etc). No account credentials or write endpoints.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

SYMBOLS = ("AVAX", "BTC", "DOGE", "ETH", "LINK", "LTC", "SOL", "XRP")
TARGETS = ("2025-10-25T16:00:00+00:00", "2026-05-08T00:00:00+00:00", "2026-05-08T04:00:00+00:00")
WINDOWS = (("2025-10-25T12:00:00+00:00", "2025-10-26T00:00:00+00:00"),
           ("2026-05-07T20:00:00+00:00", "2026-05-08T12:00:00+00:00"))
BAR_SEC = 14400


def epoch(stamp: str) -> int:
    return int(dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())


def source_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return {int(row["ts"]): row for row in csv.DictReader(f)}


def resample(hourly):
    """Aggregate exactly 4 consecutive source H1 bars; reject incomplete bars."""
    hourly_by_ts = {int(row[0]): row for row in hourly}
    result = {}
    for bar in sorted({ts // BAR_SEC * BAR_SEC for ts in hourly_by_ts}):
        stamps = [bar + i * 3600 for i in range(4)]
        if any(s not in hourly_by_ts for s in stamps):
            continue
        h = [hourly_by_ts[s] for s in stamps]
        # Coinbase raw: [epoch, low, high, open, close, base_volume]
        values = {"ts": bar, "open": float(h[0][3]), "high": max(float(x[2]) for x in h),
                  "low": min(float(x[1]) for x in h), "close": float(h[-1][4]),
                  "volume": sum(float(x[5]) for x in h), "hours": stamps}
        if not all(math.isfinite(values[k]) and values[k] > 0 for k in ("open","high","low","close")):
            continue
        if not math.isfinite(values["volume"]) or values["volume"] <= 0:
            continue
        result[bar] = values
    return result


def resample_5min(five_minute):
    """Only reconstruct a 4H candle if ALL 48 exchange 5m bins are present."""
    by_time = {int(x[0]): x for x in five_minute}
    result = {}
    for bar in sorted({ts // BAR_SEC * BAR_SEC for ts in by_time}):
        stamps = [bar + i * 300 for i in range(48)]
        if any(t not in by_time for t in stamps):
            continue
        h = [by_time[t] for t in stamps]
        result[bar] = {"ts": bar, "open": float(h[0][3]),
                       "high": max(float(x[2]) for x in h),
                       "low": min(float(x[1]) for x in h),
                       "close": float(h[-1][4]),
                       "volume": sum(float(x[5]) for x in h),
                       "source_resolution_seconds": 300, "hours": stamps}
    return result


def fetch_hourly(symbol: str, start: str, end: str, granularity=3600):
    params = urllib.parse.urlencode({"granularity": granularity, "start": start, "end": end})
    url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles?{params}"
    errors = []
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json", "User-Agent": "HermesResearchSourceAudit/1.0"
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read()
                payload = json.loads(raw)
                if not isinstance(payload, list):
                    raise ValueError("Non-list Coinbase response")
                if any(not isinstance(x, list) or len(x) < 6 for x in payload):
                    raise ValueError("Malformed Coinbase hourly candle")
                return payload, hashlib.sha256(raw).hexdigest(), None
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as e:
            errors.append(type(e).__name__ + ": " + str(e)[:160])
            if attempt < 2:
                time.sleep(1 + attempt)
    return [], None, "; ".join(errors)


def equal_bar(a: dict, b: dict, rel=3e-5):
    return all(
        math.isclose(float(a[k]), float(b[k]), rel_tol=rel, abs_tol=1e-10)
        for k in ("open", "high", "low", "close", "volume")
    )


def recover(root: Path, use_network: bool):
    recorded = []
    gap_times = [epoch(s) for s in TARGETS]
    for symbol in SYMBOLS:
        historical = source_csv(root / "crypto-prop-strategies/data/h4" / f"{symbol}_4h.csv")
        missing = sorted(t for t in gap_times if t not in historical)
        source_receipts, known_bars, recovered, conflicts = [], {}, [], []
        for start, end in WINDOWS:
            if not use_network:
                raise ValueError("Retrieval requires --network; never synthesize missing source bars")
            series, raw_sha, error = fetch_hourly(symbol, start, end)
            source_receipts.append({"start": start, "end": end, "sha256_raw_response": raw_sha,
                                    "hourly_records": len(series), "error": error,
                                    "endpoint": f"coinbase_exchange_public_{symbol}_USD_3600"})
            if error:
                conflicts.append("FETCH_FAILED_" + start)
                continue
            fine, fine_sha, fine_error = fetch_hourly(symbol, start, end, 300)
            source_receipts.append({"start": start, "end": end, "sha256_raw_response": fine_sha,
                                    "native_five_minute_records": len(fine), "error": fine_error,
                                    "endpoint": f"coinbase_exchange_public_{symbol}_USD_300"})
            if fine_error:
                conflicts.append("5MIN_FETCH_FAILED_" + start)
            for k, row in resample_5min(fine).items():
                if k in known_bars and not equal_bar(known_bars[k], row):
                    conflicts.append("FIVE_MINUTE_HOURLY_MISMATCH_" + str(k))
                else:
                    known_bars[k] = row
            for k, row in resample(series).items():
                if k in known_bars and not equal_bar(known_bars[k], row):
                    conflicts.append("SOURCE_DUPLICATE_CONFLICT_" + str(k))
                known_bars[k] = row
        for t in missing:
            bar = known_bars.get(t)
            if bar is None:
                conflicts.append("NO_COMPLETE_NATIVE_4H_BAR_" + str(t))
            else:
                recovered.append(bar)
        anchors = []
        for t in missing:
            for adjacent in (t - BAR_SEC, t + BAR_SEC):
                if adjacent in historical and adjacent in known_bars:
                    anchors.append({"ts": adjacent, "matches_stored": equal_bar(historical[adjacent], known_bars[adjacent])})
        if not anchors or not all(a["matches_stored"] for a in anchors):
            conflicts.append("ADJACENT_SOURCE_RECONCILIATION_FAILED")
        current = set(historical)
        combined = sorted(current.union(b["ts"] for b in recovered))
        gap_count = sum((n - p) // BAR_SEC - 1 for p, n in zip(combined, combined[1:]) if n - p > BAR_SEC)
        recorded.append({"symbol": symbol, "original_rows": len(historical),
                         "missing_4h_timestamps": missing,
                         "recovered_bars": recovered,
                         "unresolved_gap_count": gap_count,
                         "anchors": anchors, "source_requests": source_receipts,
                         "errors": sorted(set(conflicts)),
                         "recovery_state": "SOURCE_VALIDATED" if len(recovered) == len(missing) and
                                           not conflicts and gap_count == 0 else "BLOCKED_OR_PARTIAL"})
    return {"schema_version": "coinbase-missing-4h/v1", "source_repo": "michaelrcreagan-hash/nextjs",
            "provider": "Coinbase Exchange public historical H1 candles",
            "source_api": "https://api.exchange.coinbase.com/products/{symbol}-USD/candles",
            "observation_class": "RECONSTRUCTED_FROM_NATIVE_H1",
            "not_exchange_trade_tape": True, "not_intrabar_firm_data": True,
            "backfill_does_not_certify_trading_strategy": True,
            "results": recorded, "all_valid": all(r["recovery_state"] == "SOURCE_VALIDATED" for r in recorded)}


def confirmed_source_gap(report):
    """Classification is acceptable only when all native source queries succeeded."""
    if len(report.get("results", [])) != len(SYMBOLS):
        return False
    for entry in report["results"]:
        if len(entry.get("missing_4h_timestamps", [])) != len(TARGETS):
            return False
        if entry["recovery_state"] != "BLOCKED_OR_PARTIAL":
            return False
        if entry.get("recovered_bars") or entry.get("unresolved_gap_count") != len(TARGETS):
            return False
        expected = {"NO_COMPLETE_NATIVE_4H_BAR_" + str(epoch(stamp)) for stamp in TARGETS}
        if set(entry.get("errors", [])) != expected:
            return False
        source = entry.get("source_requests", [])
        if len(source) != 4 or any(q.get("error") or not q.get("sha256_raw_response") for q in source):
            return False
        anchors = entry.get("anchors", [])
        if len(anchors) < 3 or not all(a.get("matches_stored") for a in anchors):
            return False
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--network", action="store_true")
    p.add_argument("--allow-confirmed-source-gap", action="store_true", help="Exit 0 ONLY for independently evidenced absent source bars; does not fill bars")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = recover(args.root, args.network)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    print("summary:", [(r["symbol"], r["recovery_state"], len(r["recovered_bars"]),
                       r["unresolved_gap_count"], r["errors"]) for r in report["results"]])
    if report["all_valid"]:
        return 0
    if args.allow_confirmed_source_gap and confirmed_source_gap(report):
        print("EVIDENCE_STATUS=BLOCKED_UPSTREAM: 24 native Coinbase bars not recoverable; no synthetic values committed")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
