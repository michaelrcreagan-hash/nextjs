"""Charts for the four-sleeve backtest report (one 2x2 panel per period)."""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hedgefund.monte_carlo.sleeve_analysis import (
    PERIODS,
    block_bootstrap_paths,
)
from hedgefund.sleeves import (
    SleeveParams,
    load_long_panel,
    run_sleeve_backtest,
)

HERE = os.path.dirname(__file__)


def main():
    panel = load_long_panel()
    for pname, (start, end) in PERIODS.items():
        res = run_sleeve_backtest(panel, start, end, SleeveParams())
        curve = res["curve"] / res["curve"].iloc[0]
        spy = panel.close["SPY"].loc[start:end]
        spy = spy / spy.iloc[0]
        qqq = panel.close["QQQ"].loc[start:end]
        qqq = qqq / qqq.iloc[0]

        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        fig.suptitle(f"Four-Sleeve Portfolio — {pname.replace('_', ' -> ')}",
                     fontsize=14, fontweight="bold")

        ax = axes[0][0]
        ax.plot(curve.index, curve.values, lw=1.8, color="#2563eb",
                label="4-sleeve portfolio")
        ax.plot(spy.index, spy.values, lw=1.2, color="#6b7280", label="SPY")
        ax.plot(qqq.index, qqq.values, lw=1.2, color="#d97706", label="QQQ")
        ax.set_title("Growth of $1 (regime-weighted, all triggers)")
        ax.legend()
        ax.grid(alpha=0.3)

        ax = axes[0][1]
        dd = curve / curve.cummax() - 1
        sdd = spy / spy.cummax() - 1
        ax.fill_between(dd.index, dd.values * 100, 0, color="#2563eb",
                        alpha=0.6, label="portfolio")
        ax.plot(sdd.index, sdd.values * 100, color="#6b7280", lw=1.0,
                label="SPY")
        ax.set_title("Drawdown (%)")
        ax.legend()
        ax.grid(alpha=0.3)

        ax = axes[1][0]
        colors = {"macro": "#059669", "income": "#7c3aed",
                  "innovation": "#dc2626", "options": "#d97706"}
        for name, c in res["sleeve_curves"].items():
            norm = c / c.iloc[0]
            ax.plot(norm.index, norm.values, lw=1.2,
                    color=colors[name], label=name)
        ax.set_yscale("log")
        ax.set_title("Standalone sleeve curves (log, 100% internal weight)")
        ax.legend()
        ax.grid(alpha=0.3, which="both")

        ax = axes[1][1]
        port_ret = res["curve"].pct_change().dropna().values
        paths = block_bootstrap_paths(port_ret, 400, len(port_ret))
        growth = np.cumprod(1 + paths, axis=1)
        x = np.arange(growth.shape[1])
        for q, c, a in ((5, "#dc2626", 0.9), (25, "#d97706", 0.9),
                        (50, "#2563eb", 1.2), (75, "#d97706", 0.9),
                        (95, "#059669", 0.9)):
            ax.plot(x, np.percentile(growth, q, axis=0), lw=a, color=c,
                    label=f"p{q}")
        for row in growth[:120]:
            ax.plot(x, row, lw=0.3, color="#94a3b8", alpha=0.15)
        ax.set_yscale("log")
        ax.set_title("Monte Carlo fan (block bootstrap, growth of $1)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3, which="both")

        out = os.path.join(HERE, f"sleeve_backtest_{pname}.png")
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print("wrote", out)


if __name__ == "__main__":
    main()
