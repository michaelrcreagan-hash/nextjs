"""
hermes_agent -- Step 4: Backtest Runner (Numba JIT portfolio loop)

Multi-position, regime-capped, venue-costed, partial-exit-aware.

WHY THIS IS NOT THE CBT TEMPLATE ENGINE
---------------------------------------
~/.claude/cbt-framework/templates/backtest.py holds a single `self.position`
and has no partial-exit path. hermes_agent needs neither of those things: it
runs up to `max_positions` concurrently under a regime-varying gross exposure
cap, and its whole exit design is a partial. The template's prop-firm breach
tracking is genuinely useful and is retained in spirit (see prop_firm in
config.yaml, currently disabled for this personal-account strategy).

THE THREE RULES THAT ARE EASY TO GET WRONG AND MATTER MOST
----------------------------------------------------------
1. `min_position_value_usd` is a SKIP, never a scale-down. Scaling a signal
   down to fit recreates the ~$143-average-position structure that Barber &
   Odean (2000) measured a 6.5pp/yr cost drag on.
2. Costs are per-trade DOLLARS at the venue's real structure, not a blended
   percentage of portfolio. Coinbase spot taker at 0.60% is ~17x the equity
   slippage assumption; blending them hides which sleeve pays.
3. Deployed capital may never exceed gross_exposure[t]. That is the entire
   mechanism under test -- if it leaks, R1 is untestable.

Each is asserted after the run, not merely intended.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml
from numba import njit

from src.data_loader import load_panel, atr_proxy
from src.exits import (EXIT_NONE, EXIT_INITIAL_STOP, EXIT_TRAIL,
                       EXIT_BREAKEVEN, EXIT_SCALE_OUT, EXIT_END_OF_DATA,
                       EXIT_DERISK, EXIT_NAMES, initial_stop_long, step_position)
from src.regime import compute_regime, occupancy, REGIME_NAMES
from src.signals import momentum_signals

STRATEGY_DIR = Path(__file__).resolve().parent

MAX_TRADES = 20000
TRADE_COLS = 9  # sym, entry_idx, exit_idx, entry_px, exit_px, qty, pnl, cost, reason


@njit(cache=True)
def _run_loop(close, atr, eligible, rank_key, gross_exposure, trail_pct,
              venue, initial_capital, percent_per_trade, max_positions,
              min_position_value, atr_mult, activation_pct, trigger_rr,
              min_move_pct, first_tranche_pct, move_stop_to_be,
              crypto_taker_pct, crypto_slip_bps, equity_commission,
              equity_slip_bps, warm_start):
    """
    The hot path. Returns (equity_curve, trades, n_trades, deployed_frac).

    A "trade" row is one FILL, so a scaled-out position emits two rows: the
    tranche and the runner. Profit factor is therefore computed over fills,
    which is the conservative reading -- it counts the scale-out's small win
    and the runner's outcome separately rather than netting them into one
    flattering round-trip.
    """
    n_bars, n_sym = close.shape

    cash = initial_capital
    equity_curve = np.zeros(n_bars)
    deployed_frac = np.zeros(n_bars)

    # Per-slot position state.
    p_active = np.zeros(max_positions, dtype=np.int8)
    p_sym = np.zeros(max_positions, dtype=np.int32)
    p_entry_px = np.zeros(max_positions)
    p_entry_idx = np.zeros(max_positions, dtype=np.int32)
    p_qty = np.zeros(max_positions)
    p_stop = np.zeros(max_positions)
    p_kind = np.zeros(max_positions, dtype=np.int8)
    p_peak = np.zeros(max_positions)
    p_scaled = np.zeros(max_positions, dtype=np.int8)
    p_rdist = np.zeros(max_positions)
    p_cost = np.zeros(max_positions)   # entry cost carried until fully closed

    trades = np.zeros((MAX_TRADES, TRADE_COLS))
    n_trades = 0

    for t in range(n_bars):
        # ---------- mark to market ----------
        pos_value = 0.0
        for k in range(max_positions):
            if p_active[k] == 1:
                pos_value += p_qty[k] * close[t, p_sym[k]]
        equity = cash + pos_value

        if t < warm_start:
            equity_curve[t] = equity
            deployed_frac[t] = 0.0
            continue

        # ---------- manage open positions ----------
        for k in range(max_positions):
            if p_active[k] == 0:
                continue
            s = p_sym[k]
            price = close[t, s]

            action, fill, frac, new_stop, new_kind, new_peak, new_scaled = step_position(
                price, p_entry_px[k], p_stop[k], p_kind[k], p_peak[k],
                p_scaled[k], p_rdist[k], trail_pct[t], activation_pct,
                trigger_rr, min_move_pct, first_tranche_pct, move_stop_to_be)

            p_stop[k] = new_stop
            p_kind[k] = new_kind
            p_peak[k] = new_peak
            p_scaled[k] = new_scaled

            if action == EXIT_NONE:
                continue

            qty_out = p_qty[k] * frac
            gross_out = qty_out * fill

            # --- venue-aware exit cost, in dollars ---
            if venue[s] == 0:
                cost = gross_out * (crypto_taker_pct / 100.0) \
                     + gross_out * (crypto_slip_bps / 10000.0)
            else:
                cost = equity_commission + gross_out * (equity_slip_bps / 10000.0)

            cash += gross_out - cost

            # Entry cost is amortised across the fills that close the position.
            entry_cost_share = p_cost[k] * frac
            pnl = qty_out * (fill - p_entry_px[k]) - cost - entry_cost_share
            p_cost[k] -= entry_cost_share

            if n_trades < MAX_TRADES:
                trades[n_trades, 0] = s
                trades[n_trades, 1] = p_entry_idx[k]
                trades[n_trades, 2] = t
                trades[n_trades, 3] = p_entry_px[k]
                trades[n_trades, 4] = fill
                trades[n_trades, 5] = qty_out
                trades[n_trades, 6] = pnl
                trades[n_trades, 7] = cost + entry_cost_share
                trades[n_trades, 8] = action
                n_trades += 1

            p_qty[k] -= qty_out
            if action != EXIT_SCALE_OUT or p_qty[k] <= 1e-12:
                p_active[k] = 0
                p_qty[k] = 0.0
                p_cost[k] = 0.0

        # ---------- re-mark after exits ----------
        pos_value = 0.0
        n_open = 0
        for k in range(max_positions):
            if p_active[k] == 1:
                pos_value += p_qty[k] * close[t, p_sym[k]]
                n_open += 1
        equity = cash + pos_value

        # ---------- DE-RISK: enforce the cap CONTINUOUSLY, not just at entry --
        # Without this the regime engine only gates NEW entries, and deployed
        # capital drifts above the cap whenever the regime downgrades (80% ->
        # 25%) or prices rise. That is a materially weaker mechanism than the
        # one config.yaml describes, and it made the "deployed <= gross
        # exposure" invariant fail on 29 bars in the first baseline run.
        #
        # The trim ITERATES because trimming costs money: selling reduces
        # equity, which reduces the cap, which can leave the position set
        # marginally over again. One pass left 11 bars still breaching. Three
        # passes converge -- each pass shrinks the overshoot by roughly the
        # cost rate, so the residual after three is far below the 1e-6
        # tolerance the invariant check uses.
        #
        # Trim pro-rata across open positions: risk reduction must not be
        # blocked by min_position_value_usd, which governs ENTRIES only.
        for _pass in range(3):
            cap = gross_exposure[t] * equity
            if pos_value <= cap + 1e-9 or n_open == 0:
                break
            keep = cap / pos_value if pos_value > 0 else 0.0
            if keep < 0.0:
                keep = 0.0
            for k in range(max_positions):
                if p_active[k] == 0:
                    continue
                s = p_sym[k]
                price = close[t, s]
                qty_out = p_qty[k] * (1.0 - keep)
                if qty_out <= 1e-12:
                    continue
                gross_out = qty_out * price
                if venue[s] == 0:
                    cost = gross_out * (crypto_taker_pct / 100.0) \
                         + gross_out * (crypto_slip_bps / 10000.0)
                else:
                    cost = equity_commission + gross_out * (equity_slip_bps / 10000.0)
                cash += gross_out - cost
                entry_cost_share = p_cost[k] * (1.0 - keep)
                pnl = qty_out * (price - p_entry_px[k]) - cost - entry_cost_share
                p_cost[k] -= entry_cost_share
                if n_trades < MAX_TRADES:
                    trades[n_trades, 0] = s
                    trades[n_trades, 1] = p_entry_idx[k]
                    trades[n_trades, 2] = t
                    trades[n_trades, 3] = p_entry_px[k]
                    trades[n_trades, 4] = price
                    trades[n_trades, 5] = qty_out
                    trades[n_trades, 6] = pnl
                    trades[n_trades, 7] = cost + entry_cost_share
                    trades[n_trades, 8] = EXIT_DERISK
                    n_trades += 1
                p_qty[k] -= qty_out
                if p_qty[k] * price < 1.0:      # dust
                    p_active[k] = 0
                    p_qty[k] = 0.0
                    p_cost[k] = 0.0

            pos_value = 0.0
            n_open = 0
            for k in range(max_positions):
                if p_active[k] == 1:
                    pos_value += p_qty[k] * close[t, p_sym[k]]
                    n_open += 1
            equity = cash + pos_value

        # ---------- entries ----------
        cap = gross_exposure[t] * equity
        room = cap - pos_value
        free_slots = max_positions - n_open

        if room > 0.0 and free_slots > 0:
            # Rank eligible symbols not already held.
            for _ in range(free_slots):
                best = -1
                best_key = -1.0e18
                for s in range(n_sym):
                    if not eligible[t, s]:
                        continue
                    held = False
                    for k in range(max_positions):
                        if p_active[k] == 1 and p_sym[k] == s:
                            held = True
                            break
                    if held:
                        continue
                    if rank_key[t, s] > best_key:
                        best_key = rank_key[t, s]
                        best = s
                if best < 0:
                    break

                s = best
                price = close[t, s]

                # Cost-reserved sizing. Entering costs money, so equity falls
                # by `cost` and the cap (gross x equity) falls with it. Sizing
                # naively to `room` therefore lands marginally OVER the cap --
                # which is what still breached the invariant on 11 bars after
                # the de-risk loop was added. Solve for the largest target
                # that stays inside the cap once its own cost is paid:
                #     target <= (room - gross*fixed) / (1 + gross*rate)
                if venue[s] == 0:
                    rate = crypto_taker_pct / 100.0 + crypto_slip_bps / 10000.0
                    fixed = 0.0
                else:
                    rate = equity_slip_bps / 10000.0
                    fixed = equity_commission
                g = gross_exposure[t]
                room_adj = (room - g * fixed) / (1.0 + g * rate)

                target = equity * (percent_per_trade / 100.0)
                if target > room_adj:
                    target = room_adj

                # RULE 1: below the floor is a SKIP. Not a scale-down.
                if target < min_position_value:
                    break

                if venue[s] == 0:
                    cost = target * (crypto_taker_pct / 100.0) \
                         + target * (crypto_slip_bps / 10000.0)
                else:
                    cost = equity_commission + target * (equity_slip_bps / 10000.0)

                if cash < target + cost:
                    break

                qty = target / price
                stop = initial_stop_long(price, atr[t, s], atr_mult)

                slot = -1
                for k in range(max_positions):
                    if p_active[k] == 0:
                        slot = k
                        break
                if slot < 0:
                    break

                cash -= (target + cost)
                p_active[slot] = 1
                p_sym[slot] = s
                p_entry_px[slot] = price
                p_entry_idx[slot] = t
                p_qty[slot] = qty
                p_stop[slot] = stop
                p_kind[slot] = 0
                p_peak[slot] = price
                p_scaled[slot] = 0
                p_rdist[slot] = price - stop
                p_cost[slot] = cost

                # Recompute equity/cap/room from actuals rather than
                # decrementing `room` by `target`. Each entry's cost lowers
                # equity and therefore lowers the cap, so on a bar that opens
                # several positions the later ones were being sized against a
                # stale cap -- the last 4 breaching bars were all multi-entry
                # bars overshooting by ~3e-4 of equity.
                pos_value = 0.0
                n_open = 0
                for kk in range(max_positions):
                    if p_active[kk] == 1:
                        pos_value += p_qty[kk] * close[t, p_sym[kk]]
                        n_open += 1
                equity = cash + pos_value
                cap = gross_exposure[t] * equity
                room = cap - pos_value

        pos_value = 0.0
        for k in range(max_positions):
            if p_active[k] == 1:
                pos_value += p_qty[k] * close[t, p_sym[k]]
        equity_curve[t] = cash + pos_value
        deployed_frac[t] = pos_value / (cash + pos_value) if (cash + pos_value) > 0 else 0.0

    # ---------- close survivors at the final bar ----------
    t = n_bars - 1
    for k in range(max_positions):
        if p_active[k] == 1:
            s = p_sym[k]
            fill = close[t, s]
            gross_out = p_qty[k] * fill
            if venue[s] == 0:
                cost = gross_out * (crypto_taker_pct / 100.0) \
                     + gross_out * (crypto_slip_bps / 10000.0)
            else:
                cost = equity_commission + gross_out * (equity_slip_bps / 10000.0)
            cash += gross_out - cost
            pnl = p_qty[k] * (fill - p_entry_px[k]) - cost - p_cost[k]
            if n_trades < MAX_TRADES:
                trades[n_trades, 0] = s
                trades[n_trades, 1] = p_entry_idx[k]
                trades[n_trades, 2] = t
                trades[n_trades, 3] = p_entry_px[k]
                trades[n_trades, 4] = fill
                trades[n_trades, 5] = p_qty[k]
                trades[n_trades, 6] = pnl
                trades[n_trades, 7] = cost + p_cost[k]
                trades[n_trades, 8] = EXIT_END_OF_DATA
                n_trades += 1
            p_active[k] = 0
    equity_curve[t] = cash

    return equity_curve, trades, n_trades, deployed_frac


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def compute_metrics(equity: np.ndarray, trades: np.ndarray, n_trades: int,
                    dates: np.ndarray, n_trials: int = 1) -> dict:
    eq = equity[equity > 0]
    if eq.size < 2:
        return {"error": "degenerate equity curve"}

    years = (dates[-1].astype("datetime64[D]").astype(int)
             - dates[0].astype("datetime64[D]").astype(int)) / 365.25
    total_return = eq[-1] / eq[0] - 1.0
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0 if years > 0 else np.nan

    rets = np.diff(eq) / eq[:-1]
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0

    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    max_dd = float(dd.min())
    mar = cagr / abs(max_dd) if max_dd < 0 else np.nan

    tr = trades[:n_trades]
    pnl = tr[:, 6]
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf
    win_rate = float(len(wins)) / n_trades if n_trades else 0.0
    expectancy = float(pnl.mean()) if n_trades else 0.0
    total_cost = float(tr[:, 7].sum())
    turnover = float((tr[:, 5] * tr[:, 4]).sum()) / eq[0] if eq[0] > 0 else 0.0

    return {
        "total_return_pct": round(100 * total_return, 2),
        "cagr_pct": round(100 * cagr, 2),
        "sharpe": round(float(sharpe), 3),
        "deflated_sharpe": round(deflated_sharpe(rets, sharpe, n_trials), 3),
        "dsr_trials": n_trials,
        "max_drawdown_pct": round(100 * max_dd, 2),
        "mar": round(float(mar), 3) if not np.isnan(mar) else None,
        "profit_factor": round(float(profit_factor), 3),
        "win_rate_pct": round(100 * win_rate, 2),
        "expectancy_usd": round(expectancy, 2),
        "n_fills": int(n_trades),
        "total_cost_usd": round(total_cost, 2),
        "turnover_x": round(turnover, 2),
        "final_equity_usd": round(float(eq[-1]), 2),
        "years": round(float(years), 3),
    }


def deflated_sharpe(rets: np.ndarray, sharpe: float, n_trials: int,
                    trial_sr_std: float | None = None) -> float:
    """
    Bailey & Lopez de Prado's Deflated Sharpe Ratio.

    Why this and not raw Sharpe: with N candidate configurations, the BEST
    observed Sharpe is inflated even when every candidate is pure noise. DSR
    is the probability the true Sharpe exceeds the expected MAXIMUM under that
    null, and it corrects for skew and fat tails as well as for selection.

        SR0  = trial_sr_std * [ (1-g) * Z(1 - 1/N) + g * Z(1 - 1/(N*e)) ]
        DSR  = PHI( (SR - SR0) * sqrt(n-1)
                    / sqrt(1 - g3*SR + (g4-1)/4 * SR^2) )

    with g = Euler-Mascheroni, SR in PER-PERIOD (daily) units.

    At step 5 n_trials is honestly 1, so SR0 = 0 and this reduces to the
    Probabilistic Sharpe Ratio against zero. That is the number to quote now.
    It will fall sharply at step 8: the pre-registered grids multiply out past
    1,700 configurations, and the same Sharpe deflates a great deal against
    N=1,700. Quoting the step-5 figure as if it survived the search would be
    exactly the error DSR exists to prevent.

    `trial_sr_std` is the dispersion of Sharpe across the trials. When it is
    not supplied it defaults to 1/sqrt(n), the standard error of a Sharpe
    estimate under the null -- a conservative stand-in, not a measurement.
    """
    from math import sqrt, log, erf, e as E

    n = len(rets)
    sd = float(rets.std())
    if n < 3 or sd == 0:
        return float("nan")

    sr = sharpe / sqrt(252.0)                     # annualized -> daily
    g3 = float(((rets - rets.mean()) ** 3).mean() / sd ** 3)
    g4 = float(((rets - rets.mean()) ** 4).mean() / sd ** 4)

    if n_trials > 1:
        v = trial_sr_std if trial_sr_std is not None else 1.0 / sqrt(n)
        euler = 0.5772156649015329
        sr0 = v * ((1.0 - euler) * _z(1.0 - 1.0 / n_trials)
                   + euler * _z(1.0 - 1.0 / (n_trials * E)))
    else:
        sr0 = 0.0

    denom = sqrt(max(1e-12, 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2))
    z = (sr - sr0) * sqrt(n - 1.0) / denom
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def _z(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    from math import sqrt, log
    if p <= 0 or p >= 1:
        return 0.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = sqrt(-2 * log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = sqrt(-2 * log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def load_config() -> dict:
    return yaml.safe_load((STRATEGY_DIR / "config.yaml").read_text())


def run(cfg: dict,
        regime_scaled: bool = True,
        first_tranche_override: float | None = None,
        static_gross: float = 0.80) -> dict:
    """
    Execute one arm.

    regime_scaled=False is the STATIC ALLOCATION arm RESEARCH.md requires --
    identical entries and exits, gross exposure pinned at `static_gross`
    instead of varying by regime. It is the arm that can embarrass the regime
    engine, and four_sleeve's experience says it might: its regime matrix
    ADDED drawdown versus a static allocation.
    """
    panel = load_panel(start_date=cfg["time"]["start_date"])
    reg = compute_regime(panel, cfg)
    sig = momentum_signals(panel["close"])
    atr = atr_proxy(panel["close"], 14)

    warm_start = int(np.argmax(reg["warm"])) if reg["warm"].any() else panel["n_bars"]

    gross = reg["gross_exposure"] if regime_scaled else np.where(
        reg["warm"], static_gross, 0.0)
    trail = reg["trail_pct"] if regime_scaled else np.full(
        panel["n_bars"], float(cfg["risk"]["trailing_stop"]["distance"]))

    so = cfg["risk"]["scale_out"]
    ft = so["first_tranche_pct"] if first_tranche_override is None else first_tranche_override
    vc = cfg["strategy_params"]["venue_costs"]

    eq, trades, n_tr, dep = _run_loop(
        np.ascontiguousarray(panel["close"]),
        np.ascontiguousarray(np.nan_to_num(atr, nan=0.0)),
        np.ascontiguousarray(sig["eligible"]),
        np.ascontiguousarray(sig["rank_key"]),
        np.ascontiguousarray(gross),
        np.ascontiguousarray(trail),
        panel["venue"],
        float(cfg["account"]["initial_capital"]),
        float(cfg["sizing"]["percent_per_trade"]),
        int(cfg["sizing"]["max_positions"]),
        float(cfg["sizing"]["min_position_value_usd"]),
        float(cfg["risk"]["stop_loss"]["atr_multiplier"]),
        float(cfg["risk"]["trailing_stop"]["activation"]),
        float(so["trigger_rr"]),
        float(so["min_move_pct"]),
        float(ft),
        1 if so["move_stop_to_breakeven"] else 0,
        float(vc["coinbase_spot"]["taker_pct"]),
        float(vc["coinbase_spot"]["slippage_bps"]),
        float(vc["merrill_ira"]["commission_usd"]),
        float(vc["merrill_ira"]["slippage_bps"]),
        warm_start,
    )

    m = compute_metrics(eq, trades, n_tr, panel["dates"], n_trials=1)
    m["max_deployed_frac"] = round(float(dep.max()), 4)
    m["mean_deployed_frac"] = round(float(dep[warm_start:].mean()), 4)

    return {"metrics": m, "equity": eq, "trades": trades[:n_tr],
            "panel": panel, "regime": reg, "deployed": dep,
            "warm_start": warm_start, "gross": gross}


def buy_and_hold(panel: dict, cfg: dict, symbol: str | None = None) -> dict:
    """
    Comparison arm. symbol=None -> equal-weight all 11, rebalanced never.
    """
    close = panel["close"]
    cap = float(cfg["account"]["initial_capital"])
    if symbol is None:
        qty = (cap / close.shape[1]) / close[0]
        eq = close @ qty
    else:
        i = panel["symbols"].index(symbol)
        eq = cap * close[:, i] / close[0, i]
    m = compute_metrics(eq, np.zeros((1, TRADE_COLS)), 0, panel["dates"])
    m["profit_factor"] = None
    m["win_rate_pct"] = None
    m["expectancy_usd"] = None
    return {"metrics": m, "equity": eq}
