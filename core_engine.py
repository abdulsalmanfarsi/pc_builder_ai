"""
Core AI engine using Google Gemini via HTTP requests - no SDK needed.
"""

import re
import requests

from config import GOOGLE_API_KEY, CURRENT_YEAR, TOOLS_GEMINI
from tools import search_web, compare_parts, generate_builds


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

    # Convert internal conversation messages to Gemini format
    contents = []
    system_instruction = None

    for msg in messages:

        role = msg.get("role")

        # ----------------------------------------------
        # SYSTEM MESSAGE
        # ----------------------------------------------

        if role == "system":

            system_instruction = msg.get("content", "")

        # ----------------------------------------------
        # USER MESSAGE
        # ----------------------------------------------

        elif role == "user":

            contents.append({
                "role": "user",
                "parts": [
                    {
                        "text": msg.get("content", "")
                    }
                ]
            })

        # ----------------------------------------------
        # ASSISTANT MESSAGE
        # ----------------------------------------------

        elif role == "assistant":

            contents.append({
                "role": "model",
                "parts": [
                    {
                        "text": msg.get("content", "")
                    }
                ]
            })

        # ----------------------------------------------
        # FUNCTION CALL
        # ----------------------------------------------

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

        # ----------------------------------------------
        # FUNCTION RESPONSE
        # ----------------------------------------------

        elif role == "function_response":

            contents.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": msg["content"]
                    }
                ]
            })

    # ==================================================
    # API PAYLOAD
    # ==================================================

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2500
        }
    }

    # Add system instruction
    if system_instruction:

        payload["systemInstruction"] = {
            "parts": [
                {
                    "text": system_instruction
                }
            ]
        }

    # Add tools if enabled
    if tools:

        payload["tools"] = tools

    # ==================================================
    # API REQUEST
    # ==================================================

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

    # ==================================================
    # API ERROR
    # ==================================================

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
    question
):

    # ==================================================
    # KEEP ORIGINAL USER QUESTION
    # ==================================================

    # This is what will permanently be stored in history.
    original_question = question


    # ==================================================
    # FIND MOST RECENT PREVIOUS BUILD
    # ==================================================

    previous_build_text = None

    for msg in reversed(history):

        # Only look at AI responses
        if msg.get("role") != "assistant":
            continue

        content = msg.get("content", "")

        # Skip messages without a build
        if "[BUILD]" not in content:
            continue

        # Extract only the BUILD block
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

    # Gemini receives this version.
    # The extra context is NOT permanently saved in history.
    question_for_ai = original_question

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

    # Start with existing conversation history
    messages = list(history)

    # Add ONLY ONE current user question
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

    MAX_ROUNDS = 2

    for round_num in range(MAX_ROUNDS):

        function_call_found = False


        # Check ALL response parts
        for part in parts:

            if "functionCall" not in part:
                continue


            # ==================================================
            # EXTRACT FUNCTION CALL
            # ==================================================

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


            # ==================================================
            # EXECUTE SEARCH WEB
            # ==================================================

            if function_name == "search_web":

                query = args.get(
                    "query",
                    ""
                )

                if query:

                    search_log.append(
                        query
                    )

                    tool_result = search_web(
                        tavily_client,
                        query
                    )

                else:

                    tool_result = (
                        "No search query was provided."
                    )


            # ==================================================
            # EXECUTE GENERATE BUILDS
            # ==================================================

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
                        f"Building: "
                        f"{budget}, "
                        f"{use_case}"
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
                        "Budget or use case was missing."
                    )


            # ==================================================
            # EXECUTE COMPARE PARTS
            # ==================================================

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


            # ==================================================
            # UNKNOWN TOOL
            # ==================================================

            else:

                tool_result = (
                    f"Unknown tool requested: "
                    f"{function_name}"
                )


            # ==================================================
            # ADD FUNCTION CALL TO CONVERSATION
            # ==================================================

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


            # ==================================================
            # ADD FUNCTION RESPONSE
            # ==================================================

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


        # ==================================================
        # NO TOOL CALLS → WE HAVE FINAL ANSWER
        # ==================================================

        if not function_call_found:

            break


        # ==================================================
        # CALL GEMINI AGAIN WITH TOOL RESULTS
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
    # EXTRACT FINAL TEXT
    # ==================================================

    answer = None

    for part in parts:

        if "text" in part:

            answer = part["text"]

            break


    # ==================================================
    # FINAL FALLBACK
    # ==================================================

    # If Gemini still returned function calls or no text
    # after the allowed tool rounds, force a final answer.

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

    # Store ONLY the original user question.
    # Do NOT store the injected previous-build context.

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