"""Investment universe and bottleneck taxonomy.

Tickers come from the user's Institutional Top-Down System doc, tagged with
the bottleneck category they own so the portfolio can enforce per-category
concentration caps (three cooling names is one bet, not three).
"""

# category -> tickers. A ticker may appear in exactly one category (its
# primary bottleneck) so category exposure sums cleanly.
BOTTLENECK_CATEGORIES: dict[str, list[str]] = {
    "compute": ["NVDA", "AMD", "AVGO", "MRVL", "ARM"],
    "semicap": ["AMAT", "LRCX", "KLAC", "ASML", "TER"],
    "memory": ["MU", "WDC", "STX"],
    "networking_optical": ["ANET", "CIEN", "LITE", "COHR"],
    "power": ["VRT", "ETN", "PWR", "GEV", "VST", "CEG", "TLN"],
    "nuclear": ["OKLO", "SMR", "CCJ"],
    "server_oem": ["SMCI", "DELL", "CLS"],
    "ai_software": ["PLTR", "DDOG", "CRWD", "SNOW", "MSFT", "NOW"],
    "dc_reit": ["DLR", "EQIX"],
}

UNIVERSE: list[str] = [t for ts in BOTTLENECK_CATEGORIES.values() for t in ts]

CATEGORY_OF: dict[str, str] = {
    t: cat for cat, ts in BOTTLENECK_CATEGORIES.items() for t in ts
}

# Benchmarks / regime inputs. VIX is stored under this alias in the cache.
BENCHMARKS: list[str] = ["SMH", "SPY", "QQQ", "BTCUSD", "VIX"]

ALL_SYMBOLS: list[str] = UNIVERSE + BENCHMARKS
