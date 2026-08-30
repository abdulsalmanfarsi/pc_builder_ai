"""
Core AI engine using Google Gemini via HTTP requests - no SDK needed.
"""

import json
import requests
from config import GOOGLE_API_KEY, CURRENT_YEAR
from tools import search_web, compare_parts, generate_builds

MODEL_NAME = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"


def call_gemini(messages, tools=None):
    """Call Gemini API directly via HTTP."""
    headers = {"Content-Type": "application/json"}

    # Convert messages to Gemini format
    contents = []
    system_instruction = None

    for msg in messages:
        if msg["role"] == "system":
            system_instruction = msg["content"]
        elif msg["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        elif msg["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": msg["content"]}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2500
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    if tools:
        payload["tools"] = tools

    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def run_conversation(genai_client, tavily_client, history, question):
    """
    Gemini conversation with manual tool handling.
    """
    search_log = []

    # Build messages
    messages = list(history) + [{"role": "user", "content": question}]

    # Define tools for Gemini
    tools = [{
        "function_declarations": [
            {
                "name": "search_web",
                "description": "Search the web for current PC part prices, benchmarks, or comparisons",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "The search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "generate_builds",
                "description": "Generate complete PC build options for a budget and use case",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "budget": {"type": "STRING"},
                        "use_case": {"type": "STRING"},
                        "existing_parts": {"type": "STRING"}
                    },
                    "required": ["budget", "use_case"]
                }
            },
            {
                "name": "compare_parts",
                "description": "Compare 2-3 PC parts side by side",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "parts": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["parts"]
                }
            }
        ]
    }]

    # Make API call with tools
    result = call_gemini(messages, tools)

    # Process response
    candidate = result.get("candidates", [{}])[0]
    content = candidate.get("content", {})
    parts = content.get("parts", [{}])

    # Check for function calls
    MAX_ROUNDS = 2
    for round_num in range(MAX_ROUNDS):
        if parts and "functionCall" in parts[0]:
            fc = parts[0]["functionCall"]
            function_name = fc["name"]
            args = fc.get("args", {})

            # Execute tool
            if function_name == "search_web":
                query = args.get("query", "")
                search_log.append(query)
                tool_result = search_web(tavily_client, query)

            elif function_name == "generate_builds":
                budget = args.get("budget", "")
                use_case = args.get("use_case", "")
                existing = args.get("existing_parts", "")
                search_log.append(f"Building: {budget}, {use_case}")
                tool_result = generate_builds(tavily_client, budget, use_case, existing, CURRENT_YEAR)

            elif function_name == "compare_parts":
                parts_list = args.get("parts", [])
                search_log.append(f"Comparing: {', '.join(parts_list)}")
                tool_result = compare_parts(tavily_client, parts_list, CURRENT_YEAR)
            else:
                tool_result = "Unknown tool"

            # Add tool call and result to messages
            messages.append({"role": "model", "content": json.dumps({"functionCall": fc})})
            messages.append({"role": "user", "content": json.dumps({"functionResponse": {"name": function_name, "response": {"result": tool_result}}})})

            # Call again
            result = call_gemini(messages, tools)
            candidate = result.get("candidates", [{}])[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [{}])
        else:
            break

    # Extract final text
    answer = parts[0].get("text", "I couldn't generate a response.") if parts else "No response."

    # Update history
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "history": history,
        "search_log": search_log
    }
