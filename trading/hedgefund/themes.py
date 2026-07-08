"""Theme Rotation Engine — the top-level allocator.

Per the "Institutional Theme Rotation Engine" strategy note: instead of
asking "which stock should I buy?", first ask "which secular themes are
attracting capital right now?" — then select the strongest names *within*
the leading themes. This module scores every theme 0-100 and gates stock
selection: a name below its theme's leadership gate doesn't advance to
the security-selection layer regardless of its own score.

Score components (weights from the note):
    Relative Strength ..... 40%  (vs SPY/QQQ and its benchmark ETF,
                                   4/12/26/52-week momentum blended
                                   40/30/20/10)
    Breadth/Leadership ..... 30%  (% of theme constituents above 50DMA
                                   and 200DMA — the "leadership gate")
    Trend quality .......... 30%  (theme ETF/proxy above its own 200DMA
                                   and 50>200, as a regime-within-theme
                                   check)

The note's fuller formula also weighs analyst revisions, earnings
momentum, institutional buying, and options flow — those need data
this mechanical layer doesn't have (13F, dark pool, sweeps). They're
left as explicit gaps and instead surfaced as LLM-agent inputs (see
ai_bottleneck_analyst.py), which can pull them live via tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import PricePanel
from .indicators import sma

# theme -> (benchmark proxy ticker, constituent tickers). The proxy is
# used for the theme-level trend check; constituents drive breadth and
# are the pool ranked for stock selection within the theme.
THEME_MAP: dict[str, dict] = {
    "ai_compute": {
        "proxy": "SMH",
        "tickers": ["NVDA", "AMD", "AVGO", "MRVL", "ARM"],
    },
    "semi_equipment": {
        "proxy": "SMH",
        "tickers": ["AMAT", "LRCX", "KLAC", "ASML", "TER"],
    },
    "hbm_memory": {
        "proxy": "SMH",
        "tickers": ["MU", "WDC", "STX"],
    },
    "ai_networking_optical": {
        "proxy": "SMH",
        "tickers": ["ANET", "CIEN", "LITE", "COHR"],
    },
    "power_infrastructure": {
        "proxy": "XLU",
        "tickers": ["VRT", "ETN", "PWR", "GEV", "VST", "CEG", "TLN"],
    },
    "nuclear": {
        "proxy": "XLU",
        "tickers": ["OKLO", "SMR", "CCJ"],
    },
    "data_centers": {
        "proxy": "SMH",
        "tickers": ["DLR", "EQIX", "SMCI", "DELL", "CLS"],
    },
    "enterprise_ai_software": {
        "proxy": "XLK",
        "tickers": ["PLTR", "DDOG", "CRWD", "SNOW", "MSFT", "NOW"],
    },
    "defense_ai": {
        "proxy": "ITA",
        "tickers": ["RTX", "LMT", "NOC", "BWXT"],
    },
    "resources_electrification": {
        "proxy": "COPX",
        "tickers": ["FCX", "CAT"],
    },
    "healthcare_ai": {
        "proxy": "XLV",
        "tickers": ["LLY", "UNH", "JNJ"],
    },
    "digital_assets_tokenization": {
        "proxy": "BTCUSD",
        "tickers": ["COIN", "MSTR", "MARA", "RIOT", "CLSK", "HUT", "IREN",
                     "HIVE", "CORZ", "CIFR", "BKKT"],
    },
    "financial_infrastructure_rwa": {
        "proxy": "SPY",
        "tickers": ["ICE", "CME", "BLK", "PYPL", "V", "MA"],
    },
}


@dataclass
class ThemeParams:
    mom_weights: tuple = (0.40, 0.30, 0.20, 0.10)  # 4w, 12w, 26w, 52w
    mom_windows: tuple = (20, 63, 130, 252)         # trading days
    breadth_50_gate: float = 0.60
    breadth_200_gate: float = 0.70
    w_relative_strength: float = 0.40
    w_breadth: float = 0.30
    w_trend: float = 0.30
    increase_threshold: float = 90.0
    maintain_threshold: float = 80.0
    watch_threshold: float = 70.0


def _momentum_blend(close: pd.Series | pd.DataFrame, p: ThemeParams) -> pd.Series | pd.DataFrame:
    """Weighted 4/12/26/52-week momentum. Works on a Series (single
    benchmark) or a DataFrame (multiple theme members) — output shape
    matches input shape."""
    out = close * 0.0
    for w, window in zip(p.mom_weights, p.mom_windows):
        ret = close / close.shift(window) - 1
        out = out + w * ret.fillna(0.0)
    return out


def compute_theme_scores(
    panel: PricePanel,
    params: ThemeParams | None = None,
    theme_map: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Daily theme score table: one row per date, one column per theme."""
    p = params or ThemeParams()
    tm = theme_map or THEME_MAP
    close = panel.close
    spy = close.get("SPY")
    qqq = close.get("QQQ")

    scores: dict[str, pd.Series] = {}
    for theme, cfg in tm.items():
        proxy = cfg["proxy"]
        members = [t for t in cfg["tickers"] if t in close.columns]
        if not members:
            continue
        member_close = close[members]
        # Graceful degradation: if the named proxy ETF hasn't been fetched
        # yet, use the member-average close as its own trend-quality proxy
        # rather than dropping the whole theme (fetch_data + universe.py's
        # THEME_BENCHMARKS list has the real ETFs when available).
        proxy_close = close[proxy] if proxy in close.columns else member_close.mean(axis=1)

        # --- relative strength: theme member momentum blend, relative
        # to SPY/QQQ momentum blend, ranked into a 0-100 band ---
        mom_members = _momentum_blend(member_close, p).mean(axis=1)
        mom_bench = _momentum_blend(
            pd.concat([spy, qqq], axis=1).mean(axis=1), p
        )
        rel_strength = (mom_members - mom_bench).clip(-0.5, 0.5)
        rs_score = (rel_strength + 0.5) / 1.0 * 100  # map [-50%,+50%]->0-100

        # --- breadth / leadership gate ---
        ma50 = sma(member_close, 50)
        ma200 = sma(member_close, 200)
        above_50 = (member_close > ma50).sum(axis=1) / len(members)
        above_200 = (member_close > ma200).sum(axis=1) / len(members)
        leadership_ok = (above_50 > p.breadth_50_gate) & (
            above_200 > p.breadth_200_gate
        )
        breadth_raw = (above_50 + above_200) / 2 * 100
        breadth_score = breadth_raw.where(leadership_ok, breadth_raw * 0.5)

        # --- theme-level trend quality (proxy ETF/asset, or member-average
        # fallback — see graceful-degradation note above) ---
        proxy_ma50 = sma(proxy_close, 50)
        proxy_ma200 = sma(proxy_close, 200)
        trend_ok = (proxy_close > proxy_ma200) & (proxy_ma50 > proxy_ma200)
        trend_score = trend_ok.astype(float) * 100

        score = (
            p.w_relative_strength * rs_score
            + p.w_breadth * breadth_score
            + p.w_trend * trend_score
        )
        scores[theme] = score.clip(0, 100)

    return pd.DataFrame(scores)


def theme_action(score: float, p: ThemeParams | None = None) -> str:
    p = p or ThemeParams()
    if np.isnan(score):
        return "n/a"
    if score >= p.increase_threshold:
        return "INCREASE"
    if score >= p.maintain_threshold:
        return "MAINTAIN"
    if score >= p.watch_threshold:
        return "WATCH"
    return "REDUCE"


def theme_leaders(
    panel: PricePanel,
    theme: str,
    day,
    top_n: int = 3,
    theme_map: dict[str, dict] | None = None,
) -> list[str]:
    """Top-N members of a theme by trailing 3-month return, as of ``day``."""
    tm = theme_map or THEME_MAP
    cfg = tm.get(theme)
    if not cfg:
        return []
    members = [t for t in cfg["tickers"] if t in panel.close.columns]
    if not members:
        return []
    close = panel.close[members]
    ret = (close.loc[day] / close.loc[:day].iloc[-63] - 1).sort_values(
        ascending=False
    )
    return ret.head(top_n).index.tolist()


def latest_theme_ranking(
    panel: PricePanel,
    params: ThemeParams | None = None,
    theme_map: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Convenience: today's theme ranking table for reports/dashboard."""
    scores = compute_theme_scores(panel, params, theme_map)
    day = scores.dropna(how="all").index[-1]
    row = scores.loc[day].dropna().sort_values(ascending=False)
    p = params or ThemeParams()
    return pd.DataFrame(
        {
            "score": row.round(1),
            "action": [theme_action(s, p) for s in row],
        }
    )
