"""
Core AI engine logic - no Streamlit dependency.
This can be used by Streamlit, FastAPI, or anything else that wants
to talk to the PC Builder AI.
"""

import json
import time

from config import TOOLS, CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds


MODEL = "deepseek-ai/deepseek-v4-flash-0731"


def format_build_answer(client, answer):
    """
    Kept for now in case we need it later.

    Currently NOT used because the system prompt already instructs
    the AI to return complete builds in [BUILD] format.
    """

    formatter_prompt = f"""
You are formatting a PC build recommendation for a mobile application.

Convert the answer below into the EXACT structure required.

IMPORTANT:
- Do not invent or change any hardware, prices, or specifications.
- Keep the information from the original answer.
- If there are multiple builds, create a separate [BUILD] block for each.
- Put the explanation AFTER the build blocks.
- Do not put markdown tables inside the BUILD blocks.
- Every complete build MUST have all these fields.

EXACT FORMAT:

[BUILD]
Name: <short build name>
Use Case: <gaming / editing / general use>
CPU: <CPU>
GPU: <GPU>
Motherboard: <motherboard>
RAM: <RAM>
Storage: <storage>
PSU: <PSU>
Cooler: <cooler or Included with CPU>
Case: <case or Not specified>
Estimated Total: <price in INR>
[/BUILD]

Original answer:

{answer}
"""

    try:
        format_start = time.time()

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict formatting assistant. "
                        "Return only the reformatted answer."
                    ),
                },
                {
                    "role": "user",
                    "content": formatter_prompt,
                },
            ],
        )

        format_elapsed = time.time() - format_start

        print(
            f"\n[TIMING] Build formatter: "
            f"{format_elapsed:.2f} seconds\n"
        )

        formatted = response.choices[0].message.content

        if formatted:
            return formatted

        return answer

    except Exception as e:
        print(f"Build formatting failed: {e}")
        return answer


def run_conversation(
    client,
    tavily_client,
    history,
    question
):
    """
    Takes the AI client, search client, the FULL conversation history
    so far, and a new question.

    Runs the tool-calling loop and returns the answer plus
    the updated history.
    """

    history.append({
        "role": "user",
        "content": question
    })

    search_log = []

    build_tool_used = False

    MAX_ROUNDS = 1

    for round_num in range(MAX_ROUNDS):

        ai_start = time.time()

        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=TOOLS
        )

        ai_elapsed = time.time() - ai_start

        print(
            f"\n[TIMING] AI call: "
            f"{ai_elapsed:.2f} seconds\n"
        )

        message = response.choices[0].message

        # ---------------------------------------------------------
        # AI wants to use one or more tools
        # ---------------------------------------------------------

        if message.tool_calls:

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

                try:
                    args = json.loads(
                        tool_call.function.arguments
                    )

                except json.JSONDecodeError:

                    tool_result = (
                        "The tool arguments could not be "
                        "read correctly."
                    )

                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })

                    continue

                function_name = tool_call.function.name

                # -------------------------------------------------
                # WEB SEARCH
                # -------------------------------------------------

                if function_name == "search_web":

                    query = args.get("query")

                    if not query:

                        tool_result = (
                            "No search query was provided."
                        )

                    else:

                        search_log.append(query)

                        tool_result = search_web(
                            tavily_client,
                            query
                        )

                # -------------------------------------------------
                # PART COMPARISON
                # -------------------------------------------------

                elif function_name == "compare_parts":

                    parts = args.get(
                        "parts",
                        []
                    )

                    search_log.append(
                        "Comparing: "
                        + ", ".join(parts)
                    )

                    tool_result = compare_parts(
                        tavily_client,
                        parts,
                        CURRENT_YEAR
                    )

                # -------------------------------------------------
                # BUILD GENERATOR
                # -------------------------------------------------

                elif function_name == "generate_builds":

                    build_tool_used = True

                    budget = args.get(
                        "budget"
                    )

                    use_case = args.get(
                        "use_case"
                    )

                    existing_parts = args.get(
                        "existing_parts"
                    )

                    search_log.append(
                        f"Generating builds: "
                        f"Rs.{budget}, {use_case}"
                    )

                    tool_result = generate_builds(
                        tavily_client,
                        budget,
                        use_case,
                        existing_parts,
                        CURRENT_YEAR
                    )

                else:

                    tool_result = (
                        f"Unknown tool: "
                        f"{function_name}"
                    )

                # Add tool result to conversation
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

        # ---------------------------------------------------------
        # AI is ready to answer
        # ---------------------------------------------------------

        else:

            answer = (
                message.content
                or "I couldn't generate a response."
            )

            # No formatter call here.
            # The system prompt should already force [BUILD] format.

            history.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "history": history,
                "search_log": search_log
            }

    # -------------------------------------------------------------
    # Safety fallback if AI keeps calling tools
    # -------------------------------------------------------------

    history.append({
        "role": "user",
        "content": (
            "You now have enough information. "
            "Do not call any more tools. "
            "Give your best final answer now."
        )
    })

    final_start = time.time()

    final = client.chat.completions.create(
        model=MODEL,
        messages=history
    )

    final_elapsed = time.time() - final_start

    print(
        f"\n[TIMING] Final AI answer: "
        f"{final_elapsed:.2f} seconds\n"
    )

    answer = (
        final.choices[0].message.content
        or "I couldn't generate a final response."
    )

    # IMPORTANT:
    # No format_build_answer() call here.
    # The AI's system prompt should already produce [BUILD] blocks.

    history.append({
        "role": "assistant",
        "content": answer
    })

    return {
        "answer": answer,
        "history": history,
        "search_log": search_log
    }