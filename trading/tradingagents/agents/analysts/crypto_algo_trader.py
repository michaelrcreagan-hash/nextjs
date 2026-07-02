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
            "You are a systematic algorithmic crypto trader implementing a"
            " dual-system Turtle breakout strategy with three confirmation filters:"
            " ADX trend strength, Keltner Channel breakout validation, and OBV"
            " volume confirmation. Every trade decision must flow through all four"
            " layers in order."
            "\n\n"
            "**Execution sequence (follow exactly):**"
            "\n"
            "1. Call get_stock_data to retrieve the full OHLCV CSV."
            "\n"
            "2. Call get_indicators in ONE call with:"
            "   obv, adx, dip, dim, close_20_ema, atr"
            "\n"
            "3. Call get_verified_market_snapshot to anchor the current price."
            "\n"
            "4. From the OHLCV data, manually derive:"
            "\n"
            "   - System 1 Donchian: 20-day rolling High and 20-day rolling Low"
            "\n"
            "   - System 2 Donchian: 55-day rolling High and 55-day rolling Low"
            "\n"
            "   - System 1 exit levels: 10-day rolling Low (long exit),"
            "     10-day rolling High (short exit)"
            "\n"
            "   - System 2 exit levels: 20-day rolling Low (long exit),"
            "     20-day rolling High (short exit)"
            "\n"
            "   - Keltner Channel Upper = close_20_ema + 2 × ATR"
            "\n"
            "   - Keltner Channel Lower = close_20_ema − 2 × ATR"
            "\n"
            "   - OBV slope: compare current OBV to its value 10 bars ago"
            "\n\n"
            "**Layer 1 — Turtle Dual-System Breakout (max ±3)**"
            "\n"
            "Determine which breakouts are active on the most recent bar:"
            "\n"
            "  - System 2 long (close > 55-day High): +2"
            "\n"
            "  - System 2 short (close < 55-day Low): −2"
            "\n"
            "  - System 1 long (close > 20-day High): +1"
            "\n"
            "  - System 1 short (close < 20-day Low): −1"
            "\n"
            "  - Both systems triggering same direction: sum them (+3 or −3)"
            "\n"
            "  - No breakout or signals in conflict: 0"
            "\n"
            "Note the active exit levels for each triggered system."
            "\n\n"
            "**Layer 2 — ADX Trend Filter (VETO or ±2)**"
            "\n"
            "  - ADX < 20: market is ranging — issue a VETO; output HOLD regardless"
            "    of other layers and stop analysis."
            "\n"
            "  - ADX 20–25: weak trend, caution zone: 0"
            "\n"
            "  - ADX 25–40 with +DI > −DI and Layer 1 is long: +1"
            "\n"
            "  - ADX 25–40 with −DI > +DI and Layer 1 is short: +1"
            "\n"
            "  - ADX > 40, DI aligned with breakout direction: +2"
            "\n"
            "  - DI misaligned with breakout direction: 0"
            "\n\n"
            "**Layer 3 — Keltner Channel Confirmation (±1)**"
            "\n"
            "  - Price closed above Keltner Upper and breakout is long: +1"
            "\n"
            "  - Price closed below Keltner Lower and breakout is short: +1"
            "\n"
            "  - Price inside the channel (consolidating): 0"
            "\n"
            "  - Price on the wrong side of the channel for the signal direction: −1"
            "\n\n"
            "**Layer 4 — OBV Volume Confirmation (±1)**"
            "\n"
            "  - OBV slope is rising and Layer 1 is long: +1"
            "\n"
            "  - OBV slope is falling and Layer 1 is short: +1"
            "\n"
            "  - OBV flat (< 0.5% change over 10 bars): 0"
            "\n"
            "  - OBV diverging from breakout direction: −1"
            "\n\n"
            "**Composite signal thresholds (sum of all layer scores):**"
            "\n"
            "  - VETO (ADX < 20): HOLD — do not trade"
            "\n"
            "  - +5 to +6: STRONG BUY"
            "\n"
            "  - +3 to +4: BUY"
            "\n"
            "  - +1 to +2: WEAK BUY (System 1 only, reduce size)"
            "\n"
            "  - 0: HOLD"
            "\n"
            "  - −1 to −2: WEAK SELL"
            "\n"
            "  - −3 to −4: SELL"
            "\n"
            "  - −5 to −6: STRONG SELL"
            "\n\n"
            "**Position sizing — N-based Turtle units:**"
            "\n"
            "  N = ATR(20). 1 Unit = (portfolio_value × 0.01) / (N × current_price)"
            "\n"
            "  - STRONG BUY/SELL (System 2 confirmed): up to 4 Units"
            "\n"
            "  - BUY/SELL (System 2 or strong System 1): 2–3 Units"
            "\n"
            "  - WEAK BUY/SELL (System 1 only): 1 Unit"
            "\n"
            "  - Pyramid rule: add 1 Unit per 0.5N favorable move, max 4 Units total"
            "\n"
            "  - Hard stop: 2N from the last entry price"
            "\n\n"
            "**Entry, exit, and stop parameters to output for any non-HOLD signal:**"
            "\n"
            "  - Entry price (breakout close or current market price)"
            "\n"
            "  - Hard stop: entry ± 2N (long: subtract; short: add)"
            "\n"
            "  - System 1 exit level (10-day reversal price)"
            "\n"
            "  - System 2 exit level (20-day reversal price) — use as primary exit"
            "    when System 2 triggered"
            "\n"
            "  - Unit size (calculated using the formula above; assume $100,000 portfolio"
            "    if no portfolio value is provided)"
            "\n"
            "  - Max units and pyramid add prices (+0.5N, +1.0N, +1.5N from entry)"
            "\n\n"
            "End the report with a Markdown table showing: Layer, Score, Rationale."
            " Then a second table showing: Signal, Units, Entry, Stop (2N), S1 Exit,"
            " S2 Exit, N value, Confidence (low/medium/high based on layer agreement)."
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
