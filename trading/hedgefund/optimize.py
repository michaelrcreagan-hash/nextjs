"""Walk-forward refinement engine (Hermes layer).

Grid search on the train window, ranked by MAR (CAGR / max drawdown) with a
win-rate tiebreak, then re-scored untouched on the validation window. The
train/validation gap is the overfitting readout and gets reported, never
hidden.
"""

from __future__ import annotations

import itertools
from dataclasses import replace

import pandas as pd

from .backtest import StrategyParams, run_backtest
from .data import PricePanel
from .metrics import summarize
from .signals import SignalParams


DEFAULT_GRID: dict[str, list] = {
    "top_n": [5, 8, 12],
    "tier_cutoff": [50.0, 60.0, 70.0],
    "trailing_stop": [0.20, 0.25, 0.30],
    "atr_stop_mult": [2.0, 2.5, 3.0],
    "rsi_hi": [70.0, 80.0],
    "use_regime": [True],
}


def _apply(base: StrategyParams, combo: dict) -> StrategyParams:
    sig_updates = {k: v for k, v in combo.items() if hasattr(SignalParams(), k)}
    strat_updates = {k: v for k, v in combo.items() if k not in sig_updates}
    params = replace(base, **strat_updates)
    if sig_updates:
        params = replace(params, signal=replace(base.signal, **sig_updates))
    return params


def grid_search(
    panel: PricePanel,
    universe: list[str],
    train: tuple[str, str],
    validate: tuple[str, str],
    grid: dict[str, list] | None = None,
    base: StrategyParams | None = None,
    objective: str = "mar",
) -> pd.DataFrame:
    grid = grid or DEFAULT_GRID
    base = base or StrategyParams()
    keys = list(grid)
    rows = []
    for values in itertools.product(*(grid[k] for k in keys)):
        combo = dict(zip(keys, values))
        params = _apply(base, combo)
        tr = run_backtest(panel, universe, params, start=train[0], end=train[1])
        tr_stats = summarize("train", tr.equity, tr.trades)
        va = run_backtest(panel, universe, params, start=validate[0], end=validate[1])
        va_stats = summarize("validate", va.equity, va.trades)
        rows.append(
            {
                **combo,
                "train_cagr": tr_stats["cagr"],
                "train_dd": tr_stats["max_dd"],
                "train_mar": tr_stats["mar"],
                "train_win": tr_stats["win_rate"],
                "val_cagr": va_stats["cagr"],
                "val_dd": va_stats["max_dd"],
                "val_mar": va_stats["mar"],
                "val_win": va_stats["win_rate"],
                "val_sharpe": va_stats["sharpe"],
            }
        )
    df = pd.DataFrame(rows)
    obj_col = f"train_{objective}"
    return df.sort_values([obj_col, "train_win"], ascending=False).reset_index(
        drop=True
    )


def pick_robust(results: pd.DataFrame, top_k: int = 10) -> pd.Series:
    """From the top-k train configs, pick the one with the best validation
    MAR — rewards configs whose edge survives out-of-sample rather than the
    single best in-sample point."""
    head = results.head(top_k)
    return head.sort_values("val_mar", ascending=False).iloc[0]
