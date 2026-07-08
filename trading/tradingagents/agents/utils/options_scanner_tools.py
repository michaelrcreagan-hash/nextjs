import json
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.strategies import (
    OptionBias,
    OptionCandidate,
    OptionStructure,
    scan_defined_risk_options,
)

def _json_default(value):
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)

@tool
def scan_omega_defined_risk_options(
    candidates_json: Annotated[
        str,
        (
            "JSON list of option candidates. Required fields: ticker, structure, bias, "
            "expiry, dte, underlying_price, long_strike, net_debit. Optional fields "
            "include short_strike, implied_vol, realized_vol, bid_ask_spread_pct, "
            "open_interest, volume, catalyst_score, theme_score, technical_score."
        ),
    ],
    min_reward_to_risk: Annotated[float, "Minimum acceptable reward-to-risk ratio"] = 2.0,
    max_loss_pct_underlying: Annotated[float, "Max option max-loss as percent of underlying"] = 12.0,
) -> str:
    """Rank defined-risk options for asymmetric Omega trade expressions."""
    raw_candidates = json.loads(candidates_json)
    candidates = [
        OptionCandidate(
            **{
                **raw,
                "structure": OptionStructure(raw["structure"]),
                "bias": OptionBias(raw["bias"]),
            }
        )
        for raw in raw_candidates
    ]
    results = scan_defined_risk_options(
        candidates,
        min_reward_to_risk=min_reward_to_risk,
        max_loss_pct_underlying=max_loss_pct_underlying,
    )
    return json.dumps(results, default=_json_default, sort_keys=True)