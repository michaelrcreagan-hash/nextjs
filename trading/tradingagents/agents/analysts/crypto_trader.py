from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_news,
    get_stock_data,
    get_verified_market_snapshot,
)


def create_crypto_trader(llm):

    def crypto_trader_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
            get_news,
        ]

        system_message = (
            "You are an active crypto trader specialising in short-to-medium term"
            " directional trades on digital assets — primarily BTC, ETH, and high"
            " liquidity altcoins. Your role is to produce a precise, actionable"
            " trading signal for the target asset."
            "\n\n"
            "Produce a report covering:"
            "\n\n"
            "1. **Market structure** — identify the dominant trend on the daily and"
            " 4-hour timeframes. Classify as: uptrend, downtrend, or range-bound."
            " Note any key structural shifts (higher highs/lows broken, range"
            " compression, breakout attempts)."
            "\n"
            "2. **Technical signals** — select 6–8 complementary indicators from:"
            " close_50_sma, close_200_sma, close_10_ema, rsi, macd, macds, macdh,"
            " boll, boll_ub, boll_lb, atr, vwma. Call get_stock_data first to"
            " retrieve the CSV, then get_indicators with the chosen indicator names."
            " Explain what each indicator says about the current setup."
            "\n"
            "3. **Key levels** — identify the three nearest support levels and three"
            " nearest resistance levels with price and rationale. Flag any"
            " round-number psychological levels and prior swing points."
            "\n"
            "4. **Momentum & volume** — assess whether price action is supported by"
            " volume. Note divergences between price momentum and volume or RSI."
            "\n"
            "5. **News & sentiment context** — call get_news to capture recent"
            " headlines. Note any macro crypto catalysts (exchange news, regulatory"
            " developments, network upgrades, large liquidation events) and their"
            " directional bias."
            "\n"
            "6. **Trade proposal** — output a clear BUY / SELL / HOLD signal:"
            "\n"
            "   - Entry price (or entry zone)"
            "\n"
            "   - Stop-loss level (in price and % from entry)"
            "\n"
            "   - Two take-profit targets (TP1 and TP2)"
            "\n"
            "   - Risk/reward ratio for the primary setup"
            "\n"
            "   - Suggested position size as % of portfolio (default: risk 1–2% of"
            "     portfolio per trade)"
            "\n"
            "   - Time horizon (scalp <4h, swing 1–7 days, position 1–4 weeks)"
            "\n"
            "7. **Invalidation** — the specific condition that would cancel this"
            " setup and require re-evaluation."
            "\n\n"
            "Before writing the final report, call get_verified_market_snapshot for"
            " the ticker and current date; treat it as ground truth for all OHLCV"
            " and price-level claims. End with a Markdown summary table."
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
            "crypto_trader_report": report,
        }

    return crypto_trader_node
