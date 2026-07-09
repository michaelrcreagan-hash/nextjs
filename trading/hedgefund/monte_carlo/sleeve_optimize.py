"""Per-sleeve grid optimization with an in-sample / out-of-sample split.

    python -m hedgefund.monte_carlo.sleeve_optimize

Goal (from /cbt:optimize): highest return + lowest drawdown per sleeve —
ranked by MAR (CAGR / |maxDD|) on the IN-SAMPLE window, then validated
out-of-sample. Grids come straight from the research priorities in
strategies/four_sleeve_portfolio/RESEARCH.md, kept deliberately small
(41 configs total) to limit the selection-bias engine the deflated-Sharpe
literature warns about.

Windows:
  IS   2010-01-04 -> 2018-12-31  (QE bull, 2011/2015/2018 corrections)
  OOS  2019-01-02 -> 2026-07-08  (COVID crash, 2022 bear, 2023-26 bull)

Standalone sleeve mechanics mirror sleeves.py: monthly rebalance,
position drift in between, 10 bps/side, $5 investability floor,
dividend-adjusted closes.
"""

from __future__ import annotations

import itertools
import json
import os

import numpy as np
import pandas as pd

from hedgefund.options_sim import PMCCParams, run_pmcc
from hedgefund.regime import RegimeParams, compute_regime
from hedgefund.sleeves import (
    BREADTH_UNIVERSE,
    INCOME_MIX,
    INNOVATION_MEMBERS,
    MACRO_MEMBERS,
    load_long_panel,
    perf_stats,
)

HERE = os.path.dirname(__file__)
IS_WIN = ("2010-01-04", "2018-12-31")
OOS_WIN = ("2019-01-02", "2026-07-08")

COST = 10 / 10_000.0
CASH_YIELD = 0.03
MIN_PRICE = 5.0


class Ctx:
    """Shared precomputations."""

    def __init__(self, panel):
        self.close = panel.close
        self.ret = self.close.pct_change()
        sma50 = self.close.rolling(50).mean()
        self.sma200 = self.close.rolling(200).mean()
        self.trend_ok = (self.close > self.sma200) & (sma50 > self.sma200)
        self.inv_vol = (1.0 / self.ret.rolling(63).std()).replace(
            [np.inf, -np.inf], np.nan)
        self.investable = self.close.rolling(63).median() > MIN_PRICE
        regime = compute_regime(panel, BREADTH_UNIVERSE, RegimeParams())
        self.state = regime["state"].reindex(self.close.index).ffill().fillna(
            "MIXED")
        # income-variant signals
        self.tlt_below_200 = self.close["TLT"] < self.sma200["TLT"]
        self.spy_tlt_corr = (self.ret["SPY"].rolling(126)
                             .corr(self.ret["TLT"]))


def equity_sleeve_curve(ctx: Ctx, members, start, end, *, gate=True,
                        top_n=None, mom_window=126, weighting="inv_vol",
                        vol_target=None) -> pd.Series:
    """Standalone equity-sleeve simulation (monthly rebalance + drift)."""
    mom = ctx.close.pct_change(mom_window)
    days = ctx.close.loc[start:end].index
    eq, cash = 100_000.0, 100_000.0
    pos: dict[str, float] = {}
    cash_v = eq
    last_month = None
    curve = np.empty(len(days))
    trail: list[float] = []   # trailing daily returns of the sleeve itself
    daily_rf = CASH_YIELD / 252.0
    n_rebals = 0

    for i, day in enumerate(days):
        if i > 0:
            prev_eq = eq
            for m in list(pos):
                r = ctx.ret.at[day, m]
                if not pd.isna(r):
                    pos[m] *= (1.0 + r)
            cash_v *= (1.0 + daily_rf)
            eq = sum(pos.values()) + cash_v
            trail.append(eq / prev_eq - 1.0)

        if last_month is None or day.month != last_month:
            live = [m for m in members if m in ctx.close.columns
                    and not pd.isna(ctx.inv_vol.at[day, m])
                    and bool(ctx.investable.at[day, m])]
            if gate:
                live = [m for m in live if bool(ctx.trend_ok.at[day, m])]
            if top_n and live:
                ranked = {m: mom.at[day, m] for m in live
                          if not pd.isna(mom.at[day, m])}
                live = [m for m, _ in sorted(ranked.items(),
                                             key=lambda kv: -kv[1])[:top_n]]
            if weighting == "equal":
                w = {m: 1.0 / len(live) for m in live} if live else {}
            else:
                raw = {m: float(ctx.inv_vol.at[day, m]) for m in live}
                tot = sum(raw.values())
                w = {m: v / tot for m, v in raw.items()} if tot else {}

            scale = 1.0
            if vol_target and len(trail) >= 21:
                realized = np.std(trail[-21:]) * np.sqrt(252)
                if realized > 0:
                    scale = min(1.0, vol_target / realized)
            w = {m: v * scale for m, v in w.items()}

            new_pos = {m: v * eq for m, v in w.items()}
            turn = sum(abs(new_pos.get(m, 0.0) - pos.get(m, 0.0))
                       for m in set(new_pos) | set(pos))
            eq -= turn * COST
            pos = {m: v * eq for m, v in w.items()}
            cash_v = eq - sum(pos.values())
            last_month = day.month
            n_rebals += 1

        curve[i] = eq
    s = pd.Series(curve, index=days)
    s.attrs["n_rebalances"] = n_rebals
    return s


def income_sleeve_curve(ctx: Ctx, start, end, variant="baseline") -> pd.Series:
    """Income sleeve with regime mix + research variants."""
    days = ctx.close.loc[start:end].index
    eq = 100_000.0
    pos: dict[str, float] = {}
    cash_v = eq
    last_month = None
    curve = np.empty(len(days))
    daily_rf = CASH_YIELD / 252.0

    for i, day in enumerate(days):
        if i > 0:
            for m in list(pos):
                r = ctx.ret.at[day, m]
                if not pd.isna(r):
                    pos[m] *= (1.0 + r)
            cash_v *= (1.0 + daily_rf)
            eq = sum(pos.values()) + cash_v

        if last_month is None or day.month != last_month:
            mix = dict(INCOME_MIX[ctx.state.at[day]])
            # research variant: halve duration when TLT trades below its
            # own 200DMA (rates-rising / inflation-shock proxy)
            if variant in ("duration", "both") and mix.get("TLT", 0) > 0:
                if bool(ctx.tlt_below_200.at[day]):
                    mix["TLT"] = mix["TLT"] * 0.5   # freed half -> cash
            # research variant: when stock-bond correlation flips positive,
            # gold takes half of the remaining TLT weight
            if variant in ("gold", "both") and mix.get("TLT", 0) > 0:
                corr = ctx.spy_tlt_corr.at[day]
                if not pd.isna(corr) and corr > 0:
                    shift = mix["TLT"] * 0.5
                    mix["TLT"] -= shift
                    mix["GLD"] = mix.get("GLD", 0.0) + shift
            live = {m: v for m, v in mix.items()
                    if v > 0 and m in ctx.close.columns
                    and not pd.isna(ctx.close.at[day, m])}
            # NOTE: weights deliberately NOT renormalized for the duration
            # variant — the freed weight is meant to sit in cash.
            new_pos = {m: v * eq for m, v in live.items()}
            turn = sum(abs(new_pos.get(m, 0.0) - pos.get(m, 0.0))
                       for m in set(new_pos) | set(pos))
            eq -= turn * COST
            pos = {m: v * eq for m, v in live.items()}
            cash_v = eq - sum(pos.values())
            last_month = day.month

        curve[i] = eq
    return pd.Series(curve, index=days)


def evaluate(curve: pd.Series) -> dict:
    st = perf_stats(curve)
    return {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
            for k, v in st.items()}


def main():
    panel = load_long_panel()
    ctx = Ctx(panel)
    results = {"sleeve1_macro": [], "sleeve2_income": [],
               "sleeve3_innovation": [], "sleeve4_options": []}

    # ---- Sleeve 1: selection & weighting grid (8) ----
    for gate, top_n, weighting in itertools.product(
            [True, False], [None, 4], ["inv_vol", "equal"]):
        cfg = {"gate": gate, "top_n": top_n, "weighting": weighting}
        row = {"config": cfg}
        for label, (s, e) in (("is", IS_WIN), ("oos", OOS_WIN)):
            c = equity_sleeve_curve(ctx, MACRO_MEMBERS, s, e, gate=gate,
                                    top_n=top_n, weighting=weighting)
            row[label] = evaluate(c)
        results["sleeve1_macro"].append(row)
        print("S1", cfg, "IS MAR", row["is"]["mar"],
              "OOS MAR", row["oos"]["mar"], flush=True)

    # ---- Sleeve 3: window x topN x vol-target grid (27) ----
    for window, top_n, vt in itertools.product(
            [63, 126, 252], [4, 6, 8], [None, 0.25, 0.35]):
        cfg = {"mom_window": window, "top_n": top_n, "vol_target": vt}
        row = {"config": cfg}
        for label, (s, e) in (("is", IS_WIN), ("oos", OOS_WIN)):
            c = equity_sleeve_curve(ctx, INNOVATION_MEMBERS, s, e,
                                    gate=True, top_n=top_n,
                                    mom_window=window, vol_target=vt)
            row[label] = evaluate(c)
        results["sleeve3_innovation"].append(row)
        print("S3", cfg, "IS MAR", row["is"]["mar"],
              "OOS MAR", row["oos"]["mar"], flush=True)

    # ---- Sleeve 2: research variants (4) ----
    for variant in ("baseline", "duration", "gold", "both"):
        cfg = {"variant": variant}
        row = {"config": cfg}
        for label, (s, e) in (("is", IS_WIN), ("oos", OOS_WIN)):
            c = income_sleeve_curve(ctx, s, e, variant=variant)
            row[label] = evaluate(c)
        results["sleeve2_income"].append(row)
        print("S2", cfg, "IS MAR", row["is"]["mar"],
              "OOS MAR", row["oos"]["mar"], flush=True)

    # ---- Sleeve 4: PMCC sweep on SMH (4) ----
    s4_cfgs = [{"short_delta": d, "sell_short_leg": True}
               for d in (0.15, 0.22, 0.30)]
    s4_cfgs.append({"short_delta": 0.22, "sell_short_leg": False})
    for cfg in s4_cfgs:
        row = {"config": cfg}
        for label, (s, e) in (("is", IS_WIN), ("oos", OOS_WIN)):
            curve, _ = run_pmcc(ctx.close["SMH"],
                                PMCCParams(short_delta=cfg["short_delta"],
                                           sell_short_leg=cfg["sell_short_leg"]),
                                start=s, end=e)
            row[label] = evaluate(curve)
        results["sleeve4_options"].append(row)
        print("S4", cfg, "IS MAR", row["is"]["mar"],
              "OOS MAR", row["oos"]["mar"], flush=True)

    out = os.path.join(HERE, "sleeve_optimize_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("written:", out, flush=True)


if __name__ == "__main__":
    main()
