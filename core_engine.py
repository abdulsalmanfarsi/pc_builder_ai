"""
Core AI engine using Google Gemini API - simple and reliable.
"""

import google.generativeai as genai
from config import CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds

MODEL_NAME = "gemini-1.5-flash"


def run_conversation(genai_module, tavily_client, history, question):
    """
    Gemini conversation with manual tool handling.
    """
    search_log = []

    # Extract system prompt
    system_prompt = ""
    if history and history[0]["role"] == "system":
        system_prompt = history[0]["content"]

    # Create model with system instruction
    model = genai_module.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt
    )

    # Define tools in Gemini format
    search_tool = genai_module.protos.Tool(
        function_declarations=[
            genai_module.protos.FunctionDeclaration(
                name="search_web",
                description="Search the web for current PC part prices, benchmarks, or comparisons",
                parameters=genai_module.protos.Schema(
                    type=genai_module.protos.Type.OBJECT,
                    properties={
                        "query": genai_module.protos.Schema(type=genai_module.protos.Type.STRING)
                    },
                    required=["query"]
                )
            ),
            genai_module.protos.FunctionDeclaration(
                name="generate_builds",
                description="Generate complete PC build options for a budget and use case",
                parameters=genai_module.protos.Schema(
                    type=genai_module.protos.Type.OBJECT,
                    properties={
                        "budget": genai_module.protos.Schema(type=genai_module.protos.Type.STRING),
                        "use_case": genai_module.protos.Schema(type=genai_module.protos.Type.STRING),
                        "existing_parts": genai_module.protos.Schema(type=genai_module.protos.Type.STRING)
                    },
                    required=["budget", "use_case"]
                )
            ),
            genai_module.protos.FunctionDeclaration(
                name="compare_parts",
                description="Compare 2-3 PC parts side by side",
                parameters=genai_module.protos.Schema(
                    type=genai_module.protos.Type.OBJECT,
                    properties={
                        "parts": genai_module.protos.Schema(
                            type=genai_module.protos.Type.ARRAY,
                            items=genai_module.protos.Schema(type=genai_module.protos.Type.STRING)
                        )
                    },
                    required=["parts"]
                )
            )
        ]
    )

    # Start chat with tools
    chat = model.start_chat(enable_automatic_function_calling=False)

    # Send message with tools
    response = chat.send_message(question, tools=[search_tool])

    MAX_ROUNDS = 2
    for round_num in range(MAX_ROUNDS):
        # Check if model wants to call a function
        if response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            function_name = function_call.name
            args = dict(function_call.args)

            # Execute the tool
            if function_name == "search_web":
                query = args.get("query", "")
                search_log.append(query)
                result = search_web(tavily_client, query)

            elif function_name == "generate_builds":
                budget = args.get("budget", "")
                use_case = args.get("use_case", "")
                existing = args.get("existing_parts", "")
                search_log.append(f"Building: {budget}, {use_case}")
                result = generate_builds(tavily_client, budget, use_case, existing, CURRENT_YEAR)

            elif function_name == "compare_parts":
                parts = args.get("parts", [])
                search_log.append(f"Comparing: {', '.join(parts)}")
                result = compare_parts(tavily_client, parts, CURRENT_YEAR)
            else:
                result = "Unknown tool"

            # Send function response back
            response = chat.send_message(
                genai_module.protos.Content(
                    parts=[genai_module.protos.Part(
                        function_response=genai_module.protos.FunctionResponse(
                            name=function_name,
                            response={"result": result}
                        )
                    )]
                )
            )
        else:
            # No more function calls, we have the answer
            break

    # Get final answer
    answer = response.text

    # Update history
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "history": history,
        "search_log": search_log
    }
