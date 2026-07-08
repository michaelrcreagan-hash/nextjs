"""Four-sleeve backtest + Monte Carlo, both eras, with department ablations.

    python -m hedgefund.monte_carlo.sleeve_analysis

Periods:
  P1  2023-01-01 -> 2026-07-08  (current secular Phase-1/2 regime)
  P2  2010-01-04 -> 2022-12-31  (full prior cycle: QE bull, 2018, COVID,
                                 2021 mania, 2022 bear)

Outputs sleeve_backtest_results.json next to this file — the detailed
markdown report is generated from that JSON.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from hedgefund.sleeves import (
    SleeveParams,
    load_long_panel,
    perf_stats,
    run_sleeve_backtest,
)

HERE = os.path.dirname(__file__)
PERIODS = {
    "2023_2026": ("2023-01-03", "2026-07-08"),
    "2010_2023": ("2010-01-04", "2022-12-30"),
}

# department -> SleeveParams override that switches it OFF
ABLATIONS = {
    "macro_regime": {"use_macro_matrix": False},
    "cycle_overlay": {"use_cycle_overlay": False},
    "technical_gate": {"use_trend_gate": False},
    "momentum_selection": {"use_momentum_selection": False},
    "portfolio_stop": {"use_portfolio_stop": False},
    "options_sleeve": {"use_options_sleeve": False},
}


def block_bootstrap_paths(daily_ret: np.ndarray, n_paths: int,
                          horizon: int, block: int = 21,
                          seed: int = 42) -> np.ndarray:
    """Stationary block bootstrap of a daily return series.
    Returns [n_paths, horizon] resampled return paths."""
    rng = np.random.default_rng(seed)
    n = len(daily_ret)
    n_blocks = horizon // block + 1
    starts = rng.integers(0, n - block, size=(n_paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :])
    paths = daily_ret[idx.reshape(n_paths, -1)][:, :horizon]
    return paths


def mc_stats(paths: np.ndarray, years: float) -> dict:
    """Terminal-multiple / CAGR / max-drawdown percentiles over paths."""
    growth = np.cumprod(1.0 + paths, axis=1)
    terminal = growth[:, -1]
    cagr = terminal ** (1.0 / years) - 1.0
    running_max = np.maximum.accumulate(growth, axis=1)
    max_dd = ((growth / running_max) - 1.0).min(axis=1)

    def pct(a, q):
        return round(float(np.percentile(a, q)), 4)

    return {
        "n_paths": int(paths.shape[0]),
        "horizon_days": int(paths.shape[1]),
        "terminal_multiple": {q: pct(terminal, q) for q in (5, 25, 50, 75, 95)},
        "cagr_pct": {q: round(pct(cagr, q) * 100, 1) for q in (5, 25, 50, 75, 95)},
        "max_dd_pct": {q: round(pct(max_dd, q) * 100, 1) for q in (5, 25, 50, 75, 95)},
        "p_loss": round(float((terminal < 1.0).mean()), 4),
        "p_dd_gt_20": round(float((max_dd < -0.20).mean()), 4),
        "p_dd_gt_25": round(float((max_dd < -0.25).mean()), 4),
        "p_dd_gt_40": round(float((max_dd < -0.40).mean()), 4),
    }


def benchmark_stats(panel, start, end) -> dict:
    out = {}
    for sym in ("SPY", "QQQ", "SMH"):
        curve = panel.close[sym].loc[start:end].dropna()
        out[f"{sym}_buy_hold"] = perf_stats(curve)
    # classic 60/40 SPY/TLT, monthly rebalance
    px = panel.close[["SPY", "TLT"]].loc[start:end].dropna()
    ret = px.pct_change().fillna(0.0)
    eq, w_spy, w_tlt = 1.0, 0.6, 0.4
    curve = []
    last_month = None
    for day, r in ret.iterrows():
        eq_spy, eq_tlt = w_spy * (1 + r["SPY"]), w_tlt * (1 + r["TLT"])
        total = eq_spy + eq_tlt
        eq *= total
        w_spy, w_tlt = eq_spy / total, eq_tlt / total
        if last_month is not None and day.month != last_month:
            w_spy, w_tlt = 0.6, 0.4
        last_month = day.month
        curve.append(eq)
    out["60_40_spy_tlt"] = perf_stats(pd.Series(curve, index=ret.index))
    return out


def regime_summary(res) -> dict:
    w = res["weights"]
    states = w["state"].value_counts(normalize=True).round(3).to_dict()
    reb = res["rebalances"]
    return {
        "days": int(len(w)),
        "state_share": states,
        "n_rebalances": int(len(reb)),
        "avg_turnover": round(float(reb["turnover"].mean()), 3),
        "stop_engagements": int(
            (w["stopped"] & ~w["stopped"].shift(1, fill_value=False)).sum()),
        "days_stopped": int(w["stopped"].sum()),
        "avg_cash": round(float(w["cash"].mean()), 3),
        "avg_equity_w": round(float(w["equity_w"].mean()), 3),
    }


def main():
    panel = load_long_panel()
    results = {}

    for pname, (start, end) in PERIODS.items():
        print(f"\n=== {pname}: {start} -> {end} ===", flush=True)
        full = run_sleeve_backtest(panel, start, end, SleeveParams())
        entry = {
            "portfolio": perf_stats(full["curve"]),
            "sleeves": {k: perf_stats(v)
                        for k, v in full["sleeve_curves"].items()},
            "regime": regime_summary(full),
            "benchmarks": benchmark_stats(panel, start, end),
            "ablations": {},
        }
        print("full portfolio:", entry["portfolio"], flush=True)

        # department ablations
        for dept, overrides in ABLATIONS.items():
            p = SleeveParams(**overrides)
            res = run_sleeve_backtest(panel, start, end, p)
            entry["ablations"][dept] = perf_stats(res["curve"])
            print(f"  without {dept}: {entry['ablations'][dept]}", flush=True)

        # sleeve correlation matrix (daily returns, realized)
        sleeve_ret = pd.DataFrame(
            {k: v.pct_change() for k, v in full["sleeve_curves"].items()}
        ).dropna()
        entry["sleeve_correlation"] = sleeve_ret.corr().round(2).to_dict()

        # --- Monte Carlo ---
        port_ret = full["curve"].pct_change().dropna().values
        years = entry["portfolio"]["years"]
        horizon = len(port_ret)
        entry["monte_carlo"] = {
            "portfolio": mc_stats(
                block_bootstrap_paths(port_ret, 10_000, horizon), years),
            "sleeves": {},
        }
        for k in full["sleeve_curves"]:
            r = full["sleeve_curves"][k].pct_change().dropna().values
            entry["monte_carlo"]["sleeves"][k] = mc_stats(
                block_bootstrap_paths(r, 5_000, horizon, seed=7), years)
        print("  MC portfolio:", entry["monte_carlo"]["portfolio"]["cagr_pct"],
              flush=True)

        # empirical sleeve params (for comparison vs the assumed parametric MC)
        ann = {}
        for k in sleeve_ret.columns:
            ann[k] = {
                "mean_pct": round(float(sleeve_ret[k].mean() * 252 * 100), 1),
                "vol_pct": round(float(sleeve_ret[k].std()
                                       * np.sqrt(252) * 100), 1),
            }
        entry["empirical_sleeve_params"] = ann

        results[pname] = entry

    out_path = os.path.join(HERE, "sleeve_backtest_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n[results written to {out_path}]", flush=True)


if __name__ == "__main__":
    main()
