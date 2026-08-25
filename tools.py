import concurrent.futures
import datetime
import time


def search_web(tavily_client, query, max_results=4):
    """Perform a web search and log how long it takes."""

    start_time = time.time()

    try:
        response = tavily_client.search(
            query,
            max_results=max_results
        )

        elapsed = time.time() - start_time
        print(f"\n[TIMING] Tavily search: {elapsed:.2f} seconds")
        print(f"[SEARCH] {query}\n")

        results = response.get("results", [])

        if not results:
            return "No search results found for this query."

        formatted = ""

        for r in results:
            formatted += (
                f"Title: {r.get('title', '')}\n"
                f"Content: {r.get('content', '')}\n"
                f"URL: {r.get('url', '')}\n\n"
            )

        return formatted

    except Exception as e:
        elapsed = time.time() - start_time

        print(
            f"\n[TIMING] Tavily search failed after "
            f"{elapsed:.2f} seconds"
        )

        return (
            f"Search failed (error: {e}). "
            "Please answer using whatever information you already have, "
            "and mention that live search wasn't available."
        )


def compare_parts(tavily_client, parts, current_year):
    """
    Compare up to 3 PC parts.

    Searches for each part simultaneously instead of sequentially.
    """

    if len(parts) > 3:
        parts = parts[:3]

    start_time = time.time()

    print(f"\n[COMPARE] Comparing: {', '.join(parts)}")

    def search_one(part):

        search_query = (
            f"{part} price specs benchmarks "
            f"{current_year}"
        )

        result = search_web(
            tavily_client,
            search_query,
            max_results=3
        )

        return f"=== {part} ===\n{result}\n\n"

    # Run searches in parallel
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(parts)
    ) as executor:

        results = list(
            executor.map(
                search_one,
                parts
            )
        )

    elapsed = time.time() - start_time

    print(
        f"[TIMING] Total compare_parts time: "
        f"{elapsed:.2f} seconds\n"
    )

    return "".join(results)


def generate_builds(
    tavily_client,
    budget,
    use_case,
    existing_parts=None,
    current_year=None
):
    """
    Search for information needed to generate
    a complete PC build.
    """

    start_time = time.time()

    if current_year is None:
        current_year = str(
            datetime.date.today().year
        )

    use_case_focus = {

        "gpu_heavy":
            "gaming GPU-intensive PC build "
            "prioritizing graphics card performance",

        "cpu_heavy":
            "video editing content creation PC build "
            "prioritizing CPU multi-core performance",

        "casual":
            "budget daily-use PC build "
            "prioritizing reliability and lowest cost "
            "over raw performance"
    }

    focus_description = use_case_focus.get(
        use_case,
        "general PC build"
    )

    search_query = (
        f"best {focus_description} "
        f"under {budget} "
        f"{current_year} "
        f"complete PC build"
    )

    if existing_parts:
        search_query += (
            f" compatible with "
            f"{existing_parts}"
        )

    print(
        f"\n[BUILD SEARCH] "
        f"Budget: {budget}"
    )

    result = search_web(
        tavily_client,
        search_query,
        max_results=4
    )

    elapsed = time.time() - start_time

    print(
        f"[TIMING] Total generate_builds time: "
        f"{elapsed:.2f} seconds\n"
    )

    return result