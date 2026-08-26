import json
import streamlit as st
from config import CURRENT_YEAR, SYSTEM_PROMPT, TOOLS
from tools import compare_parts, generate_builds, search_web

MODEL = "nvidia/nemotron-3-ultra-550b-a55b"


def ask_pc_builder(question):
    if not st.session_state.history:
        st.session_state.history.append({"role": "system", "content": SYSTEM_PROMPT})

    st.session_state.history.append({"role": "user", "content": question})
    tavily_client = getattr(st.session_state, "tavily_client", None)

    MAX_ROUNDS = 3
    for _ in range(MAX_ROUNDS):
        response = st.session_state.client.chat.completions.create(
            model=MODEL, messages=st.session_state.history, tools=TOOLS
        )
        message = response.choices[0].message

        if message.tool_calls:
            st.session_state.history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                function_name = tool_call.function.name

                if function_name == "search_web":
                    query = args.get("query", "")
                    st.session_state.search_log.append(query)
                    tool_result = search_web(tavily_client, query)

                elif function_name == "compare_parts":
                    parts = args.get("parts", [])
                    st.session_state.search_log.append(
                        "Comparing: " + ", ".join(parts)
                    )
                    tool_result = compare_parts(
                        tavily_client, parts, CURRENT_YEAR
                    )

                elif function_name == "generate_builds":
                    budget = args.get("budget", "")
                    use_case = args.get("use_case", "")
                    existing_parts = args.get("existing_parts")
                    st.session_state.search_log.append(
                        f"Generating builds: ₹{budget}, {use_case}"
                    )
                    tool_result = generate_builds(
                        tavily_client,
                        budget,
                        use_case,
                        existing_parts,
                        CURRENT_YEAR,
                    )

                else:
                    tool_result = f"Unknown tool call: {function_name}"

                st.session_state.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })
        else:
            st.session_state.history.append(
                {"role": "assistant", "content": message.content}
            )
            return message.content

    final = st.session_state.client.chat.completions.create(
        model=MODEL, messages=st.session_state.history
    )
    answer = final.choices[0].message.content
    st.session_state.history.append({"role": "assistant", "content": answer})
    return answer