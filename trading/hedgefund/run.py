"""CLI for the hedge fund mechanical layer.

Usage (from the ``trading/`` directory):

    python -m hedgefund.run status     # data cache coverage
    python -m hedgefund.run backtest   # strategy vs SMH/BTC baselines
    python -m hedgefund.run optimize   # walk-forward grid search
    python -m hedgefund.run screen     # today's ranked watchlist + regime
"""

from __future__ import annotations

import argparse

import pandas as pd

from .backtest import StrategyParams, run_backtest
from .data import cache_status, load_panel
from .metrics import buy_and_hold, comparison_table, summarize
from .optimize import grid_search, pick_robust
from .universe import ALL_SYMBOLS, UNIVERSE

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def cmd_status(_args):
    print(cache_status(ALL_SYMBOLS).to_string())


def cmd_backtest(args):
    panel = load_panel(ALL_SYMBOLS)
    rows = []

    smh = buy_and_hold(panel.close["SMH"].loc[args.start :])
    rows.append(summarize("SMH buy-and-hold", smh))
    if "BTCUSD" in panel.close.columns:
        btc = buy_and_hold(panel.close["BTCUSD"].loc[args.start :].dropna())
        rows.append(summarize("BTC buy-and-hold", btc))

    no_regime = run_backtest(
        panel,
        UNIVERSE,
        StrategyParams(use_regime=False),
        start=args.start,
        end=args.end,
    )
    rows.append(summarize("momentum (no regime)", no_regime.equity, no_regime.trades))

    full = run_backtest(panel, UNIVERSE, StrategyParams(), start=args.start, end=args.end)
    rows.append(summarize("momentum + regime", full.equity, full.trades))

    print(comparison_table(rows).to_string())
    if args.trades:
        print("\nLast 15 trades (regime-gated strategy):")
        print(full.trades.tail(15).to_string())


def cmd_optimize(args):
    panel = load_panel(ALL_SYMBOLS)
    results = grid_search(
        panel,
        UNIVERSE,
        train=(args.train_start, args.train_end),
        validate=(args.val_start, args.val_end),
    )
    print("Top 10 by train MAR:")
    print(results.head(10).to_string())
    best = pick_robust(results)
    print("\nRobust pick (best validation MAR among top-10 train):")
    print(best.to_string())
    if args.out:
        results.to_csv(args.out, index=False)
        print(f"\nfull grid written to {args.out}")


def cmd_screen(_args):
    from .workflow import screen

    result = screen()
    print(f"As of {result['as_of'].date()}")
    reg = result["regime"]
    print(
        f"Regime: {reg['state']} (score {reg['score']}, "
        f"gross multiplier {reg['multiplier']:.0%}, "
        f"no_new_longs={reg['no_new_longs']})"
    )
    print("\nWatchlist:")
    print(result["watchlist"].to_string())
    if result["asymmetric_setups"]:
        print(f"\nAsymmetric setups: {', '.join(result['asymmetric_setups'])}")


def cmd_daily(args):
    from .daily import run_daily

    run_daily(force_rebalance=args.force_rebalance, deep_dive=args.deep_dive)


def cmd_portfolio(_args):
    from .daily import portfolio_summary

    portfolio_summary()


def cmd_topdown(args):
    from .topdown import run_topdown

    run_topdown(top_setups=args.setups,
                fetch_revisions=not args.no_revisions)


def main():
    ap = argparse.ArgumentParser(prog="hedgefund")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    bt = sub.add_parser("backtest")
    bt.add_argument("--start", default="2019-06-01")
    bt.add_argument("--end", default=None)
    bt.add_argument("--trades", action="store_true")

    opt = sub.add_parser("optimize")
    opt.add_argument("--train-start", default="2019-06-01")
    opt.add_argument("--train-end", default="2022-12-31")
    opt.add_argument("--val-start", default="2023-01-01")
    opt.add_argument("--val-end", default=None)
    opt.add_argument("--out", default=None)

    sub.add_parser("screen")

    dl = sub.add_parser("daily")
    dl.add_argument("--force-rebalance", action="store_true")
    dl.add_argument("--deep-dive", action="store_true")

    sub.add_parser("portfolio")

    td = sub.add_parser("topdown")
    td.add_argument("--setups", type=int, default=5)
    td.add_argument("--no-revisions", action="store_true")

    args = ap.parse_args()
    {
        "status": cmd_status,
        "backtest": cmd_backtest,
        "optimize": cmd_optimize,
        "screen": cmd_screen,
        "daily": cmd_daily,
        "portfolio": cmd_portfolio,
        "topdown": cmd_topdown,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
