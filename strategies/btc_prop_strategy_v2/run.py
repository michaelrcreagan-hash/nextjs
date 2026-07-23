"""Baseline backtest + grid-search optimizer for btc_prop_strategy_v2.

Usage:
    python3 run.py baseline    # single run with config.yaml params
    python3 run.py optimize    # grid search + walk-forward + overfit checks
"""
import itertools
import json
import sys

import pandas as pd
import yaml

from src.backtester import run_backtest, walk_forward_windows
from src.risk import RiskConfig


def load():
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    df = pd.read_csv("Data/btc_ohlcv_1d.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    sp = cfg["strategy_params"]
    rmc = sp["risk_manager"]
    risk_cfg = RiskConfig(
        max_daily_loss_pct=rmc["max_daily_loss_percent"],
        max_total_dd_pct=rmc["max_total_drawdown_percent"],
        risk_per_trade_pct=rmc["max_risk_per_trade_percent"],
        max_trades_per_day=rmc["max_trades_per_day"],
        max_positions=cfg["sizing"]["max_positions"],
        max_leverage=cfg["leverage"]["max"],
    )
    return cfg, df, sp, risk_cfg


def print_result(tag, r):
    print(f"{tag}: sharpe={r['sharpe']} return={r['total_return_pct']}% "
          f"maxDD={r['max_dd_pct']}% winrate={r['win_rate_pct']}% "
          f"trades={r['trades']} PF={r['profit_factor']} halted={r['halted']}")
    if r["breaches"]:
        print(f"  breaches: {r['breaches']}")


def cmd_baseline():
    cfg, df, sp, risk_cfg = load()
    r = run_backtest(df, sp, cfg["fees"], risk_cfg, cfg["account"]["initial_capital"])
    print_result("BASELINE (full history 2018-2026)", r)
    tdf = pd.DataFrame(r["trade_list"])
    if not tdf.empty:
        print("\nPer sub-strategy:")
        for strat, g in tdf.groupby("strat"):
            print(f"  {strat}: {len(g)} trades, winrate {(g['pnl'] > 0).mean() * 100:.1f}%, "
                  f"net pnl ${g['pnl'].sum():,.0f}")
    r["equity"].to_csv("experiments/baseline_equity.csv", index=False)
    summary = {k: v for k, v in r.items() if k not in ("trade_list", "equity")}
    with open("experiments/baseline.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return r


def cmd_optimize():
    cfg, df, sp, risk_cfg = load()
    fees, cap = cfg["fees"], cfg["account"]["initial_capital"]

    grid = {
        "adx_threshold": [20, 25, 30],
        "rsi_oversold": [5, 10, 15],
        "trail_mult": [1.5, 2.0, 2.5],
    }
    combos = list(itertools.product(*grid.values()))
    print(f"Grid: {len(combos)} configs x 5 walk-forward windows")

    results = []
    for adx_t, rsi_o, trail in combos:
        is_metrics, oos_metrics = [], []
        for train, test in walk_forward_windows(df, n_windows=5):
            r_is = run_backtest(train, sp, fees, risk_cfg, cap,
                                adx_threshold=adx_t, rsi_oversold=rsi_o, trail_mult=trail)
            r_oos = run_backtest(test, sp, fees, risk_cfg, cap,
                                 adx_threshold=adx_t, rsi_oversold=rsi_o, trail_mult=trail)
            is_metrics.append(r_is)
            oos_metrics.append(r_oos)
        full = run_backtest(df, sp, fees, risk_cfg, cap,
                            adx_threshold=adx_t, rsi_oversold=rsi_o, trail_mult=trail)
        results.append({
            "adx_threshold": adx_t, "rsi_oversold": rsi_o, "trail_mult": trail,
            "is_sharpe_avg": round(sum(m["sharpe"] for m in is_metrics) / 5, 3),
            "oos_sharpe_avg": round(sum(m["sharpe"] for m in oos_metrics) / 5, 3),
            "oos_trades_total": sum(m["trades"] for m in oos_metrics),
            "full_sharpe": full["sharpe"], "full_return_pct": full["total_return_pct"],
            "full_max_dd_pct": full["max_dd_pct"], "full_win_rate_pct": full["win_rate_pct"],
            "full_trades": full["trades"], "full_pf": full["profit_factor"],
            "halted": full["halted"],
        })
        print(f"  adx={adx_t} rsi={rsi_o} trail={trail}: "
              f"IS={results[-1]['is_sharpe_avg']} OOS={results[-1]['oos_sharpe_avg']} "
              f"full={full['sharpe']} trades={full['trades']}")

    rdf = pd.DataFrame(results).sort_values("oos_sharpe_avg", ascending=False)
    rdf.to_csv("experiments/optimize_grid.csv", index=False)
    print("\nTop 5 by OOS sharpe:")
    print(rdf.head(5).to_string(index=False))
    return rdf


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if mode == "baseline":
        cmd_baseline()
    elif mode == "optimize":
        cmd_optimize()
