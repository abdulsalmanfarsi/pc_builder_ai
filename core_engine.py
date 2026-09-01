"""
Core AI engine using Google Gemini via HTTP requests - no SDK needed.
"""

import requests
from config import GOOGLE_API_KEY, CURRENT_YEAR, TOOLS_GEMINI
from tools import search_web, compare_parts, generate_builds

MODEL_NAME = "gemini-3.5-flash-lite"
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
        elif msg["role"] == "function_call":
            # The model's own request to call a tool - must be sent back as a
            # real functionCall part, or Gemini loses track of what it asked for.
            # Gemini 3.x also requires the thoughtSignature that came attached
            # to this part to be echoed back exactly, or it 400s.
            part = {"functionCall": msg["content"]["functionCall"]}
            if msg["content"].get("thoughtSignature"):
                part["thoughtSignature"] = msg["content"]["thoughtSignature"]
            contents.append({"role": "model", "parts": [part]})
        elif msg["role"] == "function_response":
            # The tool's result - Gemini's generateContent REST API only accepts
            # role "user" or "model" (no "function" role exists here), so the
            # functionResponse part goes back under "user".
            contents.append({"role": "user", "parts": [{"functionResponse": msg["content"]}]})

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
    if not response.ok:
        # Embed Google's actual error text directly in the exception message -
        # print() wasn't showing up reliably in Render's logs, but exception
        # tracebacks are, so put the diagnostic info where we know it'll appear.
        raise RuntimeError(f"Gemini API error {response.status_code}: {response.text}")
    return response.json()


def run_conversation(tavily_client, history, question):
    """
    Gemini conversation with manual tool handling.
    """
    search_log = []

    # Build messages
    messages = list(history) + [{"role": "user", "content": question}]

    # Use the single source-of-truth tool schema from config.py
    tools = TOOLS_GEMINI

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
            thought_signature = parts[0].get("thoughtSignature")
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

            # Add tool call and result to messages, using roles call_gemini()
            # now knows how to convert into real functionCall/functionResponse parts
            messages.append({"role": "function_call", "content": {"functionCall": fc, "thoughtSignature": thought_signature}})
            messages.append({"role": "function_response", "content": {"name": function_name, "response": {"result": tool_result}}})

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