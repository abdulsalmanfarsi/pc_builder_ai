"""
Core AI engine logic - no Streamlit dependency.
This can be used by Streamlit, FastAPI, or anything else that wants
to talk to the PC Builder AI.
"""
import json
from config import TOOLS, CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds

MODEL = "nvidia/nemotron-3-ultra-550b-a55b"


def run_conversation(client, tavily_client, history, question):
    """
    Takes the AI client, search client, the full conversation history,
    and a new question.

    Runs the AI + tool-calling loop and returns:
    - answer
    - updated history
    - search log
    """

    history.append({
        "role": "user",
        "content": question
    })

    search_log = []

    MAX_ROUNDS = 2

    for round_num in range(MAX_ROUNDS):

        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=TOOLS
        )

        message = response.choices[0].message

        # --------------------------------------------------
        # NO TOOL CALLS -> THE AI HAS ITS FINAL ANSWER
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

        for tool_call in message.tool_calls:

            function_name = tool_call.function.name

            try:
                args = json.loads(tool_call.function.arguments)

            except json.JSONDecodeError:

                tool_result = (
                    "The tool arguments could not be read correctly. "
                    "Please answer using the information already available."
                )

                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

                continue

            # ----------------------------------------------
            # SEARCH WEB
            # ----------------------------------------------

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

            # ----------------------------------------------
            # COMPARE PARTS
            # ----------------------------------------------

            elif function_name == "compare_parts":

                parts = args.get("parts", [])

                if not parts:
                    tool_result = "No parts were provided for comparison."

                else:
                    search_log.append(
                        "Comparing: " + ", ".join(parts)
                    )

                    tool_result = compare_parts(
                        tavily_client,
                        parts,
                        CURRENT_YEAR
                    )

            # ----------------------------------------------
            # GENERATE BUILD
            # ----------------------------------------------

            elif function_name == "generate_builds":

                budget = args.get("budget")
                use_case = args.get("use_case")
                existing_parts = args.get("existing_parts")

                if budget is None or not use_case:

                    tool_result = (
                        "Budget or use case was missing. "
                        "Please answer based on the available information."
                    )

                else:

                    search_log.append(
                        f"Generating build: Rs.{budget}, {use_case}"
                    )

                    tool_result = generate_builds(
                        tavily_client,
                        budget,
                        use_case,
                        existing_parts,
                        CURRENT_YEAR
                    )

            # ----------------------------------------------
            # UNKNOWN TOOL
            # ----------------------------------------------

            else:

                tool_result = (
                    f"Unknown tool requested: {function_name}"
                )

            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

    # --------------------------------------------------
    # MAX TOOL ROUNDS REACHED
    # --------------------------------------------------

    history.append({
        "role": "user",
        "content": (
            "You now have enough information. "
            "Do not call any more tools. "
            "Give the user your best complete and polished answer "
            "using the information already collected."
        )
    })

    final = client.chat.completions.create(
        model=MODEL,
        messages=history
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