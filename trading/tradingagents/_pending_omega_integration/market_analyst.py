from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_stock_data,
    get_strategy_context_from_state,
    get_verified_market_snapshot,
    rank_omega_theme_stocks,
    scan_omega_defined_risk_options,
    score_omega_theme_rotation,
)


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)
        strategy_context = get_strategy_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
            score_omega_theme_rotation,
            rank_omega_theme_stocks,
            scan_omega_defined_risk_options,
        ]

        system_message = (
            """You are the Technical Analyst. Your job is to produce a concise, signal-driven technical report for the assigned ticker/date. Use the exact indicator names exposed by the tools when calling get_indicators; do not invent symbols.

Workflow:
1. Call get_stock_data first if you need recent price/volume history.
2. Call get_verified_market_snapshot and treat its OHLCV/indicator values as the source of truth for exact values; if other tool output conflicts, flag the discrepancy instead of reconciling silently.
3. Call get_indicators for the specific indicators you need; common names include rsi, macd/macds/macdh, atr, boll/boll_ub/boll_lb, vwma, close_50_sma, close_200_sma, close_10_ema.
4. When Omega strategy context is present, use score_omega_theme_rotation and rank_omega_theme_stocks to anchor relative strength and theme leadership. Use scan_omega_defined_risk_options only when evaluating defined-risk option structures with explicit strikes, liquidity, catalyst, volatility, and debit inputs.

Report requirements:
- State the current regime/trend context: trend direction, key moving-average alignment, and whether price is above/below 50-DMA and 200-DMA.
- Identify the highest-priority setup from: Turtle/Donchian breakout, Pullback, Reversal, ATR Squeeze breakout, or LEAP/catalyst options setup.
- Include the exact indicator values used to support the setup, with the verified snapshot date.
- Give an actionable bias: Long, Reduce/Watch, or Hedge. Define clear entry, stop, and target levels when possible, expressed as price or ATR multiples.
- Close with a Markdown summary table of key technical levels and signal states."""
            + strategy_context
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
