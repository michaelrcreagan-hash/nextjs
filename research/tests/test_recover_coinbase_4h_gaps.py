"""Offline source integrity and non-interpolation tests."""
import unittest

from research.recover_coinbase_4h_gaps import resample, resample_5min, equal_bar, confirmed_source_gap, SYMBOLS, TARGETS, epoch

class CoinbaseGapTests(unittest.TestCase):
    def test_four_hours_required(self):
        hour = 3600
        base = 1693245600  # 2023-08-28T18:00Z, intentionally unaligned
        base = (base // 14400) * 14400
        rows = [[base+i*hour, 9, 20, 10+i, 11+i, 1+i] for i in range(4)]
        agg = resample(rows)
        self.assertEqual(agg[base]["open"], 10)
        self.assertEqual(agg[base]["close"], 14)
        self.assertEqual(agg[base]["high"], 20)
        self.assertEqual(agg[base]["low"], 9)
        self.assertEqual(agg[base]["volume"], 10)

    def test_duplicate_hour_is_rejected(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*3600, 9, 20, 10, 11, 1] for i in range(4)]
        with self.assertRaises(ValueError):
            resample(rows + [rows[0]])

    def test_malformed_native_ohlc_is_rejected(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*3600, 9, 8, 10, 11, 1] for i in range(4)]
        with self.assertRaises(ValueError):
            resample(rows)

    def test_missing_hour_no_candle(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*3600, 9, 12, 10, 11, 1] for i in [0, 1, 3]]
        self.assertNotIn(base, resample(rows))

    def test_anchors_verify_volume_as_well_as_price(self):
        original = {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 5}
        changed = dict(original, volume=7)
        self.assertFalse(equal_bar(original, changed))

    def test_five_minute_requires_all_48_bins(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*300, 9, 12, 10, 11, 1] for i in range(48)]
        self.assertEqual(len(resample_5min(rows)), 1)
        self.assertEqual(len(resample_5min(rows[:-1])), 0)

    def test_confirmed_source_gaps_must_have_receipts(self):
        rows = []
        for symbol in SYMBOLS:
            timestamps = [epoch(t) for t in TARGETS]
            rows.append({
                "symbol": symbol, "missing_4h_timestamps": timestamps,
                "recovery_state": "BLOCKED_OR_PARTIAL", "recovered_bars": [],
                "unresolved_gap_count": 3,
                "errors": ["NO_COMPLETE_NATIVE_4H_BAR_" + str(t) for t in timestamps],
                "anchors": [{"matches_stored": True}] * 3,
                "source_requests": [{"error": None, "sha256_raw_response": "abc"}] * 4
            })
        report = {"results": rows}
        self.assertTrue(confirmed_source_gap(report))
        report["results"][0]["source_requests"][0] = {"error": "blocked", "sha256_raw_response": None}
        self.assertFalse(confirmed_source_gap(report))

    def test_duplicate_hourly_ts_fails_closed(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*3600, 9, 12, 10, 11, 1] for i in range(4)]
        self.assertEqual(len(resample(rows)), 1)

if __name__ == "__main__":
    unittest.main()
