import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
from config import NVIDIA_API_KEY, TAVILY_API_KEY, SYSTEM_PROMPT
from ai_engine import ask_pc_builder

st.set_page_config(page_title="PC Builder Advisor", page_icon="🖥️", layout="centered")

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
    st.rerun()