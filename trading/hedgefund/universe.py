"""Investment universe and bottleneck taxonomy.

Tickers come from the user's Institutional Top-Down System doc, tagged with
the bottleneck category they own so the portfolio can enforce per-category
concentration caps (three cooling names is one bet, not three).
"""

# category -> tickers. A ticker may appear in exactly one category (its
# primary bottleneck) so category exposure sums cleanly.
#
# This is the WALK-FORWARD VALIDATED universe (see REPORT.md). Do not add
# tickers to BOTTLENECK_CATEGORIES/UNIVERSE directly — that would silently
# change the backtest and invalidate the cited numbers. New names from the
# thematic-engine expansion live in NEW_THEME_CATEGORIES / EXTENDED_UNIVERSE
# below instead, pending their own data pull + validation pass.
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

# ---------------------------------------------------------------------------
# Thematic expansion — "Thematic Multi-Factor Institutional Alpha Engine"
# upgrade. Feeds themes.py's Theme Rotation Engine and the ai_bottleneck_analyst
# LLM agent's broader screen. NOT part of the validated backtest universe:
# these tickers have no price history cached yet (run fetch_data, then a
# fresh walk-forward pass, before trusting any EXTENDED_UNIVERSE backtest).
# ---------------------------------------------------------------------------
NEW_THEME_CATEGORIES: dict[str, list[str]] = {
    "defense_ai": ["RTX", "LMT", "NOC", "BWXT"],
    "healthcare_ai": ["LLY", "UNH", "JNJ"],
    "resources_electrification": ["FCX", "CAT"],
    "crypto_equities": [
        "COIN", "MSTR", "MARA", "RIOT", "CLSK", "HUT", "IREN",
        "HIVE", "CORZ", "CIFR", "BKKT",
    ],
    "financial_infrastructure_rwa": ["ICE", "CME", "BLK", "PYPL", "V", "MA"],
}

EXTENDED_CATEGORY_OF: dict[str, str] = {
    **CATEGORY_OF,
    **{t: cat for cat, ts in NEW_THEME_CATEGORIES.items() for t in ts},
}

EXTENDED_UNIVERSE: list[str] = UNIVERSE + [
    t for ts in NEW_THEME_CATEGORIES.values() for t in ts
]

# AI Layer Cake (Jensen's compute-stack layers). Each name's PRIMARY layer
# only — a company can straddle layers in reality, but a single tag keeps
# layer-level exposure math additive, same convention as CATEGORY_OF.
LAYER_CAKE: dict[str, list[str]] = {
    "Layer1_Compute": ["NVDA", "AMD", "AVGO", "MRVL", "ARM", "MU"],
    "Layer2_Fabrication": ["AMAT", "LRCX", "KLAC", "ASML", "TER"],
    "Layer3_Networking": ["ANET", "CIEN", "LITE", "COHR"],
    "Layer4_Infrastructure": [
        "VRT", "ETN", "PWR", "GEV", "VST", "CEG", "TLN", "OKLO", "SMR",
        "CCJ", "DLR", "EQIX", "SMCI", "DELL", "CLS",
    ],
    "Layer5_Software": ["MSFT", "PLTR", "DDOG", "CRWD", "SNOW", "NOW"],
    # Layer6_Applications (consumer/vertical AI apps) has no current
    # universe member — placeholder for names like UBER/DUOL/APP if added.
    "Layer6_Applications": [],
}

LAYER_OF: dict[str, str] = {
    t: layer for layer, ts in LAYER_CAKE.items() for t in ts
}

# Extra benchmark/proxy ETFs the Theme Rotation Engine needs beyond
# BENCHMARKS (theme-level trend checks in themes.py THEME_MAP).
THEME_BENCHMARKS: list[str] = ["XLU", "XLK", "XLV", "ITA", "COPX"]

EXTENDED_ALL_SYMBOLS: list[str] = (
    EXTENDED_UNIVERSE + BENCHMARKS + THEME_BENCHMARKS
)
