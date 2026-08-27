"""
Step 3 verification: hand-constructed synthetic paths that hit each exit in
isolation, with the exact bar and price asserted.

BUILD_PLAN.md step 3 requires exactly these four, plus the min_move_pct gate
and the control-arm equivalence. Run: python3 -m src.test_exits
"""

import numpy as np

from .exits import (EXIT_NONE, EXIT_INITIAL_STOP, EXIT_TRAIL, EXIT_BREAKEVEN,
                    EXIT_SCALE_OUT, step_position, initial_stop_long)

# Baseline params matching config.yaml.
P = dict(trail_pct=20.0, activation_pct=5.0, trigger_rr=1.0,
         min_move_pct=3.0, first_tranche_pct=50.0, move_stop_to_be=1)


def walk(prices, entry, stop, **over):
    """Drive step_position across a path; return the list of (bar, action, price)."""
    p = {**P, **over}
    r_dist = entry - stop
    st, kind, peak, scaled = stop, 0, entry, 0
    events = []
    for i, px in enumerate(prices):
        act, fill, frac, st, kind, peak, scaled = step_position(
            px, entry, st, kind, peak, scaled, r_dist,
            p["trail_pct"], p["activation_pct"], p["trigger_rr"],
            p["min_move_pct"], p["first_tranche_pct"], p["move_stop_to_be"])
        if act != EXIT_NONE:
            events.append((i, act, fill, frac, st))
            if act != EXIT_SCALE_OUT:
                break
    return events, st


def t_initial_stop():
    entry, stop = 100.0, 90.0            # 1R = 10
    ev, _ = walk([99, 95, 91, 89.5], entry, stop)
    assert len(ev) == 1, ev
    bar, act, fill, frac, _ = ev[0]
    assert act == EXIT_INITIAL_STOP, act
    assert bar == 3 and fill == 89.5 and frac == 1.0, ev
    print("  initial ATR stop      : bar 3 @ 89.50, full exit          PASS")


def t_scale_out_and_breakeven():
    entry, stop = 100.0, 90.0            # 1R = 10 -> trigger at 110 (+10%)
    ev, st = walk([104, 108, 110.5, 99.0], entry, stop)
    assert ev[0][1] == EXIT_SCALE_OUT and ev[0][0] == 2, ev
    assert abs(ev[0][3] - 0.5) < 1e-12, ev
    assert abs(st - 100.0) < 1e-9 or st > 88.0, st
    # After the scale-out the runner's stop is breakeven (100), so bar 3 at 99
    # must close the runner as a breakeven exit.
    assert ev[1][1] == EXIT_BREAKEVEN and ev[1][0] == 3 and ev[1][2] == 99.0, ev
    print("  1R scale-out          : bar 2, 50% @ 110.50               PASS")
    print("  breakeven on runner   : bar 3 @ 99.00, full exit          PASS")


def t_trailing_stop():
    entry, stop = 100.0, 90.0
    # Run to 150 (peak), trail = 20% -> 120. No scale-out (control arm) so the
    # trail is the only exit mechanism in play.
    ev, _ = walk([110, 130, 150, 125, 119], entry, stop, first_tranche_pct=0.0)
    assert len(ev) == 1, ev
    bar, act, fill, frac, _ = ev[0]
    assert act == EXIT_TRAIL, act
    assert bar == 4 and fill == 119.0 and frac == 1.0, ev
    print("  trailing stop @20%    : bar 4 @ 119.00 (peak 150 -> 120)  PASS")


def t_min_move_gate():
    """SPY-like: tight ATR makes 1R only +1.8%, below the 3.0% floor."""
    entry, stop = 100.0, 98.2            # 1R = 1.8 -> trigger at 101.8 (+1.8%)
    # Path stays strictly under the 3.0% floor. (An earlier version of this
    # fixture ran to 103.0, i.e. exactly +3.0%, which CLEARS the floor -- the
    # gate is >=, so it correctly fired. The gate was right; the path was wrong.)
    ev, _ = walk([101.0, 102.0, 102.5], entry, stop)
    assert all(a != EXIT_SCALE_OUT for _, a, _, _, _ in ev), ev
    print("  min_move_pct gate     : +2.5% move does NOT scale out     PASS")
    # Same setup, floor lowered to 1.0 -> the scale-out now fires, proving the
    # gate and not something else was what suppressed it.
    ev2, _ = walk([101.0, 102.0], entry, stop, min_move_pct=1.0)
    assert ev2 and ev2[0][1] == EXIT_SCALE_OUT and ev2[0][0] == 1, ev2
    print("  gate is the cause     : floor 1.0% -> fires at bar 1      PASS")


def t_control_arm_is_pure_trail():
    """first_tranche_pct=0 must be identical to a pure trailing-stop path."""
    entry, stop = 100.0, 90.0
    path = [104, 108, 112, 140, 160, 130, 127]
    ev_ctrl, _ = walk(path, entry, stop, first_tranche_pct=0.0)
    # Reference: trail only, computed independently here.
    peak, st = entry, stop
    ref = None
    for i, px in enumerate(path):
        if px <= st:
            ref = (i, px)
            break
        peak = max(peak, px)
        if (peak / entry - 1) * 100 >= P["activation_pct"]:
            st = max(st, peak * (1 - P["trail_pct"] / 100))
    assert len(ev_ctrl) == 1 and (ev_ctrl[0][0], ev_ctrl[0][2]) == ref, (ev_ctrl, ref)
    print(f"  control arm == trail  : bar {ref[0]} @ {ref[1]:.2f}                  PASS")


def t_stop_before_trail_ordering():
    """
    A bar that breaches the carried stop must exit, even though that same
    bar's price would (if processed first) have widened the trail. Getting
    this backwards silently flatters every downside statistic.
    """
    entry, stop = 100.0, 90.0
    ev, _ = walk([150, 89.0], entry, stop, first_tranche_pct=0.0)
    # After bar 0 the trail sits at 120. Bar 1 at 89 breaches it.
    assert len(ev) == 1 and ev[0][0] == 1 and ev[0][1] == EXIT_TRAIL, ev
    print("  stop tested before trail update                           PASS")


def t_atr_fallback():
    assert initial_stop_long(100.0, 0.0, 3.0) == 90.0
    assert initial_stop_long(100.0, np.nan, 3.0) == 90.0
    assert initial_stop_long(100.0, 50.0, 3.0) == 90.0   # would go negative
    assert abs(initial_stop_long(100.0, 2.0, 3.0) - 94.0) < 1e-12
    print("  ATR fallback guards   : 0 / NaN / negative -> 10% stop    PASS")


if __name__ == "__main__":
    print("Step 3 exit-engine synthetic path tests")
    print("-" * 60)
    t_initial_stop()
    t_scale_out_and_breakeven()
    t_trailing_stop()
    t_min_move_gate()
    t_control_arm_is_pure_trail()
    t_stop_before_trail_ordering()
    t_atr_fallback()
    print("-" * 60)
    print("all exit-engine tests PASS")
