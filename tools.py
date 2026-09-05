import concurrent.futures
import datetime


def search_web(tavily_client, query, max_results=4):
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
    """Runs a separate, focused search for each part (max 3), IN PARALLEL,
    so each one gets fair, complete information without waiting on each other sequentially."""
    if len(parts) > 3:
        parts = parts[:3]

    def search_one(part):
        search_query = f"{part} price specs benchmarks {current_year}"
        result = search_web(tavily_client, search_query, max_results=3)
        return f"=== {part} ===\n{result}\n\n"

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(search_one, parts))

    return "".join(results)


def generate_builds(
    tavily_client,
    budget,
    use_case,
    existing_parts=None,
    region="",
    current_year=None
):
    """
    Searches for current PC component and pricing information.

    Region should come from the user's selected market.
    Never infer a country solely from a currency symbol.
    """

    if current_year is None:
        current_year = str(datetime.date.today().year)

    # ================================================
    # USE CASE
    # ================================================

    use_case_focus = {
        "gpu_heavy": (
            "gaming and GPU-intensive workloads, "
            "prioritizing graphics performance"
        ),

        "cpu_heavy": (
            "video editing, rendering, and content creation, "
            "prioritizing CPU multi-core performance"
        ),

        "casual": (
            "daily use and general computing, "
            "prioritizing reliability and value"
        )
    }

    focus_description = use_case_focus.get(
        use_case,
        "general PC build"
    )

    # ================================================
    # MARKET CONTEXT
    # ================================================

    region_hint = region.strip() if region else ""

    # ================================================
    # SEARCH FOR REAL BUILD + CURRENT PRICING
    # ================================================

    search_query = (
        f"current PC component prices {current_year} "
        f"{region_hint} "
        f"{focus_description} "
        f"total budget {budget} "
        f"CPU GPU motherboard RAM SSD storage PSU case cooler "
        f"current retailer prices available"
    )

    if existing_parts:

        search_query += (
            f" existing components {existing_parts} "
            f"find compatible upgrades only"
        )

    # ================================================
    # SEARCH RESULTS
    # ================================================

    result = search_web(
        tavily_client,
        search_query,
        max_results=6
    )

    return f"""
CURRENT MARKET SEARCH RESULTS

Budget: {budget}
Market/Region: {region_hint or "Not specified"}
Use case: {focus_description}

IMPORTANT:
The information below is current search data.

When generating the build:

1. Prefer component prices explicitly found in these results.

2. Do NOT invent an exact current component price.

3. Do NOT claim a precise estimated total unless enough
   component pricing information is available.

4. If pricing information is incomplete, use a broader
   price range and clearly acknowledge uncertainty.

5. Do NOT assume the cheapest result is always reliable.
   Prefer reputable retailers and currently available listings.

6. If Market/Region is specified, prioritize retailers and
   availability relevant to that market.

7. If Market/Region is not specified, do not claim that
   retrieved prices represent a specific country.

SEARCH RESULTS:

{result}
"""

def verify_component_prices(
    tavily_client,
    components,
    region="",
    current_year=None
):
    """
    Searches current prices for exact PC components.

    components: list of exact component names selected for a build.
    """

    if current_year is None:
        current_year = str(datetime.date.today().year)

    if not components:
        return "No components provided for price verification."

    # Limit searches to prevent excessive Tavily usage
    components = components[:8]

    def search_component(component):

        query = (
            f"{component} current price {current_year} "
            f"{region} retailer available"
        )

        result = search_web(
            tavily_client,
            query,
            max_results=3
        )

        return (
            f"\n=== PRICE CHECK: {component} ===\n"
            f"{result}\n"
        )

    # Run searches in parallel to keep response time reasonable
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=4
    ) as executor:

        results = list(
            executor.map(
                search_component,
                components
            )
        )

    return "".join(results)