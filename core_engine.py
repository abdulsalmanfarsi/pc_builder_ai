"""
Core AI engine logic - no Streamlit dependency.
This can be used by Streamlit, FastAPI, or anything else that wants
to talk to the PC Builder AI.
"""

import json
from config import TOOLS, CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds

MODEL = "llama-3.1-70b-versatile"


def run_conversation(client, tavily_client, history, question):
    """
    Takes the AI client, Tavily client, conversation history,
    and a new question.

    Runs:
        AI -> tool -> final AI answer

    Returns:
        answer
        updated history
        search log
    """

    history.append({
        "role": "user",
        "content": question
    })

    search_log = []

    # --------------------------------------------------
    # ONLY ONE TOOL ROUND
    # --------------------------------------------------
    #
    # This prevents:
    #
    # AI -> tool -> AI -> tool -> AI
    #
    # For normal PC questions we want:
    #
    # AI -> tool -> AI -> DONE
    #
    MAX_TOOL_ROUNDS = 1

    # ==================================================
    # AI + TOOL CALL
    # ==================================================

    for round_num in range(MAX_TOOL_ROUNDS):

        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=TOOLS,
            max_tokens=400  # tool-selection call — only needs to decide which tool to use, not write a full answer
        )

        message = response.choices[0].message

        # --------------------------------------------------
        # AI DID NOT REQUEST A TOOL
        # --------------------------------------------------

        if not message.tool_calls:

            answer = message.content or "I couldn't generate a response."

            history.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "history": history,
                "search_log": search_log
            }

        # --------------------------------------------------
        # AI REQUESTED TOOL(S)
        # --------------------------------------------------

        history.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        })

        # --------------------------------------------------
        # EXECUTE TOOLS
        # --------------------------------------------------

        for tool_call in message.tool_calls:

            function_name = tool_call.function.name

            try:
                args = json.loads(
                    tool_call.function.arguments
                )

            except json.JSONDecodeError:

                tool_result = (
                    "The tool arguments could not be read correctly. "
                    "Answer using the information already available."
                )

                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

                continue

            # ==============================================
            # SEARCH WEB
            # ==============================================

            if function_name == "search_web":

                query = args.get("query")

                if not query:

                    tool_result = "No search query was provided."

                else:

                    search_log.append(query)

                    tool_result = search_web(
                        tavily_client,
                        query
                    )

            # ==============================================
            # COMPARE PARTS
            # ==============================================

            elif function_name == "compare_parts":

                parts = args.get("parts", [])

                if not parts:

                    tool_result = (
                        "No parts were provided for comparison."
                    )

                else:

                    search_log.append(
                        "Comparing: " + ", ".join(parts)
                    )

                    tool_result = compare_parts(
                        tavily_client,
                        parts,
                        CURRENT_YEAR
                    )

            # ==============================================
            # GENERATE BUILD
            # ==============================================

            elif function_name == "generate_builds":

                budget = args.get("budget")
                use_case = args.get("use_case")
                existing_parts = args.get("existing_parts")

                if budget is None or not use_case:

                    tool_result = (
                        "Budget or use case was missing. "
                        "Answer using the available information."
                    )

                else:

                    search_log.append(
                        f"Generating build: {budget}, {use_case}"
                    )

                    tool_result = generate_builds(
                        tavily_client,
                        budget,
                        use_case,
                        existing_parts,
                        CURRENT_YEAR
                    )

            # ==============================================
            # UNKNOWN TOOL
            # ==============================================

            else:

                tool_result = (
                    f"Unknown tool requested: {function_name}"
                )

            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

    # ==================================================
    # FINAL AI ANSWER
    # ==================================================
    #
    # At this point the AI has already received the
    # search results.
    #
    # We now make ONE final, short AI call.
    # ==================================================

    history.append({
        "role": "system",
        "content": (
            "You now have the required information. "
            "Give the final answer immediately. "
            "Do not call any more tools. "
            "Be concise and avoid unnecessary explanations. "
            "If this is a complete PC build request, "
            "follow the required [BUILD] format exactly."
        )
    })

    final = client.chat.completions.create(
        model=MODEL,
        messages=history,
        max_tokens=1400
    )

    answer = (
        final.choices[0].message.content
        or "I couldn't generate a final response."
    )

    history.append({
        "role": "assistant",
        "content": answer
    })

    return {
        "answer": answer,
        "history": history,
        "search_log": search_log
    }