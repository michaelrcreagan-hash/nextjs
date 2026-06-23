from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_stock_data,
    get_verified_market_snapshot,
)


def create_options_analyst(llm):

    def options_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
        ]

        system_message = (
            "You are a specialist options analyst focused on defined-risk strategies"
            " and long-dated (LEAPS) positioning. Produce a thorough options research"
            " report covering:"
            "\n\n"
            "1. **Volatility landscape** — estimate current implied volatility (IV)"
            " relative to recent historical volatility (HV) using ATR and price range"
            " data. Classify IV environment: compressed (< 25th percentile),"
            " normal, or elevated (> 75th percentile). State whether conditions"
            " favour buying or selling premium."
            "\n"
            "2. **Key price levels** — identify nearest support and resistance using"
            " Bollinger Bands, 50-SMA, 200-SMA, and recent swing highs/lows."
            " These anchor strike selection."
            "\n"
            "3. **Defined-risk structures** — for each directional bias (bullish,"
            " bearish, neutral), recommend one or two defined-risk trades:"
            "\n"
            "   - **Debit spreads** (bull call spread / bear put spread): state"
            " expiry, strikes, max risk, max reward, breakeven."
            "\n"
            "   - **Credit spreads** (bull put spread / bear call spread): state"
            " expiry, strikes, premium received, max risk, breakeven."
            "\n"
            "   - **Iron condor / iron butterfly** for range-bound conditions."
            "\n"
            "4. **LEAPS strategy** — recommend one LEAPS position (≥ 12 months to"
            " expiry) for long-term directional exposure with capped downside:"
            " state target strike (preferably 70–90 delta), expiry, rationale,"
            " and how it compares to holding shares outright."
            "\n"
            "5. **Technical confirmation** — select 5–7 indicators from:"
            " close_50_sma, close_200_sma, close_10_ema, rsi, macd, macds, macdh,"
            " boll, boll_ub, boll_lb, atr. Call get_stock_data first, then"
            " get_indicators. Use them to confirm or invalidate the directional bias."
            "\n"
            "6. **Risk management rules** — position sizing (% of portfolio per trade),"
            " stop-loss triggers, roll/adjustment criteria."
            "\n"
            "7. **Actionable summary** — rank the top 2 trades by risk-adjusted appeal;"
            " include specific entry conditions and catalyst timeline."
            "\n\n"
            "Before writing the final report, call get_verified_market_snapshot for"
            " the ticker and current date; use it as ground truth for price-level"
            " claims. End with a Markdown summary table."
        ) + get_language_instruction()

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
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
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
            "options_report": report,
        }

    return options_analyst_node
