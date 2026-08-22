"""
Core AI engine logic - no Streamlit dependency.
This can be used by Streamlit, FastAPI, or anything else that wants
to talk to the PC Builder AI.
"""
import json
from openai import OpenAI
from tavily import TavilyClient
from config import TOOLS, CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds


def run_conversation(client, tavily_client, history, question):
    """
    Takes the AI client, search client, the FULL conversation history so far,
    and a new question. Runs the tool-calling loop and returns the answer
    plus the updated history (so the caller can store/send it for next time).
    """
    history.append({"role": "user", "content": question})
    search_log = []

    MAX_ROUNDS = 3
    for round_num in range(MAX_ROUNDS):
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=history,
            tools=TOOLS
        )
        message = response.choices[0].message

        if message.tool_calls:
            history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in message.tool_calls
                ]
            })

            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                function_name = tool_call.function.name

                if function_name == "search_web":
                    query = args["query"]
                    search_log.append(query)
                    tool_result = search_web(tavily_client, query)

                elif function_name == "compare_parts":
                    parts = args["parts"]
                    search_log.append("Comparing: " + ", ".join(parts))
                    tool_result = compare_parts(tavily_client, parts, CURRENT_YEAR)

                elif function_name == "generate_builds":
                    budget = args["budget"]
                    use_case = args["use_case"]
                    existing_parts = args.get("existing_parts")
                    search_log.append(f"Generating builds: Rs.{budget}, {use_case}")
                    tool_result = generate_builds(tavily_client, budget, use_case, existing_parts, CURRENT_YEAR)

                else:
                    tool_result = f"Unknown tool: {function_name}"

                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
        else:
            history.append({"role": "assistant", "content": message.content})
            return {"answer": message.content, "history": history, "search_log": search_log}

    history.append({"role": "user", "content": "Please give your best answer now with what you have."})
    final = client.chat.completions.create(
        model="nvidia/nemotron-3-ultra-550b-a55b",
        messages=history
    )
    answer = final.choices[0].message.content
    history.append({"role": "assistant", "content": answer})
    return {"answer": answer, "history": history, "search_log": search_log}