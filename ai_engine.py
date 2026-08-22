import streamlit as st
import json
from config import SYSTEM_PROMPT, TOOLS, CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds


def ask_pc_builder(question):
    st.session_state.history.append({"role": "user", "content": question})

    MAX_ROUNDS = 3
    for round_num in range(MAX_ROUNDS):
        response = st.session_state.client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=st.session_state.history,
            tools=TOOLS
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
                    st.session_state.search_log.append(query)
                    tool_result = search_web(query)

                elif function_name == "compare_parts":
                    parts = args["parts"]
                    st.session_state.search_log.append("Comparing: " + ", ".join(parts))
                    tool_result = compare_parts(parts, CURRENT_YEAR)
                elif function_name == "generate_builds":
                    budget = args["budget"]
                    use_case = args["use_case"]
                    existing_parts = args.get("existing_parts")
                    st.session_state.search_log.append(f"Generating builds: ₹{budget}, {use_case}")
                    tool_result = generate_builds(budget, use_case, existing_parts, CURRENT_YEAR)

                else:
                    tool_result = f"Unknown tool: {function_name}"

                st.session_state.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
        else:
            st.session_state.history.append({"role": "assistant", "content": message.content})
            return message.content

    st.session_state.history.append({"role": "user", "content": "Please give your best answer now with what you have."})
    final = st.session_state.client.chat.completions.create(
        model="nvidia/nemotron-3-ultra-550b-a55b",
        messages=st.session_state.history
    )
    answer = final.choices[0].message.content
    st.session_state.history.append({"role": "assistant", "content": answer})
    return answer