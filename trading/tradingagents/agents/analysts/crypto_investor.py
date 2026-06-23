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


def create_crypto_investor(llm):

    def crypto_investor_node(state):
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
            "You are a long-term crypto investor with a multi-month to multi-year"
            " time horizon. Your role is to evaluate whether the target digital asset"
            " deserves a core portfolio allocation and at what sizing, based on"
            " fundamental value and macro cycle positioning."
            "\n\n"
            "Produce a comprehensive investment thesis covering:"
            "\n\n"
            "1. **Asset fundamentals** — describe the asset's core value proposition:"
            " monetary asset (BTC), smart contract platform (ETH, SOL), DeFi protocol"
            " token, L2 token, or other. Summarise the network's utility, security"
            " model, and competitive moat."
            "\n"
            "2. **On-chain & supply metrics** — assess tokenomics: total supply, FDV"
            " vs circulating market cap, inflation/deflation schedule, vesting cliff"
            " risk, and any burn mechanisms. Use get_fundamentals where available."
            "\n"
            "3. **Adoption & network growth** — evaluate network activity trends:"
            " active addresses, transaction volumes, developer commits, TVL (for DeFi"
            " protocols), and real-world user growth signals surfaced by get_news."
            "\n"
            "4. **Macro cycle positioning** — identify where this asset sits in the"
            " broader crypto market cycle (accumulation, bull run, distribution,"
            " bear market). Reference BTC dominance trends and historical halving"
            " cycle patterns where relevant."
            "\n"
            "5. **Valuation framework** — apply one or more valuation lenses:"
            "\n"
            "   - **Stock-to-flow / scarcity model** for BTC"
            "\n"
            "   - **Network value to transactions (NVT)** ratio"
            "\n"
            "   - **Price-to-earnings or P/S** for protocol fee-generating assets"
            "\n"
            "   - **Relative value** vs comparable assets in the same category"
            "\n"
            "6. **Technical long-term picture** — call get_stock_data then"
            " get_indicators with close_200_sma, close_50_sma, rsi, macd, atr."
            " Assess whether the asset is above or below its 200-SMA, and whether"
            " it is historically cheap or expensive on a weekly RSI basis."
            "\n"
            "7. **Risk factors** — name the top three risks: regulatory, competitive,"
            " technical (smart contract exploit, consensus failure), liquidity, and"
            " macro (risk-off deleveraging)."
            "\n"
            "8. **Investment recommendation** — ACCUMULATE / HOLD / REDUCE / AVOID"
            " with:"
            "\n"
            "   - Suggested portfolio allocation range (e.g. 2–5% of total portfolio)"
            "\n"
            "   - Preferred accumulation zone (price range)"
            "\n"
            "   - 12-month and 3-year price thesis"
            "\n"
            "   - Key catalysts to monitor"
            "\n\n"
            "Before writing the final report, call get_verified_market_snapshot for"
            " the ticker and current date; use it as ground truth for current price."
            " End with a Markdown summary table."
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
            "crypto_investor_report": report,
        }

    return crypto_investor_node
