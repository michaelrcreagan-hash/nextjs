from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_news,
    get_stock_data,
    get_verified_market_snapshot,
)


def create_etf_analyst(llm):

    def etf_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
            get_news,
        ]

        system_message = (
            "You are a specialist ETF analyst. Your job is to produce a comprehensive"
            " research report on the target ETF (or ETF-eligible equity) covering:"
            "\n\n"
            "1. **Price & NAV dynamics** — current price versus intraday indicative NAV;"
            " premium/discount trend over the past 30 days; creation/redemption activity."
            "\n"
            "2. **Sector & factor exposure** — top-10 holdings (weight, ticker, sector);"
            " factor tilts (value, growth, momentum, quality, low-vol); geographic split."
            "\n"
            "3. **Fund flows & AUM** — recent inflow/outflow trend; AUM trajectory;"
            " impact on liquidity and bid-ask spread."
            "\n"
            "4. **Benchmark tracking** — tracking error vs stated benchmark;"
            " expense ratio drag; dividend yield and distribution schedule."
            "\n"
            "5. **Technical picture** — select up to 6 complementary indicators from:"
            " close_50_sma, close_200_sma, close_10_ema, rsi, macd, macds, macdh,"
            " boll, boll_ub, boll_lb, atr, vwma. Call get_stock_data first to retrieve"
            " the CSV, then get_indicators with the chosen indicator names."
            "\n"
            "6. **Relative strength** — performance vs SPY, QQQ, and the relevant"
            " sector SPDR over 1-week, 1-month, and 3-month windows."
            "\n"
            "7. **Actionable thesis** — explicit BUY / HOLD / REDUCE recommendation"
            " with entry zone, stop-loss level, and near-term catalyst."
            "\n\n"
            "Before writing the final report, call get_verified_market_snapshot for"
            " the ticker and current date; treat it as ground truth for all OHLCV and"
            " price-level claims. Flag any discrepancies rather than reconciling silently."
            " End every report with a Markdown summary table."
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
            "etf_report": report,
        }

    return etf_analyst_node
