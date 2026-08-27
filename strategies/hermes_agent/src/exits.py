"""
hermes_agent -- Step 3: Exit Engine (Numba)

The full two-stage exit the user specified:

    3.0 x ATR initial stop
      -> at +1R: sell `first_tranche_pct`, move the remaining stop to breakeven
      -> runner rides the regime-scaled trailing stop (20/18/16/15%)

Exposed as njit primitives so the portfolio loop in backtest.py can call them
per-bar per-slot, and so the synthetic-path tests below can drive them
directly. The control arm (first_tranche_pct = 0) is a first-class path here,
not a later bolt-on: step 8 needs it to price what scaling out actually costs.

FILL REALISM (close-only data)
------------------------------
This panel has close prices only. A stop is therefore *detected* at a close
and can only be *filled* at that close -- there is no intraday path to fill at
the stop level itself. So exits fill at the close that breached, which is
worse than the stop level. That is the conservative direction and it is the
honest one for this data; a backtest that filled at the stop price would be
claiming an execution it cannot demonstrate.

Same reason the ATR is a close-to-close proxy (see data_loader.atr_proxy): the
initial stop reads tighter than a true-range ATR stop would.
"""

from __future__ import annotations

import numpy as np
from numba import njit

# Exit reason codes (kept as ints for Numba).
EXIT_NONE = 0
EXIT_INITIAL_STOP = 1
EXIT_TRAIL = 2
EXIT_BREAKEVEN = 3
EXIT_SCALE_OUT = 4          # partial, position stays open
EXIT_END_OF_DATA = 5
EXIT_DERISK = 6            # partial, forced by a regime downgrade

EXIT_NAMES = {
    EXIT_NONE: "none",
    EXIT_INITIAL_STOP: "initial_stop",
    EXIT_TRAIL: "trailing_stop",
    EXIT_BREAKEVEN: "breakeven_stop",
    EXIT_SCALE_OUT: "scale_out_1R",
    EXIT_END_OF_DATA: "end_of_data",
    EXIT_DERISK: "regime_derisk",
}


@njit(cache=True)
def initial_stop_long(entry_price, atr, atr_mult):
    """3.0 x ATR below entry. Falls back to a 10% stop if ATR is unusable."""
    if atr <= 0.0 or np.isnan(atr):
        return entry_price * 0.90
    stop = entry_price - atr * atr_mult
    if stop <= 0.0:
        stop = entry_price * 0.90
    return stop


@njit(cache=True)
def step_position(price, entry_price, stop, stop_kind, peak, scaled, r_dist,
                  trail_pct, activation_pct, trigger_rr, min_move_pct,
                  first_tranche_pct, move_stop_to_be):
    """
    Advance one open long position by one bar.

    Order of operations matters and is deliberate:
      1. Test the stop CARRIED INTO this bar -- not one widened by this same
         bar's price. Updating the trail first and then testing it would let a
         position survive a bar it should have been stopped out on, which
         flatters every downside statistic in the run.
      2. Only if it survives: update peak, fire the scale-out, widen the trail.

    `stop_kind` tracks WHY the current stop is where it is, so the exit reason
    is recorded rather than inferred from level comparisons:
        0 = initial ATR stop, 1 = moved to breakeven, 2 = trailing

    Returns (action, fill_price, fraction, new_stop, new_stop_kind,
             new_peak, new_scaled)
      action   = EXIT_*
      fraction = portion of the CURRENT position closed by this action
    """
    # --- 1. stop test against the level carried into the bar --------------
    if price <= stop:
        if stop_kind == 2:
            reason = EXIT_TRAIL
        elif stop_kind == 1:
            reason = EXIT_BREAKEVEN
        else:
            reason = EXIT_INITIAL_STOP
        return reason, price, 1.0, stop, stop_kind, peak, scaled

    new_peak = peak if peak > price else price
    new_stop = stop
    new_kind = stop_kind
    new_scaled = scaled
    action = EXIT_NONE
    frac = 0.0

    # --- 2. scale-out at +trigger_rr, gated by min_move_pct ---------------
    if new_scaled == 0 and first_tranche_pct > 0.0:
        hit_r = (price - entry_price) >= r_dist * trigger_rr
        # min_move_pct is a HARD GATE on the trigger, not a size adjustment.
        # 1R is ATR-scaled, so on SPY 1R is +1.82% -- without this floor the
        # equity sleeve books a "win" on sub-2% noise and inflates profit
        # factor through turnover alone.
        big_enough = (price / entry_price - 1.0) * 100.0 >= min_move_pct
        if hit_r and big_enough:
            action = EXIT_SCALE_OUT
            frac = first_tranche_pct / 100.0
            new_scaled = 1
            if move_stop_to_be == 1 and entry_price > new_stop:
                new_stop = entry_price
                new_kind = 1

    # --- 3. trailing stop on the runner -----------------------------------
    if (new_peak / entry_price - 1.0) * 100.0 >= activation_pct:
        cand = new_peak * (1.0 - trail_pct / 100.0)
        if cand > new_stop:
            new_stop = cand
            new_kind = 2

    return action, price, frac, new_stop, new_kind, new_peak, new_scaled
