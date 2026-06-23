from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_fundamentals,
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_news,
    get_stock_data,
    get_verified_market_snapshot,
)


def create_crypto_equities_analyst(llm):

    def crypto_equities_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
            get_fundamentals,
            get_news,
        ]

        system_message = (
            "You are a specialist analyst covering crypto-exposed equities — publicly"
            " traded stocks whose value is substantially driven by digital-asset"
            " markets. This universe includes (but is not limited to):"
            "\n"
            "  • **Bitcoin treasury companies**: MicroStrategy (MSTR) and peers that"
            " hold BTC on their balance sheet."
            "\n"
            "  • **Crypto-native exchanges & brokers**: Coinbase (COIN)."
            "\n"
            "  • **Bitcoin miners**: Marathon Digital (MARA), Riot Platforms (RIOT),"
            " CleanSpark (CLSK), Hut 8 (HUT), Iris Energy (IREN), and sector peers."
            "\n"
            "  • **Crypto infrastructure & fintech**: companies providing custody,"
            " staking, settlement, or blockchain tooling."
            "\n\n"
            "Produce a comprehensive equity research report covering:"
            "\n\n"
            "1. **Crypto-asset sensitivity** — quantify the company's exposure:"
            " BTC/ETH holdings per share (for treasury plays), mined BTC per day"
            " and hash-rate capacity (for miners), or trading-volume / fee-revenue"
            " correlation with crypto market cap (for exchanges)."
            "\n"
            "2. **Premium / discount analysis** — compare equity market cap to the"
            " market value of crypto holdings (mNAV). A premium signals speculation"
            " on operational leverage or option value; a discount signals a buying"
            " opportunity or structural concern."
            "\n"
            "3. **Operating fundamentals** — call get_fundamentals for balance sheet"
            " strength, revenue trend, and cost structure. For miners: focus on"
            " cost-to-mine, fleet efficiency (J/TH), and energy mix."
            "\n"
            "4. **News & regulatory context** — call get_news for recent headlines."
            " Flag any SEC actions, exchange delistings, halving-cycle timing, or"
            " macro crypto regulation that affects this name."
            "\n"
            "5. **Technical picture** — select 5–7 indicators from:"
            " close_50_sma, close_200_sma, close_10_ema, rsi, macd, macds, macdh,"
            " boll, boll_ub, boll_lb, atr, vwma. Call get_stock_data first, then"
            " get_indicators."
            "\n"
            "6. **Peer comparison** — rank this name against 2–3 direct peers on:"
            " BTC-sensitivity beta, revenue growth, balance-sheet leverage, and"
            " 3-month relative performance."
            "\n"
            "7. **Actionable thesis** — explicit BUY / HOLD / REDUCE recommendation"
            " with entry price, stop-loss, price target, and the key catalyst or"
            " risk event on the near-term horizon."
            "\n\n"
            "Before writing the final report, call get_verified_market_snapshot for"
            " the ticker and current date; use it as ground truth for price and OHLCV"
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
            "crypto_equities_report": report,
        }

    return crypto_equities_analyst_node
