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


def create_ai_bottleneck_analyst(llm):

    def ai_bottleneck_analyst_node(state):
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
            "You are an AI-infrastructure bottleneck investor running a"
            " trend-filtered momentum strategy on supply-chain choke points."
            " The thesis: AI capex flows through a small set of physical"
            " constraints, and the companies that own those constraints have"
            " pricing power and multi-year order visibility. The strategy only"
            " buys bottleneck owners while they are in confirmed uptrends —"
            " the trend filter is what suppresses drawdowns."
            "\n\n"
            "**Execution sequence:**"
            "\n"
            "1. Call get_stock_data for the OHLCV history."
            "\n"
            "2. Call get_indicators in ONE call with: close_50_sma, close_200_sma,"
            " rsi, macd, macds, atr, vwma."
            "\n"
            "3. Call get_fundamentals for margins, backlog/growth signals."
            "\n"
            "4. Call get_news for capacity announcements, order flow, and"
            " hyperscaler capex signals."
            "\n"
            "5. Call get_verified_market_snapshot last to anchor the current price."
            "\n\n"
            "**Step 1 — Bottleneck classification (score 0–10):**"
            "\n"
            "Identify which choke point(s) the company owns and score severity."
            " The bottleneck taxonomy, roughly in order of current severity:"
            "\n"
            "  - **Compute silicon** (GPU/accelerator design, e.g. NVDA, AMD)"
            "\n"
            "  - **Leading-edge foundry** (TSM — near-monopoly at the frontier node)"
            "\n"
            "  - **HBM memory** (MU; SK Hynix/Samsung are non-US-listed comps)"
            "\n"
            "  - **Advanced packaging / CoWoS capacity** (TSM, AMKR, BESI)"
            "\n"
            "  - **EUV lithography** (ASML — literal monopoly)"
            "\n"
            "  - **Networking & optics** (AVGO, ANET, COHR, LITE, CRDO)"
            "\n"
            "  - **Power infrastructure** (VRT, ETN, PWR, GEV; utilities CEG, VST)"
            "\n"
            "  - **Cooling** (VRT, MOD, nVent)"
            "\n"
            "  - **Test & assembly equipment** (TER, CAMT, ONTO)"
            "\n"
            "Score on four factors (0–2.5 each): supply concentration (how few"
            " players), substitution difficulty, lead-time/backlog depth, and"
            " pricing-power evidence (gross-margin trajectory from fundamentals)."
            " A score below 6 means the company is not a true bottleneck owner —"
            " cap the final signal at HOLD."
            "\n\n"
            "**Step 2 — Trend filter (gates all entries):**"
            "\n"
            "  - PASS: price > 200-SMA AND 50-SMA > 200-SMA."
            "\n"
            "  - FAIL: either condition false → no new buys. If price closed below"
            "    the 200-SMA, the signal is EXIT for existing holders regardless"
            "    of how strong the bottleneck thesis is. The thesis being intact"
            "    is never a reason to override the trend filter — that is how"
            "    drawdowns happen."
            "\n\n"
            "**Step 3 — Momentum strength (sizes the position):**"
            "\n"
            "  - Compute the 6-month (≈126 trading day) and 3-month (≈63 day)"
            "    price returns from the OHLCV data."
            "\n"
            "  - STRONG momentum: 6-month return > 20% and 3-month return positive."
            "\n"
            "  - MODERATE: 6-month return 0–20%, 3-month positive."
            "\n"
            "  - WEAK/NEGATIVE: 6-month return negative → no entry even if the"
            "    trend filter passes (fresh crossovers need momentum confirmation)."
            "\n"
            "  - Prefer entries on pullbacks: RSI 45–60 near the 50-SMA beats"
            "    chasing. RSI up to 80 is acceptable when the trend filter and"
            "    momentum both confirm (walk-forward backtests show capping"
            "    entries at RSI 70 forfeits the strongest winners); above 80,"
            "    wait — flag 'extended, buy the next 50-SMA touch'."
            "\n\n"
            "**Step 4 — Thesis check (news + fundamentals):**"
            "\n"
            "  - Confirm from news: order backlog growing, capacity sold out,"
            "    hyperscaler capex guidance rising, ASP increases."
            "\n"
            "  - Red flags that override a technical BUY down to HOLD: bottleneck"
            "    easing (capacity additions coming online industry-wide), customer"
            "    concentration with a single buyer signaling insourcing, or"
            "    gross margin contraction two quarters running."
            "\n\n"
            "**Step 5 — Position and exit rules (state in every report):**"
            "\n"
            "  - Size: risk 1% of portfolio to the stop. Stop = 3 × ATR below"
            "    entry (walk-forward validated; tighter stops shake out winners)."
            "    size = (portfolio × 0.01) / (3 × ATR). Assume a $100,000"
            "    portfolio if none is given. STRONG momentum + bottleneck score ≥ 8"
            "    may size up to 1.5% risk."
            "\n"
            "  - Max single-name exposure: 12% of portfolio. Max per bottleneck"
            "    category: 25% (owning three cooling names is one bet, not three)."
            "\n"
            "  - In market stress, scale gross exposure down rather than locking"
            "    out entirely: backtests across 2019-2026 show hard no-new-longs"
            "    lockouts miss V-shaped recoveries while per-position stops"
            "    already contain the damage."
            "\n"
            "  - Exits, whichever hits first: close below 200-SMA; 30% trailing"
            "    stop from the highest close since entry (validated vs 20/25%);"
            "    or thesis break from Step 4."
            "\n\n"
            "**Signal set:** BUY / PYRAMID (add to winner on pullback) / HOLD /"
            " TRIM (extended > 40% above 200-SMA) / EXIT."
            "\n\n"
            "End with a Markdown table: Bottleneck Category, Bottleneck Score,"
            " Trend Filter, Momentum, Signal, Entry Zone, Stop, Trailing Stop,"
            " Position Size, Key Catalyst."
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
            "ai_bottleneck_report": report,
        }

    return ai_bottleneck_analyst_node
