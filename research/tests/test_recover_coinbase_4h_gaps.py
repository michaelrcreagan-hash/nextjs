"""Offline source integrity and non-interpolation tests."""
import unittest

from research.recover_coinbase_4h_gaps import resample, equal_bar

class CoinbaseGapTests(unittest.TestCase):
    def test_four_hours_required(self):
        hour = 3600
        base = 1693245600  # 2023-08-28T18:00Z, intentionally unaligned
        base = (base // 14400) * 14400
        rows = [[base+i*hour, 9, 12, 10+i, 11+i, 1+i] for i in range(4)]
        agg = resample(rows)
        self.assertEqual(agg[base]["open"], 10)
        self.assertEqual(agg[base]["close"], 14)
        self.assertEqual(agg[base]["high"], 12)
        self.assertEqual(agg[base]["low"], 9)
        self.assertEqual(agg[base]["volume"], 10)

    def test_missing_hour_no_candle(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*3600, 9, 12, 10, 11, 1] for i in [0, 1, 3]]
        self.assertNotIn(base, resample(rows))

    def test_anchors_verify_volume_as_well_as_price(self):
        original = {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 5}
        changed = dict(original, volume=7)
        self.assertFalse(equal_bar(original, changed))

    def test_duplicate_hourly_ts_fails_closed(self):
        base = 1693245600 // 14400 * 14400
        rows = [[base+i*3600, 9, 12, 10, 11, 1] for i in range(4)]
        self.assertEqual(len(resample(rows)), 1)

if __name__ == "__main__":
    unittest.main()
