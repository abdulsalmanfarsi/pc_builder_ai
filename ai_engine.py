import json
import streamlit as st
from config import CURRENT_YEAR, MODEL, SYSTEM_PROMPT, TOOLS
from tools import compare_parts, generate_builds, search_web


def ask_pc_builder(question: str) -> str:
    """Processes user input, handles tool calling loops safely, and returns the final response."""
    # Initialize conversation history if empty
    if "history" not in st.session_state or not st.session_state.history:
        st.session_state.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Ensure search log is initialized
    if "search_log" not in st.session_state:
        st.session_state.search_log = []

    # Append current user prompt
    st.session_state.history.append({"role": "user", "content": question})
    tavily_client = getattr(st.session_state, "tavily_client", None)

    MAX_ROUNDS = 3

    for _ in range(MAX_ROUNDS):
        response = st.session_state.client.chat.completions.create(
            model=MODEL, messages=st.session_state.history, tools=TOOLS
        )
        message = response.choices[0].message

        # Handle Function/Tool Calls requested by the LLM
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
                function_name = tool_call.function.name
                raw_args = tool_call.function.arguments

                # SAFE PARSING: Prevents JSON Parse error crashes when LLM sends invalid JSON
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}

                # Tool 1: General Web Search
                if function_name == "search_web":
                    query = args.get("query", question)
                    st.session_state.search_log.append(query)
                    tool_result = search_web(tavily_client, query)

                # Tool 2: Part Comparison
                elif function_name == "compare_parts":
                    parts = args.get("parts", [])
                    st.session_state.search_log.append(
                        "Comparing: "
                        + (", ".join(parts) if parts else "Components")
                    )
                    tool_result = compare_parts(
                        tavily_client, parts, CURRENT_YEAR
                    )

                # Tool 3: Build Recommendation Search
                elif function_name == "generate_builds":
                    budget = args.get("budget", "55000")
                    use_case = args.get("use_case", "gpu_heavy")
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

                # Append tool response back to LLM context window
                st.session_state.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(tool_result),
                })
        else:
            # If no tools were called, store and return final text answer
            st.session_state.history.append(
                {"role": "assistant", "content": message.content}
            )
            return message.content

    # Fallback response if maximum execution loops are reached
    final_response = st.session_state.client.chat.completions.create(
        model=MODEL, messages=st.session_state.history
    )
    answer = final_response.choices[0].message.content
    st.session_state.history.append({"role": "assistant", "content": answer})
    return answer