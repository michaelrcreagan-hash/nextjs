"""
The AI bottleneck universe, defined by FUNCTION rather than by performance.

THE TRAP THIS FILE EXISTS TO AVOID
----------------------------------
The task asks to "use the top performing stocks from 2022 to 2026 to determine
the optimal signals." Taken literally that is the single most effective way to
produce a beautiful backtest that makes no money: if the universe is chosen by
knowing who won, then any signal correlated with having won will appear to
work, and the study measures nothing but the selection.

So the universe here is built from a structural question that could have been
asked on 2022-01-01 with no knowledge of the outcome:

    Where in the AI buildout is supply physically constrained, so that demand
    growth shows up as pricing power rather than as share loss?

Every name below sits at such a chokepoint, and each is tagged with the layer
it constrains. Winners and losers are both in here on purpose -- INTC, WDC and
IPGP are bottleneck-adjacent names that badly underperformed, and a study that
quietly omitted them would be measuring hindsight.

The top performers are still used, but only in the role they can honestly play:
to GENERATE hypotheses about which fundamentals mattered (§ eda). Those
hypotheses are then TESTED on the full universe with point-in-time data.

LISTING DATES
-------------
Several of the most important names listed mid-period: ARM (2023-09), GEV
(2024-04), ALAB (2024-03), OKLO (2024-05), TLN (2023-12), SMR (2022-05).
Dropping them would bias the universe toward incumbents and silently remove
some of the largest moves in the sample. They are included, and are simply
absent (NaN) before their first trade -- the backtest must handle a universe
whose membership grows over time, because that is what the real one does.
"""

from __future__ import annotations

# layer -> (why it is a bottleneck, [tickers])
LAYERS = {
    "compute_silicon": (
        "Accelerator and networking silicon; the design-side chokepoint.",
        ["NVDA", "AMD", "AVGO", "MRVL", "INTC", "QCOM"]),

    "foundry": (
        "Leading-edge wafer capacity. Physically capped and years to expand.",
        ["TSM", "UMC", "GFS"]),

    "semicap": (
        "The tools that make the capacity. EUV is a literal monopoly.",
        ["ASML", "AMAT", "LRCX", "KLAC", "TER", "ONTO", "ACLS", "CAMT", "AEIS"]),

    "memory_hbm": (
        "HBM stacks gate accelerator shipments; supply sold out years ahead.",
        ["MU", "WDC", "STX"]),

    "optics_network": (
        "Optical interconnect and switching -- the scale-out chokepoint.",
        ["ANET", "CIEN", "COHR", "LITE", "ALAB", "CRDO", "FN"]),

    "power_electrical": (
        "Thermal, switchgear, busway. Became the binding constraint in 2024.",
        ["VRT", "ETN", "PWR", "GEV", "POWL", "ATKR", "NVT", "HUBB", "AME", "MOD"]),

    "power_generation": (
        "Electrons themselves; interconnect queues are the hard limit.",
        ["CEG", "VST", "TLN", "NRG", "OKLO", "SMR", "LEU", "CCJ"]),

    "eda_ip": (
        "Design tools and CPU IP. Two-and-a-half firms, enormous moats.",
        ["CDNS", "SNPS", "ARM"]),

    "materials_subsystems": (
        "Advanced materials, gases, subfab. Qualification takes years.",
        ["ENTG", "MKSI", "UCTT", "IPGP", "LIN", "APD"]),

    "systems_integration": (
        "Rack-scale integration and liquid cooling at volume.",
        ["SMCI", "DELL", "HPE", "PSTG"]),

    "packaging_test": (
        "Advanced packaging (CoWoS-class) -- the tightest 2023-24 constraint.",
        ["AMKR"]),

    "datacenter_reit": (
        "Powered shells and interconnection density.",
        ["EQIX", "DLR"]),
}

BENCH = ["SPY", "QQQ", "SMH", "XLU"]     # market, tech, semis, utilities

TICKERS = sorted({t for _, syms in LAYERS.values() for t in syms})
LAYER_OF = {t: lay for lay, (_, syms) in LAYERS.items() for t in syms}

# Names that listed after 2022-01-01, with the first date whose price is real.
# These are ENFORCED as hard truncation points, not merely asserted, because
# the first fetch showed Yahoo happily serving pre-listing history for several
# of them:
#
#   OKLO  came back with bars from 2021-07 and SMR from 2022-03 -- both went
#         public by SPAC merger, so those bars are the pre-merger shell (AltC
#         and Spring Valley respectively) trading flat around $10. Measuring a
#         return from that base manufactures a several-hundred-percent move
#         that no holder could have earned, in exactly the two names a
#         momentum screen would then fall in love with.
#   TLN   traded OTC after emerging from bankruptcy before its 2023-12 Nasdaq
#         listing; those bars are real but thin, so the listing date is used.
#   GEV   printed when-issued from 2024-03-27, a few days before the spin
#         completed. Harmless, and the earlier date is the honest one.
#
# The rule: a bar counts only if someone could have bought the actual company
# at that price on that day.
LATE_LISTINGS = {"ARM": "2023-09-14", "GEV": "2024-03-27", "ALAB": "2024-03-20",
                 "OKLO": "2024-05-10", "TLN": "2023-12-13", "SMR": "2022-05-02",
                 "CEG": "2022-01-19", "CRDO": "2022-01-27", "GFS": "2021-10-28"}

START = "2021-06-01"    # 6 months of burn-in before the 2022-01 study window
END = "2026-08-27"


if __name__ == "__main__":
    print(f"AI bottleneck universe: {len(TICKERS)} names across {len(LAYERS)} layers")
    for lay, (why, syms) in LAYERS.items():
        print(f"\n  {lay:<22s} {len(syms):>2d}  {why}")
        print(f"  {'':<22s}     {' '.join(syms)}")
    print(f"\n  benchmarks: {' '.join(BENCH)}")
    print(f"  late listings: {', '.join(f'{k} {v}' for k, v in sorted(LATE_LISTINGS.items()))}")
