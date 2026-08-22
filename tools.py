import datetime


def search_web(tavily_client, query, max_results=6):
    """Actually performs the web search via Tavily. No Streamlit dependency -
    the caller passes in the tavily_client to use."""
    try:
        response = tavily_client.search(query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return "No search results found for this query."
        formatted = ""
        for r in results:
            formatted += f"Title: {r['title']}\nContent: {r['content']}\nURL: {r['url']}\n\n"
        return formatted
    except Exception as e:
        return f"Search failed (error: {e}). Please answer using whatever information you already have, and mention that live search wasn't available."


def compare_parts(tavily_client, parts, current_year):
    """Runs a separate, focused search for each part (max 3),
    so each one gets fair, complete information instead of one blended search."""
    if len(parts) > 3:
        parts = parts[:3]

    comparison_results = ""
    for part in parts:
        search_query = f"{part} price specs benchmarks {current_year}"
        result = search_web(tavily_client, search_query, max_results=4)
        comparison_results += f"=== {part} ===\n{result}\n\n"

    return comparison_results


def generate_builds(tavily_client, budget, use_case, existing_parts=None, current_year=None):
    """Searches for parts fitting the budget and use case, so the AI can
    construct 2-3 complete build options."""
    if current_year is None:
        current_year = str(datetime.date.today().year)

    use_case_focus = {
        "gpu_heavy": "gaming/GPU-intensive PC build, prioritizing graphics card performance",
        "cpu_heavy": "video editing/content creation PC build, prioritizing CPU multi-core performance",
        "casual": "budget daily-use PC build, prioritizing reliability and lowest cost over raw performance"
    }
    focus_description = use_case_focus.get(use_case, "general PC build")

    search_query = f"best {focus_description} under {budget} rupees India {current_year} complete build"
    if existing_parts:
        search_query += f" compatible with {existing_parts}"

    result = search_web(tavily_client, search_query, max_results=6)
    return result