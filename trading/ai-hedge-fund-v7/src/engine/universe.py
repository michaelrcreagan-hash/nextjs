"""
AI Bottleneck Stock Universe
66 tickers across 10 layers with 4-tier conviction system.
"""
from typing import Dict, List

# Tier 1: Highest Conviction — Direct AI infrastructure
tier1 = ["NVDA", "AVGO", "ASML", "AMAT", "KLAC", "LRCX"]

# Tier 2: Strong — Critical enablers
tier2 = ["TSM", "SNPS", "CDNS", "MRVL", "MPWR", "ONTO", "UCTT", "TER"]

# Tier 3: Moderate — Growth & momentum
tier3 = ["NBIS", "GEV", "DDOG", "PANW", "AXON", "RBRK", "SMCI", "CRWD"]

# Tier 4: Speculative — Higher risk/reward
tier4 = ["OKLO", "BWXT", "CCJ", "LEU", "HOOD", "CIFR", "WULF", "IREN",
         "MSTR", "AIPO", "MAGS", "GRID"]

# Full universe
FULL_UNIVERSE = tier1 + tier2 + tier3 + tier4

# 10 AI Infrastructure Layers
AI_LAYERS = {
    "compute":       ["NVDA", "AVGO", "MRVL", "MPWR"],
    "equipment":     ["AMAT", "LRCX", "KLAC", "ONTO", "UCTT", "COHU", "CGNX", "ICHR"],
    "fabrication":   ["TSM", "ASML", "INTC"],
    "eda":           ["SNPS", "CDNS"],
    "memory":        ["NBIS", "MXL"],
    "cybersecurity": ["PANW", "CRWD", "DDOG", "TENB"],
    "software":      ["AXON", "RBRK", "SN", "DDOG"],
    "energy":        ["GEV", "OKLO", "BWXT", "CCJ", "LEU"],
    "crypto":        ["MSTR", "HOOD", "CIFR", "WULF", "IREN"],
    "etf":           ["SMH", "SOXL", "XLU", "XLV", "XLI", "XBI", "QQQ",
                      "XLK", "PAVE", "ICLN", "WGMI", "AIPO", "MAGS", "GRID"],
}

# Sector ETF mapping for breadth comparison
SECTOR_ETF_MAP = {
    "NVDA": "SMH", "AVGO": "SMH", "MRVL": "SMH", "MPWR": "SMH",
    "AMAT": "SMH", "LRCX": "SMH", "KLAC": "SMH", "ONTO": "SMH",
    "TSM": "SMH", "ASML": "SMH",
    "SNPS": "XLK", "CDNS": "XLK",
    "PANW": "XLK", "CRWD": "XLK", "DDOG": "XLK",
    "AXON": "XLI", "GEV": "XLI",
    "OKLO": "XLU", "BWXT": "XLU", "CCJ": "XLU", "LEU": "XLU",
    "MSTR": "WGMI", "HOOD": "XLK",
}

# 4-Sleeve Portfolio Mapping
SLEEVE_MAP = {
    "macro":      ["SMH", "SOXL", "XLU", "XLV", "XLI", "XLK", "PAVE", "QQQ"],
    "income":     ["TLT", "GLD", "XLU", "VIXY", "SQQQ"],
    "innovation": ["NVDA", "AVGO", "ASML", "AMAT", "KLAC", "TSM", "SNPS", "CDNS",
                   "MRVL", "NBIS", "ONTO", "GEV", "PANW", "DDOG", "AXON"],
    "options":    ["NVDA", "SMH", "QQQ", "MSTR", "PANW", "CRWD", "OKLO"],
}

def get_peers(ticker: str) -> List[str]:
    """Return peer tickers in the same AI layer."""
    for layer, tickers in AI_LAYERS.items():
        if ticker.upper() in [t.upper() for t in tickers]:
            return [t for t in tickers if t.upper() != ticker.upper()]
    return []

def get_sector_etf(ticker: str) -> str:
    """Return appropriate sector ETF for breadth comparison."""
    return SECTOR_ETF_MAP.get(ticker.upper(), "XLK")

def get_tier(ticker: str) -> int:
    """Return conviction tier (1-4)."""
    t = ticker.upper()
    if t in [x.upper() for x in tier1]: return 1
    if t in [x.upper() for x in tier2]: return 2
    if t in [x.upper() for x in tier3]: return 3
    if t in [x.upper() for x in tier4]: return 4
    return 5  # Unknown

def get_sleeve(ticker: str) -> str:
    """Return which 4-sleeve the ticker belongs to."""
    t = ticker.upper()
    for sleeve, tickers in SLEEVE_MAP.items():
        if t in [x.upper() for x in tickers]:
            return sleeve
    return "unmapped"
