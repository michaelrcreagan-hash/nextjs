"""Offline tests for legacy market-source shape and timestamp validation."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research.audit_legacy_sources import FAMILIES, audit_csv, audit_repository


class LegacySourcesTest(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.ai = self.root / FAMILIES[0]["rel"]
        self.ai.mkdir(parents=True)
        self.p = self.ai / "TEST.csv"

    def write_prices(self, rows):
        with self.p.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def row(self, day="2025-01-02", high="12"):
        return {"date": day, "open": "10", "high": high, "low": "9",
                "close": "11", "adjclose": "10.5", "volume": "100"}

    def test_valid_equity_file(self):
        self.write_prices([self.row(), self.row(day="2025-01-03")])
        result = audit_csv(self.p, FAMILIES[0])
        self.assertEqual(result["rows"], 2)
        self.assertFalse(result["errors"])
        self.assertEqual(result["sha256"], hashlib.sha256(self.p.read_bytes()).hexdigest())
        self.assertEqual(result["first"], "2025-01-02T00:00:00+00:00")

    def test_invalid_ohlc_fails(self):
        self.write_prices([self.row(high="8")])
        self.assertIn("INVALID_OHLC", audit_csv(self.p, FAMILIES[0])["errors"])

    def test_duplicate_date_fails(self):
        self.write_prices([self.row(), self.row()])
        self.assertIn("NON_INCREASING_TIMESTAMP", audit_csv(self.p, FAMILIES[0])["errors"])

    def test_does_not_scan_accounts(self):
        self.write_prices([self.row()])
        secret = self.root / "strategies/hermes_agent/Data/real_accounts/secret.csv"
        secret.parent.mkdir(parents=True)
        secret.write_text("confidential_test_marker\n")
        result = audit_repository(self.root)
        self.assertFalse(result["account_data_scanned"])
        self.assertEqual(len(result["families"][0]["files"]), 1)
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["futures"]["actual_local_csv_count"], 0)

    def test_crypto_resampled_timestamp_mismatch(self):
        p = self.root / FAMILIES[1]["rel"] / "BTC_4h.csv"
        p.parent.mkdir(parents=True)
        p.write_text(
            "ts,datetime,open,high,low,close,volume\n"
            "1693238400,2023-08-28T20:00:00+00:00,10,12,9,11,100\n"
        )
        self.assertIn("TIMESTAMP_ISO_MISMATCH", audit_csv(p, FAMILIES[1])["errors"])


if __name__ == "__main__":
    unittest.main()
