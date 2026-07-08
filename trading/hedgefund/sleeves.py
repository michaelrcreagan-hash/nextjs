"""Four-sleeve portfolio backtest — the notes' architecture made mechanical.

Implements ``notes/four_sleeve_portfolio_architecture.md`` as a testable
daily simulation over real prices (``data_long/``, 2009->present, dividend-
adjusted closes so the income sleeve's carry is real):

  Sleeve 1 Macro Rotation .... LLY UNH NEE JNJ CCJ FCX + XLV XLU URNM COPX
  Sleeve 2 Income/Hedge ...... TLT GLD PFF GDXJ (regime-dependent mix)
  Sleeve 3 Innovation ........ MSTR MARA CLSK IREN NBIS QUBT IONQ RGTI
                               VRT COHR STX LITE
  Sleeve 4 Options ........... PMCC (LEAPS diagonal) on SMH via options_sim

Departments wired in (each individually ablatable for attribution):
  macro ....... regime.py state (VIX/SMH-trend/breadth/BTC) -> the notes'
                Part-10 sleeve weight matrix
  cycle ....... cycles.py 4yr x 16.8yr x seasonal multiplier scales the
                equity sleeves (freed weight -> cash)
  technical ... 200DMA/50>200 trend gate inside sleeves 1 & 3
  selection ... momentum top-N within the innovation sleeve (the theme-
                rotation brain's stock-selection step)
  exits ....... the notes' Part-12 portfolio stop: -20% from peak ->
                equity sleeves scaled to ~30% until drawdown < -10%
  options ..... sleeve 4 on/off

Honest gaps (documented, not faked): the fundamental gate, analyst
revisions, and sentiment departments need historical fundamentals/estimate/
sentiment data this repo doesn't have; they exist in the LLM agent layer
only and are NOT part of this mechanical simulation.

Assumptions (kept deliberately plain to avoid overfitting):
  - Names enter point-in-time when their price history starts; sleeve
    weights renormalize across live members.
  - Within-sleeve weighting is inverse 63-day volatility (no return
    forecasting), gated/selected per the department flags above.
  - Rebalance triggers: regime-state change, monthly/quarterly calendar,
    portfolio-stop engage/release.
  - Costs: 10 bps per side on traded notional.
  - No monthly contributions — pure return series so CAGR is comparable
    across periods and to benchmarks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .cycles import CycleParams, cycle_signal
from .data import load_panel
from .options_sim import PMCCParams, run_pmcc
from .regime import RegimeParams, compute_regime

DATA_LONG = os.path.join(os.path.dirname(__file__), "data_long")

MACRO_MEMBERS = ["LLY", "UNH", "NEE", "JNJ", "CCJ", "FCX",
                 "XLV", "XLU", "URNM", "COPX"]
INNOVATION_MEMBERS = ["MSTR", "MARA", "CLSK", "IREN", "NBIS", "QUBT",
                      "IONQ", "RGTI", "VRT", "COHR", "STX", "LITE"]
INCOME_MEMBERS = ["TLT", "GLD", "PFF", "GDXJ"]
# Breadth universe for the regime engine: liquid names with pre-2019
# history so the macro department has a real readout in 2010-2023.
BREADTH_UNIVERSE = ["NVDA", "AMD", "AVGO", "MRVL", "MU", "WDC", "AMAT",
                    "LRCX", "KLAC", "ASML", "TER", "MSFT", "ETN", "PWR",
                    "DLR", "EQIX", "CIEN", "CLS", "SMCI", "STX", "COHR"]

ALL_SLEEVE_SYMBOLS = sorted(
    set(MACRO_MEMBERS + INNOVATION_MEMBERS + INCOME_MEMBERS
        + BREADTH_UNIVERSE + ["SPY", "QQQ", "SMH", "VIX", "BTCUSD"])
)

# Part 10 regime-adjusted allocation matrix (rows sum with cash to 1.0).
SLEEVE_MATRIX = {
    "RISK_ON":  {"macro": 0.40, "income": 0.15, "innovation": 0.35,
                 "options": 0.10, "cash": 0.00},
    "MIXED":    {"macro": 0.30, "income": 0.25, "innovation": 0.20,
                 "options": 0.10, "cash": 0.15},
    "CAUTION":  {"macro": 0.15, "income": 0.40, "innovation": 0.05,
                 "options": 0.05, "cash": 0.35},
    "RISK_OFF": {"macro": 0.05, "income": 0.50, "innovation": 0.00,
                 "options": 0.00, "cash": 0.45},
}

# Part 4 income-sleeve internal mix by regime (normalized, GDXJ folded in
# per the current-allocation table).
INCOME_MIX = {
    "RISK_ON":  {"TLT": 0.25, "GLD": 0.25, "PFF": 0.50, "GDXJ": 0.00},
    "MIXED":    {"TLT": 0.36, "GLD": 0.28, "PFF": 0.18, "GDXJ": 0.18},
    "CAUTION":  {"TLT": 0.50, "GLD": 0.33, "PFF": 0.17, "GDXJ": 0.00},
    "RISK_OFF": {"TLT": 0.57, "GLD": 0.43, "PFF": 0.00, "GDXJ": 0.00},
}


@dataclass
class SleeveParams:
    # department switches (ablation knobs)
    use_macro_matrix: bool = True     # regime -> sleeve weights
    use_cycle_overlay: bool = True    # cycle multiplier on equity sleeves
    use_trend_gate: bool = True       # technical dept inside sleeves 1 & 3
    use_momentum_selection: bool = True  # top-N selection in innovation
    use_portfolio_stop: bool = True   # Part-12 drawdown rulebook
    use_options_sleeve: bool = True
    # mechanics
    static_state: str = "MIXED"       # matrix row used when macro is OFF
    innovation_top_n: int = 6
    momentum_window: int = 126
    # --- optimization knobs (defaults reproduce the committed baseline;
    # winning values from monte_carlo/sleeve_optimize.py) ---
    macro_trend_gate: bool = True         # winner: False (rank/weight only)
    income_variant: str = "baseline"      # winner: "both" (duration + gold)
    innovation_vol_target: float | None = None   # winner: 0.35 (annualized)
    vol_window: int = 63
    cost_bps_side: float = 10.0
    cash_yield: float = 0.03          # blended 2010-2026 T-bill-ish
    stop_dd: float = 0.20             # engage at -20% from peak
    stop_release_dd: float = 0.10     # release when back above -10%
    stop_equity_scale: float = 0.30   # equity sleeves scaled to ~30%
    # Institutional investability floor: a name is only eligible while its
    # trailing 63-day median close is above this. Without it, the pre-2019
    # shell-company eras of MARA/CLSK/QUBT (sub-$1 prices, +2000% single
    # days) leak untradeable penny-stock moves into the innovation sleeve.
    min_price: float = 5.0
    start_equity: float = 100_000.0
    cycle_params: CycleParams = field(default_factory=CycleParams)


def load_long_panel(symbols: list[str] | None = None):
    return load_panel(symbols or ALL_SLEEVE_SYMBOLS, data_dir=DATA_LONG)


class _Precomp:
    """Vectorized once-per-run inputs so the daily loop stays cheap."""

    def __init__(self, panel, p: SleeveParams):
        close = panel.close
        self.close = close
        self.ret = close.pct_change()
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        self.trend_ok = (close > sma200) & (sma50 > sma200)
        self.mom = close.pct_change(p.momentum_window)
        self.inv_vol = 1.0 / self.ret.rolling(p.vol_window).std()
        self.inv_vol = self.inv_vol.replace([np.inf, -np.inf], np.nan)
        self.investable = close.rolling(63).median() > p.min_price
        # income-variant signals (duration shock proxy, corr flip)
        self.tlt_below_200 = (close["TLT"] < sma200["TLT"]
                              if "TLT" in close.columns else None)
        self.spy_tlt_corr = (self.ret["SPY"].rolling(126).corr(self.ret["TLT"])
                             if "TLT" in close.columns else None)


def _sleeve_internal_weights(pc: _Precomp, members: list[str], day,
                             p: SleeveParams, gate: bool,
                             select_top: int | None) -> dict[str, float]:
    live = [m for m in members if m in pc.close.columns
            and not pd.isna(pc.inv_vol.at[day, m])
            and bool(pc.investable.at[day, m])]
    if gate:
        live = [m for m in live if bool(pc.trend_ok.at[day, m])]
    if select_top and live:
        mom = {m: pc.mom.at[day, m] for m in live
               if not pd.isna(pc.mom.at[day, m])}
        live = [m for m, _ in sorted(mom.items(), key=lambda kv: -kv[1])
                [:select_top]]
    w = {m: float(pc.inv_vol.at[day, m]) for m in live}
    total = sum(w.values())
    return {m: v / total for m, v in w.items()} if total else {}


def _income_weights(pc: _Precomp, day, state: str,
                    variant: str = "baseline") -> dict[str, float]:
    mix = dict(INCOME_MIX[state])
    # "duration": halve TLT when it trades below its own 200DMA (rates-
    # rising / inflation-shock proxy) — freed weight sits in cash.
    if variant in ("duration", "both") and mix.get("TLT", 0) > 0 \
            and pc.tlt_below_200 is not None \
            and bool(pc.tlt_below_200.at[day]):
        mix["TLT"] *= 0.5
    # "gold": when the trailing 126d stock-bond correlation flips positive
    # (the regime where bonds stop hedging), gold takes half of TLT.
    if variant in ("gold", "both") and mix.get("TLT", 0) > 0 \
            and pc.spy_tlt_corr is not None:
        corr = pc.spy_tlt_corr.at[day]
        if not pd.isna(corr) and corr > 0:
            shift = mix["TLT"] * 0.5
            mix["TLT"] -= shift
            mix["GLD"] = mix.get("GLD", 0.0) + shift
    live = {m: w for m, w in mix.items()
            if w > 0 and m in pc.close.columns
            and not pd.isna(pc.close.at[day, m])}
    if not live:
        return {}
    if variant == "baseline":
        total = sum(live.values())
        return {m: w / total for m, w in live.items()}
    # Variants normalize against the ORIGINAL mix total so weight freed by
    # the duration cut stays in cash instead of being redistributed.
    base_total = sum(w for w in INCOME_MIX[state].values() if w > 0)
    return {m: w / base_total for m, w in live.items()}


def run_sleeve_backtest(
    panel,
    start: str,
    end: str,
    params: SleeveParams | None = None,
    pmcc_ret: pd.Series | None = None,
) -> dict:
    """Daily four-sleeve simulation. Returns portfolio curve, standalone
    sleeve curves, weights history, and the rebalance log."""
    p = params or SleeveParams()
    pc = _Precomp(panel, p)
    close = pc.close

    regime = compute_regime(panel, BREADTH_UNIVERSE, RegimeParams())
    state_series = regime["state"].reindex(close.index).ffill().fillna("MIXED")

    if pmcc_ret is None:
        pmcc_curve, _ = run_pmcc(close["SMH"], PMCCParams(),
                                 start=start, end=end)
        pmcc_ret = pmcc_curve.pct_change().fillna(0.0)

    days = close.loc[start:end].index
    if len(days) < 30:
        raise ValueError("window too short")

    equity = p.start_equity
    peak = equity
    stopped = False
    last_state = None
    last_month = None
    daily_rf = p.cash_yield / 252.0

    curve = pd.Series(index=days, dtype=float)
    sleeve_eq = {k: p.start_equity for k in
                 ("macro", "income", "innovation", "options")}
    sleeve_curves = {k: pd.Series(index=days, dtype=float) for k in sleeve_eq}
    weights_hist, rebalances = [], []

    def target_weights(day):
        state = state_series.at[day] if p.use_macro_matrix else p.static_state
        row = SLEEVE_MATRIX[state]
        w_macro, w_income = row["macro"], row["income"]
        w_innov, w_opt = row["innovation"], row["options"]

        cyc = 1.0
        if p.use_cycle_overlay:
            cyc = cycle_signal(day, p.cycle_params)["cycle_multiplier"]
            w_macro, w_innov, w_opt = w_macro * cyc, w_innov * cyc, w_opt * cyc
            # A multiplier > 1 may only expand equity sleeves into the
            # cash bucket — never into leverage or the income sleeve.
            eq_total = w_macro + w_innov + w_opt
            max_eq = 1.0 - w_income
            if eq_total > max_eq and eq_total > 0:
                s = max_eq / eq_total
                w_macro, w_innov, w_opt = w_macro * s, w_innov * s, w_opt * s
        if not p.use_options_sleeve:
            w_opt = 0.0
        if stopped:
            eq_total = w_macro + w_innov + w_opt
            if eq_total > p.stop_equity_scale and eq_total > 0:
                s = p.stop_equity_scale / eq_total
                w_macro, w_innov, w_opt = w_macro * s, w_innov * s, w_opt * s

        macro_w = _sleeve_internal_weights(
            pc, MACRO_MEMBERS, day, p,
            p.use_trend_gate and p.macro_trend_gate, None)
        innov_w = _sleeve_internal_weights(
            pc, INNOVATION_MEMBERS, day, p, p.use_trend_gate,
            p.innovation_top_n if p.use_momentum_selection else None)
        if p.innovation_vol_target and len(innov_trail) >= 21:
            realized = float(np.std(innov_trail[-21:]) * np.sqrt(252))
            if realized > 0:
                guard = min(1.0, p.innovation_vol_target / realized)
                innov_w = {m: w * guard for m, w in innov_w.items()}
        income_w = _income_weights(pc, day, state, p.income_variant)

        target: dict[str, float] = {}
        for m, w in macro_w.items():
            target[m] = target.get(m, 0.0) + w * w_macro
        for m, w in innov_w.items():
            target[m] = target.get(m, 0.0) + w * w_innov
        for m, w in income_w.items():
            target[m] = target.get(m, 0.0) + w * w_income
        cash = max(1.0 - sum(target.values()) - w_opt, 0.0)
        return target, w_opt, cash, state, cyc

    # Positions are tracked as dollar values that DRIFT with returns
    # between rebalances — no implicit free daily rebalancing. The same
    # applies to the standalone sleeve sub-curves (each rebalanced on the
    # portfolio's cadence with the same per-side costs), so sub-curve
    # stats aren't inflated by a zero-cost daily rebalancing bonus.
    values: dict[str, float] = {}          # symbol -> $ value
    options_v = 0.0
    cash_v = equity
    sleeve_pos: dict[str, dict[str, float]] = {
        "macro": {}, "income": {}, "innovation": {}}
    sleeve_cash = {"macro": p.start_equity, "income": p.start_equity,
                   "innovation": p.start_equity}

    innov_trail: list[float] = []   # daily returns of the innovation book

    def sleeve_targets(day, state):
        innov = _sleeve_internal_weights(
            pc, INNOVATION_MEMBERS, day, p, p.use_trend_gate,
            p.innovation_top_n if p.use_momentum_selection else None)
        if p.innovation_vol_target and len(innov_trail) >= 21:
            realized = float(np.std(innov_trail[-21:]) * np.sqrt(252))
            if realized > 0:
                guard = min(1.0, p.innovation_vol_target / realized)
                innov = {m: w * guard for m, w in innov.items()}
        return {
            "macro": _sleeve_internal_weights(
                pc, MACRO_MEMBERS, day, p,
                p.use_trend_gate and p.macro_trend_gate, None),
            "innovation": innov,
            "income": _income_weights(pc, day, state, p.income_variant),
        }

    for i, day in enumerate(days):
        if i > 0:
            # drift every position with the day's return
            for m in list(values):
                r = pc.ret.at[day, m]
                if not pd.isna(r):
                    values[m] *= (1.0 + r)
            r_opt = float(pmcc_ret.get(day, 0.0))
            options_v *= (1.0 + r_opt)
            cash_v *= (1.0 + daily_rf)
            equity = sum(values.values()) + options_v + cash_v

            prev_innov = sleeve_eq["innovation"]
            for name in ("macro", "income", "innovation"):
                for m in list(sleeve_pos[name]):
                    r = pc.ret.at[day, m]
                    if not pd.isna(r):
                        sleeve_pos[name][m] *= (1.0 + r)
                sleeve_cash[name] *= (1.0 + daily_rf)
                sleeve_eq[name] = (sum(sleeve_pos[name].values())
                                   + sleeve_cash[name])
            sleeve_eq["options"] *= (1.0 + r_opt)
            innov_trail.append(sleeve_eq["innovation"] / prev_innov - 1.0)

        peak = max(peak, equity)
        dd = equity / peak - 1.0

        stop_flip = False
        if p.use_portfolio_stop:
            if not stopped and dd <= -p.stop_dd:
                stopped, stop_flip = True, True
            elif stopped and dd >= -p.stop_release_dd:
                stopped, stop_flip = False, True

        state_now = (state_series.at[day] if p.use_macro_matrix
                     else p.static_state)
        need_rebal = (i == 0 or stop_flip or state_now != last_state
                      or day.month != last_month)

        if need_rebal:
            target, w_opt, cash, state, cyc = target_weights(day)
            # trade portfolio to target dollar values
            turnover_d = 0.0
            new_values = {m: w * equity for m, w in target.items()}
            for m in set(new_values) | set(values):
                turnover_d += abs(new_values.get(m, 0.0) - values.get(m, 0.0))
            turnover_d += abs(w_opt * equity - options_v)
            cost = turnover_d * (p.cost_bps_side / 10_000.0)
            equity -= cost
            values = {m: w * equity for m, w in target.items()}
            options_v = w_opt * equity
            cash_v = equity - sum(values.values()) - options_v
            last_state, last_month = state, day.month
            rebalances.append({
                "date": day, "state": state, "cycle_mult": round(cyc, 3),
                "stopped": stopped, "n_positions": len(values),
                "turnover": round(turnover_d / max(equity, 1e-9), 3),
            })

            # rebalance the standalone sleeve books on the same cadence
            st_targets = sleeve_targets(day, state)
            for name, tw in st_targets.items():
                eq_s = sleeve_eq[name]
                new_pos = {m: w * eq_s for m, w in tw.items()}
                turn = sum(abs(new_pos.get(m, 0.0)
                               - sleeve_pos[name].get(m, 0.0))
                           for m in set(new_pos) | set(sleeve_pos[name]))
                eq_s -= turn * (p.cost_bps_side / 10_000.0)
                sleeve_pos[name] = {m: w * eq_s for m, w in tw.items()}
                sleeve_cash[name] = eq_s - sum(sleeve_pos[name].values())
                sleeve_eq[name] = eq_s

        curve.loc[day] = equity
        for name in sleeve_curves:
            sleeve_curves[name].loc[day] = sleeve_eq[name]
        weights_hist.append({
            "date": day,
            "cash": round(cash_v / equity, 4),
            "options": round(options_v / equity, 4),
            "equity_w": round(sum(values.values()) / equity, 4),
            "state": last_state, "stopped": stopped,
        })

    return {
        "curve": curve,
        "sleeve_curves": sleeve_curves,
        "weights": pd.DataFrame(weights_hist).set_index("date"),
        "rebalances": pd.DataFrame(rebalances),
        "regime": regime.reindex(days),
    }


def perf_stats(curve: pd.Series) -> dict:
    curve = curve.dropna()
    yrs = (curve.index[-1] - curve.index[0]).days / 365.25
    total = curve.iloc[-1] / curve.iloc[0]
    cagr = total ** (1 / yrs) - 1 if yrs > 0 else np.nan
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(252)
    sharpe = (r.mean() * 252) / vol if vol > 0 else np.nan
    dd = (curve / curve.cummax() - 1).min()
    mar = cagr / abs(dd) if dd < 0 else np.nan
    return {
        "cagr": round(cagr * 100, 1), "vol": round(vol * 100, 1),
        "sharpe": round(float(sharpe), 2), "max_dd": round(dd * 100, 1),
        "mar": round(float(mar), 2), "total_x": round(total, 2),
        "years": round(yrs, 2),
    }
