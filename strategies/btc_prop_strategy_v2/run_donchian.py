"""Donchian 4H strategy: baseline + grid + walk-forward + challenge-pass analysis."""
import itertools
import sys

import pandas as pd

from src.donchian import DonchianParams, run, challenge_pass_analysis
from src.backtester import walk_forward_windows

DF = pd.read_csv("Data/btc_ohlcv_4h_okx.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)


def one(p, df=DF, tag=""):
    r = run(df, p)
    ch = challenge_pass_analysis(r["equity"])
    print(f"{tag}: sharpe={r['sharpe']} CAGR={r['cagr_pct']}% total={r['total_return_pct']}% "
          f"maxDD={r['max_dd_pct']}% WR={r['win_rate_pct']}% trades={r['trades']} PF={r['profit_factor']} "
          f"| challenge: pass={ch['pass_rate_pct']}% breach={ch['breach_rate_pct']}% timeout={ch['timeout_rate_pct']}% ({ch['windows']} windows)")
    return r, ch


def grid():
    rows = []
    for lb, tm, filt in itertools.product([20, 55, 100], [2.5, 3.0, 3.5], [True, False]):
        p = DonchianParams(entry_lookback=lb, trail_atr_mult=tm, daily_filter=filt)
        # walk-forward
        oos_sharpes, is_sharpes, oos_trades = [], [], 0
        for train, test in walk_forward_windows(DF, n_windows=5):
            is_sharpes.append(run(train, p)["sharpe"])
            r_oos = run(test, p)
            oos_sharpes.append(r_oos["sharpe"])
            oos_trades += r_oos["trades"]
        full = run(DF, p)
        ch = challenge_pass_analysis(full["equity"])
        rows.append({
            "lookback": lb, "trail": tm, "filter": filt,
            "is_sharpe": round(sum(is_sharpes) / 5, 3),
            "oos_sharpe": round(sum(oos_sharpes) / 5, 3),
            "oos_trades": oos_trades,
            "full_sharpe": full["sharpe"], "cagr": full["cagr_pct"],
            "max_dd": full["max_dd_pct"], "wr": full["win_rate_pct"],
            "trades": full["trades"], "pf": full["profit_factor"],
            "ch_pass": ch["pass_rate_pct"], "ch_breach": ch["breach_rate_pct"],
        })
        print(f"lb={lb} trail={tm} filt={filt}: IS={rows[-1]['is_sharpe']} OOS={rows[-1]['oos_sharpe']} "
              f"full={full['sharpe']} CAGR={full['cagr_pct']}% pass={ch['pass_rate_pct']}%")
    rdf = pd.DataFrame(rows).sort_values("oos_sharpe", ascending=False)
    rdf.to_csv("experiments/donchian_grid.csv", index=False)
    print("\nTop 6 by OOS sharpe:")
    print(rdf.head(6).to_string(index=False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if mode == "baseline":
        r, ch = one(DonchianParams(), tag="DONCHIAN 4H baseline (lb=55, trail=3.0, filter=on)")
        r["equity"].to_csv("experiments/donchian_baseline_equity.csv", index=False)
    elif mode == "grid":
        grid()
