"""
Core AI engine using Google Gemini via HTTP requests - no SDK needed.
"""

import re
import requests

from config import GOOGLE_API_KEY, CURRENT_YEAR, TOOLS_GEMINI
from tools import (
    search_web,
    compare_parts,
    generate_builds,
    verify_component_prices,
)


MODEL_NAME = "gemini-3.5-flash-lite"

API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"
)


# ==================================================
# GEMINI API CALL
# ==================================================

def call_gemini(messages, tools=None):
    """Call Gemini API directly via HTTP."""

    headers = {
        "Content-Type": "application/json"
    }

    contents = []
    system_instruction = None

    for msg in messages:

        role = msg.get("role")

        if role == "system":

            system_instruction = msg.get("content", "")

        elif role == "user":

            contents.append({
                "role": "user",
                "parts": [
                    {
                        "text": msg.get("content", "")
                    }
                ]
            })

        elif role == "assistant":

            contents.append({
                "role": "model",
                "parts": [
                    {
                        "text": msg.get("content", "")
                    }
                ]
            })

        elif role == "function_call":

            function_call = msg["content"]["functionCall"]

            part = {
                "functionCall": function_call
            }

            thought_signature = msg["content"].get(
                "thoughtSignature"
            )

            if thought_signature:
                part["thoughtSignature"] = thought_signature

            contents.append({
                "role": "model",
                "parts": [part]
            })

        elif role == "function_response":

            contents.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": msg["content"]
                    }
                ]
            })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2500
        }
    }

    if system_instruction:

        payload["systemInstruction"] = {
            "parts": [
                {
                    "text": system_instruction
                }
            ]
        }

    if tools:
        payload["tools"] = tools

    try:

        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

    except requests.exceptions.Timeout:

        raise RuntimeError(
            "Gemini API request timed out."
        )

    except requests.exceptions.RequestException as error:

        raise RuntimeError(
            f"Gemini API request failed: {error}"
        )

    if not response.ok:

        raise RuntimeError(
            f"Gemini API error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ==================================================
# MAIN CONVERSATION ENGINE
# ==================================================

def run_conversation(
    tavily_client,
    history,
    question,
    country="",
    currency=""
):

    # ==================================================
    # KEEP ORIGINAL USER QUESTION
    # ==================================================

    original_question = question


    # ==================================================
    # MARKET CONTEXT
    # ==================================================

    # The frontend provides this information.
    # Never infer a country from a currency symbol.

    market_context = ""

    if country or currency:

        market_context = (
            "\n\nUSER MARKET CONTEXT:\n"
            f"Country/Market: {country or 'Not specified'}\n"
            f"Currency: {currency or 'Not specified'}\n"
            "\n"
            "Use this market context for component availability "
            "and price searches. Do not assume another country "
            "or market unless the user explicitly asks you to.\n"
        )


    # ==================================================
    # FIND MOST RECENT PREVIOUS BUILD
    # ==================================================

    previous_build_text = None

    for msg in reversed(history):

        if msg.get("role") != "assistant":
            continue

        content = msg.get("content", "")

        if "[BUILD]" not in content:
            continue

        match = re.search(
            r"\[BUILD\](.*?)\[/BUILD\]",
            content,
            re.DOTALL
        )

        if match:

            previous_build_text = (
                "[BUILD]"
                + match.group(1)
                + "[/BUILD]"
            )

            break


    # ==================================================
    # CREATE TEMPORARY AI QUESTION
    # ==================================================

    question_for_ai = original_question

    # Add market context only for Gemini.
    # The original question remains clean in history.

    question_for_ai += market_context


    if previous_build_text:

        question_for_ai += f"""

PREVIOUS BUILD FOR CONTEXT:

{previous_build_text}

Use this previous build only if the user's current request
is modifying or updating that build.

If the user is requesting a modification, compare the new
build against this previous build and follow the
"CHANGES FROM PREVIOUS BUILD" instructions in the system prompt.

If the user is asking a new or unrelated question, ignore
this previous build.
"""


    # ==================================================
    # SEARCH LOG
    # ==================================================

    search_log = []


    # ==================================================
    # BUILD GEMINI MESSAGE LIST
    # ==================================================

    messages = list(history)

    messages.append({
        "role": "user",
        "content": question_for_ai
    })


    # ==================================================
    # GEMINI TOOLS
    # ==================================================

    tools = TOOLS_GEMINI


    # ==================================================
    # FIRST GEMINI CALL
    # ==================================================

    result = call_gemini(
        messages,
        tools
    )

    candidate = result.get(
        "candidates",
        [{}]
    )[0]

    content = candidate.get(
        "content",
        {}
    )

    parts = content.get(
        "parts",
        []
    )


    # ==================================================
    # TOOL CALL LOOP
    # ==================================================

    MAX_ROUNDS = 3

    for round_num in range(MAX_ROUNDS):

        function_call_found = False


        for part in parts:

            if "functionCall" not in part:
                continue


            fc = part["functionCall"]

            thought_signature = part.get(
                "thoughtSignature"
            )

            function_name = fc.get(
                "name"
            )

            args = fc.get(
                "args",
                {}
            )


            # ==============================================
            # SEARCH WEB
            # ==============================================

            if function_name == "search_web":

                query = args.get(
                    "query",
                    ""
                )

                if query:

                    # Force the user's market into searches
                    # when a market is available.

                    market_query = query

                    if country:
                        market_query += f" {country}"

                    if currency:
                        market_query += f" prices in {currency}"

                    search_log.append(
                        market_query
                    )

                    tool_result = search_web(
                        tavily_client,
                        market_query
                    )

                else:

                    tool_result = (
                        "No search query was provided."
                    )


            # ==============================================
            # GENERATE BUILDS
            # ==============================================

            elif function_name == "generate_builds":

                budget = args.get(
                    "budget",
                    ""
                )

                use_case = args.get(
                    "use_case",
                    ""
                )

                existing_parts = args.get(
                    "existing_parts",
                    ""
                )

                if budget and use_case:

                    search_log.append(
                        f"Building: {budget}, {use_case}, "
                        f"Market: {country or 'Not specified'}, "
                        f"Currency: {currency or 'Not specified'}"
                    )

                    tool_result = generate_builds(
                        tavily_client=tavily_client,
                        budget=budget,
                        use_case=use_case,
                        existing_parts=existing_parts,
                        region=country,
                        current_year=CURRENT_YEAR
                    )

                else:

                    tool_result = (
                        "Budget or use case was missing."
                    )


            # ==============================================
            # COMPARE PARTS
            # ==============================================

            elif function_name == "compare_parts":

                parts_list = args.get(
                    "parts",
                    []
                )

                if parts_list:

                    search_log.append(
                        "Comparing: "
                        + ", ".join(parts_list)
                    )

                    tool_result = compare_parts(
                        tavily_client,
                        parts_list,
                        CURRENT_YEAR
                    )

                else:

                    tool_result = (
                        "No components were provided "
                        "for comparison."
                    )


            # ==============================================
            # VERIFY COMPONENT PRICES
            # ==============================================

            elif function_name == "verify_component_prices":

                components = args.get(
                    "components",
                    []
                )

                if components:

                    # Do not trust the model to select
                    # a different region. Use frontend market.

                    verification_region = country

                    search_log.append(
                        "Verifying prices: "
                        + ", ".join(components)
                        + (
                            f" | Market: {verification_region}"
                            if verification_region
                            else ""
                        )
                    )

                    tool_result = verify_component_prices(
                        tavily_client=tavily_client,
                        components=components,
                        region=verification_region,
                        current_year=CURRENT_YEAR
                    )

                else:

                    tool_result = (
                        "No components were provided "
                        "for price verification."
                    )


            # ==============================================
            # UNKNOWN TOOL
            # ==============================================

            else:

                tool_result = (
                    f"Unknown tool requested: "
                    f"{function_name}"
                )


            # ==============================================
            # ADD FUNCTION CALL
            # ==============================================

            function_call_content = {
                "functionCall": fc
            }

            if thought_signature:

                function_call_content[
                    "thoughtSignature"
                ] = thought_signature


            messages.append({
                "role": "function_call",
                "content": function_call_content
            })


            # ==============================================
            # ADD FUNCTION RESPONSE
            # ==============================================

            messages.append({
                "role": "function_response",
                "content": {
                    "name": function_name,
                    "response": {
                        "result": tool_result
                    }
                }
            })


            function_call_found = True


        # ==============================================
        # NO TOOL CALL → FINAL ANSWER
        # ==============================================

        if not function_call_found:
            break


        # ==============================================
        # CALL GEMINI WITH TOOL RESULTS
        # ==============================================

        result = call_gemini(
            messages,
            tools
        )

        candidate = result.get(
            "candidates",
            [{}]
        )[0]

        content = candidate.get(
            "content",
            {}
        )

        parts = content.get(
            "parts",
            []
        )


    # ==================================================
    # EXTRACT FINAL TEXT
    # ==================================================

    answer = None

    for part in parts:

        if "text" in part:

            answer = part["text"]

            break


    # ==================================================
    # FORCE FINAL ANSWER IF NEEDED
    # ==================================================

    if not answer:

        messages.append({
            "role": "user",
            "content": (
                "Using all information already retrieved above, "
                "provide the final answer now. "
                "Do not call any more tools."
            )
        })


        result = call_gemini(
            messages,
            tools=None
        )


        candidate = result.get(
            "candidates",
            [{}]
        )[0]

        content = candidate.get(
            "content",
            {}
        )

        parts = content.get(
            "parts",
            []
        )


        for part in parts:

            if "text" in part:

                answer = part["text"]

                break


    # ==================================================
    # FINAL SAFETY FALLBACK
    # ==================================================

    answer = answer or (
        "I couldn't generate a response."
    )


    # ==================================================
    # UPDATE CONVERSATION HISTORY
    # ==================================================

    history.append({
        "role": "user",
        "content": original_question
    })


    history.append({
        "role": "assistant",
        "content": answer
    })


    # ==================================================
    # RETURN RESULT
    # ==================================================

    return {
        "answer": answer,
        "history": history,
        "search_log": search_log
    }