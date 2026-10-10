#!/usr/bin/env python3
"""Inventory PUBLIC historical research CSVs; never ingest account files.

This is a read-only evidence auditor, not a point-in-time universe builder or
strategy validator. Only the three explicit market-data directories are scanned.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

FAMILIES = (
    {
        "id": "AI_DAILY",
        "rel": "ai-bottleneck-alpha/data/prices",
        "expected": ("date", "open", "high", "low", "close", "adjclose", "volume"),
        "timestamp": "date",
        "status": "CANDIDATE_RECONSTRUCTED_EQUITY_OHLCV",
        "limitation": "Current selected ticker universe; not historical PIT constituents or original vendor price vintage.",
    },
    {
        "id": "CRYPTO_PROP_4H",
        "rel": "crypto-prop-strategies/data/h4",
        "expected": ("ts", "datetime", "open", "high", "low", "close", "volume"),
        "timestamp": "ts",
        "status": "CANDIDATE_RECONSTRUCTED_COINBASE_SPOT_4H",
        "limitation": "Coinbase 1H bars resampled to 4H, at least three hours/bar; not prop intrabar replay.",
    },
    {
        "id": "HEDGEFUND_DAILY",
        "rel": "trading/hedgefund/data_long",
        "expected": ("date", "close", "volume"),
        "timestamp": "date",
        "status": "CANDIDATE_RECONSTRUCTED_DAILY_CLOSE",
        "limitation": "Close/volume-only snapshot; provider vintage, symbol lineage and survivorship unverified.",
    },
)
RELEVANT_CSV = re.compile(r"^[A-Za-z0-9_.-]+\.csv$")
DAY_SECONDS = 24 * 60 * 60
FOUR_HOURS_SECONDS = 4 * 60 * 60


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seconds(row: dict[str, str], mode: str) -> int:
    if mode == "ts":
        parsed = int(row["ts"])
        if abs(parsed) > 100_000_000_000:
            raise ValueError("Expected UNIX seconds, not milliseconds")
        return parsed
    return int(datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def audit_csv(path: Path, family: dict) -> dict:
    outcome: dict = {"name": path.name, "sha256": checksum(path), "rows": 0,
                     "first": None, "last": None, "errors": [], "warnings": []}
    errors: set[str] = set()
    gaps = 0
    previous = None
    expected = set(family["expected"])
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not expected.issubset(set(reader.fieldnames or [])):
                errors.add("MISSING_COLUMNS")
            else:
                for row in reader:
                    outcome["rows"] += 1
                    time = seconds(row, family["timestamp"])
                    if previous is not None:
                        if time <= previous:
                            errors.add("NON_INCREASING_TIMESTAMP")
                        if family["timestamp"] == "ts":
                            delta = time - previous
                            if delta > FOUR_HOURS_SECONDS:
                                gaps += 1
                            if delta % FOUR_HOURS_SECONDS:
                                errors.add("NON_4H_GRID")
                    if family["timestamp"] == "ts" and time % FOUR_HOURS_SECONDS:
                        errors.add("NON_4H_GRID")
                    previous = time
                    if outcome["first"] is None:
                        outcome["first"] = datetime.fromtimestamp(time, tz=timezone.utc).isoformat()
                    outcome["last"] = datetime.fromtimestamp(time, tz=timezone.utc).isoformat()
                    c = float(row["close"])
                    v = float(row["volume"])
                    if not (math.isfinite(c) and c > 0):
                        errors.add("INVALID_CLOSE")
                    if not (math.isfinite(v) and v >= 0):
                        errors.add("INVALID_VOLUME")
                    if "open" in expected:
                        o, h, l = (float(row[k]) for k in ("open", "high", "low"))
                        if not all(math.isfinite(p) and p > 0 for p in (o, h, l)):
                            errors.add("INVALID_OHLC")
                        elif h < max(o, c) - 1e-8 or l > min(o, c) + 1e-8:
                            errors.add("INVALID_OHLC")
                    if family["timestamp"] == "ts":
                        iso = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
                        if iso.tzinfo is None or int(iso.timestamp()) != time:
                            errors.add("TIMESTAMP_ISO_MISMATCH")
    except (UnicodeError, OSError, ValueError, TypeError, OverflowError, KeyError) as exc:
        errors.add("PARSE_ERROR_" + type(exc).__name__)
    if not outcome["rows"]:
        errors.add("EMPTY_CSV")
    if gaps:
        outcome["warnings"].append("MISSING_4H_INTERVALS")
    outcome["missing_4h_intervals"] = gaps
    outcome["errors"] = sorted(errors)
    outcome["evidence_class"] = family["status"]
    outcome["limitations"] = family["limitation"]
    return outcome


def audit_repository(root: Path) -> dict:
    root = root.resolve()
    families = []
    for family in FAMILIES:
        folder = (root / family["rel"]).resolve()
        if not folder.is_relative_to(root):
            raise ValueError("source path escaped repository")
        files = []
        if folder.is_dir():
            for p in sorted(folder.iterdir()):
                if not p.is_file() or p.is_symlink() or not RELEVANT_CSV.fullmatch(p.name):
                    continue
                files.append(audit_csv(p, family))
        families.append({
            "family": family["id"], "source_path": family["rel"], "present": folder.is_dir(),
            "files": files,
            "verified_shape_files": sum(not f["errors"] for f in files),
            "rejected_shape_files": sum(bool(f["errors"]) for f in files),
        })
    futures = root / "strategies/hermes_agent/Data/futures"
    return {
        "schema_version": "nextjs-research-inventory/v1",
        "source_repo": "michaelrcreagan-hash/nextjs",
        "source_commit": "SUPPLY_COMMIT_SHA_IN_HANDOFF",
        "raw_data_attestation": "LOCAL_FILE_SHA256_AND_SHAPE_ONLY",
        "historical_membership_point_in_time": False,
        "research_strategy_certification": False,
        "account_data_scanned": False,
        "families": families,
        "futures": {
            "metadata_path": "strategies/hermes_agent/Data/futures/meta_1h.json",
            "actual_local_csv_count": len(list(futures.glob("*.csv"))) if futures.is_dir() else 0,
            "classification": "METADATA_ONLY_UNLESS_CSV_FILES_EXIST_AND_ARE_VERIFIED",
            "warning": "GitHub repo ignores local futures CSV files; do not infer their presence from metadata.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Optional write-once manifest destination")
    parser.add_argument("--strict", action="store_true", help="Nonzero exit on invalid historical market-data CSVs")
    args = parser.parse_args()
    manifest = audit_repository(args.root)
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            f.write(encoded)
    else:
        print(encoded, end="")
    return 1 if args.strict and any(f["rejected_shape_files"] for f in manifest["families"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
