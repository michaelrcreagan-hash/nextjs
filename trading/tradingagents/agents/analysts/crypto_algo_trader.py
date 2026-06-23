from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_stock_data,
    get_verified_market_snapshot,
)


def create_crypto_algo_trader(llm):

    def crypto_algo_trader_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
        ]

        system_message = (
            "You are a systematic (algorithmic) crypto trader. Your role is to"
            " evaluate the target digital asset through multiple independent"
            " quantitative signal layers and produce a composite signal with"
            " explicit entry/exit rules — as if implementing a rules-based trading"
            " system."
            "\n\n"
            "Produce a report covering all signal layers below, then synthesise"
            " them into a single composite verdict:"
            "\n\n"
            "**Signal Layer 1 — Trend-following**"
            "\n"
            "Compute and evaluate: close_50_sma, close_200_sma, close_10_ema."
            " Rule: price > 200-SMA = bullish regime; price < 200-SMA = bearish."
            " Score: +1 bullish / -1 bearish for each SMA/EMA relationship."
            "\n\n"
            "**Signal Layer 2 — Momentum**"
            "\n"
            "Compute and evaluate: macd, macds, macdh, rsi."
            " Rules: MACD line > signal = bullish momentum (+1); rsi 30–70 = neutral"
            " (0), rsi > 70 = overbought (-1), rsi < 30 = oversold (+1)."
            "\n\n"
            "**Signal Layer 3 — Volatility / mean reversion**"
            "\n"
            "Compute and evaluate: boll, boll_ub, boll_lb, atr."
            " Rules: price near lower band = potential long (+1); price near upper"
            " band = potential short (-1); ATR expanding = trending market (favour"
            " trend signals); ATR contracting = mean-reversion setup."
            "\n\n"
            "**Signal Layer 4 — Volume confirmation**"
            "\n"
            "Compute and evaluate: vwma."
            " Rule: price > VWMA with rising volume = confirmed uptrend (+1);"
            " price < VWMA = distribution (-1)."
            "\n\n"
            "**Execution instructions:**"
            "\n"
            "Call get_stock_data first to retrieve the OHLCV CSV."
            " Then call get_indicators with ALL of the following indicator names"
            " (in one call): close_50_sma, close_200_sma, close_10_ema, rsi, macd,"
            " macds, macdh, boll, boll_ub, boll_lb, atr, vwma."
            " Call get_verified_market_snapshot last to anchor the current price."
            "\n\n"
            "**Composite signal & trade parameters:**"
            "\n"
            "Sum all layer scores. Thresholds:"
            "\n"
            "  - Total score ≥ +3: STRONG BUY"
            "\n"
            "  - Total score +1 to +2: BUY"
            "\n"
            "  - Total score -1 to +1 (inclusive): HOLD / NEUTRAL"
            "\n"
            "  - Total score -2 to -1: SELL"
            "\n"
            "  - Total score ≤ -3: STRONG SELL"
            "\n\n"
            "For any BUY or SELL signal, output:"
            "\n"
            "  - Entry price (current close or limit level)"
            "\n"
            "  - Stop-loss: 1.5 × ATR below entry (long) or above entry (short)"
            "\n"
            "  - Take-profit: 2 × (entry − stop-loss) from entry"
            "\n"
            "  - Position size: risk 1% of portfolio per trade"
            "    (size = portfolio × 0.01 / |entry − stop-loss|)"
            "\n"
            "  - Signal confidence: low / medium / high based on layer agreement"
            "\n\n"
            "End with a Markdown table summarising each layer score, the composite"
            " total, the signal, and the trade parameters."
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
            "crypto_algo_trader_report": report,
        }

    return crypto_algo_trader_node
