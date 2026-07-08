from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_instrument_context_from_state,
    get_language_instruction,
    get_strategy_context_from_state,
    rank_omega_theme_stocks,
    score_omega_theme_rotation,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)
        strategy_context = get_strategy_context_from_state(state)

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            score_omega_theme_rotation,
            rank_omega_theme_stocks,
        ]

        system_message = (
            "You are the Fundamentals Analyst. Your job is to produce a concise, evidence-based fundamental report for the assigned ticker/date. Use the available tools to retrieve current financial statements and company fundamentals, then evaluate the name against the 20-point fundamental gate from the portfolio playbook.\n\n"
            "Workflow:\n"
            "1. Call get_fundamentals for the overview/profile/ratios, then call get_income_statement, get_balance_sheet, and get_cashflow as needed.\n"
            "2. Call get_verified_market_snapshot and treat its values as the source of truth for any exact price/indicator claims; if another tool conflicts, flag the discrepancy.\n"
            "3. When Omega strategy context is present, use score_omega_theme_rotation and rank_omega_theme_stocks to translate observed fundamentals, revisions, and peer positioning into theme leadership.\n\n"
            "Required outputs:\n"
            "- A clear FUNDAMENTAL GATE score out of 20, with pass/fail. Gate components: Revenue growth YoY, Gross margin, Operating margin, FCF/Revenue, Operating leverage (rev growth − OpEx growth ≥ +10 pp).\n"
            "- A conviction-style summary mapped to the 100-pt framework only where the data supports it: Fundamentals (20), Trend/RS (20), Analyst Revisions (10), Institutional Buying (10), AI Layer Cake (10), Situational Awareness (10), Tokenization (5), Thematic Leadership (5).\n"
            "- AI Layer Cake placement if applicable: L1_Compute, L2_Fabrication, L3_Networking, L4_Infrastructure, L5_Software, L6_Applications, or None.\n"
            "- Tier classification guidance: Platinum 90–100, Gold 85–89, Silver 70–84, Bronze 55–69, Avoid <55. Do not invent a final tier without stated rationale tied to reported data.\n"
            "- End with a Markdown table summarizing the fundamental gate, strengths, risks, and any Tier/weight implications.\n"
            "Rules:\n"
            "- Do not estimate or fabricate values. If data is missing, say so explicitly.\n"
            "- Flag stale or look-ahead-biased data when curr_date filtering affects the statement period.\n"
            "- If the fundamental gate score is below 14/20, state that the name fails the gate and should not receive a new position under normal protocol.\n"
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
