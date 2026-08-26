import datetime
import streamlit as st


def get_tavily_client(client_arg=None):
    if client_arg is not None:
        return client_arg
    if hasattr(st, "session_state") and "tavily_client" in st.session_state:
        return st.session_state.tavily_client
    return None


def search_web(tavily_client=None, query="", max_results=6):
    client = get_tavily_client(tavily_client)
    if not client:
        return "Search client unavailable. Answering using built-in hardware knowledge."

    try:
        response = client.search(query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return "No search results found for this query."
        formatted = ""
        for r in results:
            formatted += f"Title: {r['title']}\nContent: {r['content']}\nURL: {r['url']}\n\n"
        return formatted
    except Exception as e:
        return f"Search failed (error: {e}). Answering using built-in knowledge."


def compare_parts(tavily_client=None, parts=None, current_year=None):
    if parts is None:
        parts = []
    if len(parts) > 3:
        parts = parts[:3]

    client = get_tavily_client(tavily_client)
    comparison_results = ""
    for part in parts:
        search_query = f"{part} price specs benchmarks {current_year or ''}"
        result = search_web(client, search_query, max_results=4)
        comparison_results += f"=== {part} ===\n{result}\n\n"

    return comparison_results


def generate_builds(
    tavily_client=None, budget="", use_case="", existing_parts=None, current_year=None
):
    client = get_tavily_client(tavily_client)
    if current_year is None:
        current_year = str(datetime.date.today().year)

    use_case_focus = {
        "gpu_heavy": "gaming/GPU-intensive PC build",
        "cpu_heavy": "editing/CPU-intensive PC build",
        "casual": "budget daily-use PC build",
    }
    focus_description = use_case_focus.get(use_case, "general PC build")

    search_query = f"best {focus_description} under {budget} rupees India {current_year} complete build"
    if existing_parts:
        search_query += f" compatible with {existing_parts}"

    return search_web(client, search_query, max_results=6)