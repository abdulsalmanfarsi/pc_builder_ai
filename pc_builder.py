import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import datetime

NVIDIA_API_KEY = "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"
TAVILY_API_KEY = "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"

st.set_page_config(page_title="PC Builder Advisor", page_icon="🖥️", layout="centered")


# ---- Search tool ----
def search_web(query, max_results=6):
    try:
        response = st.session_state.tavily_client.search(query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return "No search results found for this query."
        formatted = ""
        for r in results:
            formatted += f"Title: {r['title']}\nContent: {r['content']}\nURL: {r['url']}\n\n"
        return formatted
    except Exception as e:
        return f"Search failed (error: {e}). Please answer using whatever information you already have, and mention that live search wasn't available."


tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information, like PC part prices, benchmarks, or recent comparisons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up"}
                },
                "required": ["query"]
            }
        }
    }
]

today = datetime.date.today().strftime("%B %d, %Y")

SYSTEM_PROMPT = f"""You are a knowledgeable, honest PC building advisor.
Today's actual date is {today}. Always use this as the correct current date - do not assume or default to any other year based on your training data.
When comparing components, base your comparison on actual specs, benchmarks, and real-world performance - not on assumptions that a newer generation is automatically better.
Some older or higher-tier parts can outperform newer, lower-tier parts in the same price range - point this out when it's true.
Be fair to both older and newer options: acknowledge a newer part's advantages (features, efficiency, longevity, driver support) even when an older part wins on raw price-to-performance.
When searching, include the current year ({today[-4:]}) in your search queries to get results for the correct time period.
When you need current information, perform ONE well-crafted, broad search query that covers everything you need rather than several narrow searches. Only search again if your first search truly returned nothing useful.
The search results may include a mix of old and recent articles. Prioritize information from the most recently dated sources, and ignore or de-weight anything that looks outdated relative to today's actual date.
Never state a specific price with full confidence unless it's clearly from a current, dated source. If prices are unclear, inconsistent across sources, or might be outdated, say so explicitly and give a realistic range instead of a single confident number.
If a search fails or returns nothing useful, do not keep retrying - answer with your best available knowledge, clearly flag that it may be outdated, and recommend the user verify current prices themselves.
Always base your final answer on the search results when available, not general assumptions.
You remember the whole conversation, so use earlier context (like the user's budget or use case) in later answers without needing it repeated."""


# ---- Session state setup (runs once) ----
if "client" not in st.session_state:
    st.session_state.client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY
    )
    st.session_state.tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    st.session_state.history = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.display_messages = []
    st.session_state.search_log = []


def ask_pc_builder(question):
    st.session_state.history.append({"role": "user", "content": question})

    MAX_ROUNDS = 3
    for round_num in range(MAX_ROUNDS):
        response = st.session_state.client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=st.session_state.history,
            tools=tools
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
                query = args["query"]
                st.session_state.search_log.append(query)

                search_results = search_web(query)

                st.session_state.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": search_results
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


# ---- UI ----
st.title("🖥️ PC Builder Advisor")
st.caption("Powered by NVIDIA Nemotron 3 Ultra + live web search")

with st.sidebar:
    st.subheader("Searches this session")
    if st.session_state.search_log:
        for q in st.session_state.search_log:
            st.write(f"🔍 {q}")
    else:
        st.write("No searches yet.")

    st.divider()
    if st.button("🔄 Start new conversation"):
        st.session_state.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.display_messages = []
        st.session_state.search_log = []
        st.rerun()

for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Ask about GPUs, CPUs, budgets, comparisons...")

if user_input:
    st.session_state.display_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Researching..."):
            answer = ask_pc_builder(user_input)
        st.write(answer)

    st.session_state.display_messages.append({"role": "assistant", "content": answer})