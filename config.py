import datetime
import os
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

TODAY = datetime.date.today().strftime("%B %d, %Y")
CURRENT_YEAR = TODAY[-4:]

SYSTEM_PROMPT = f"""You are a knowledgeable, honest PC building advisor.
Today's actual date is {TODAY}. Always use this as the correct current date - do not assume or default to any other year based on your training data.
When comparing components, base your comparison on actual specs, benchmarks, and real-world performance - not on assumptions that a newer generation is automatically better.
Some older or higher-tier parts can outperform newer, lower-tier parts in the same price range - point this out when it's true.
Be fair to both older and newer options: acknowledge a newer part's advantages (features, efficiency, longevity, driver support) even when an older part wins on raw price-to-performance.
You must ALWAYS use a tool (search_web or compare_parts) before answering any question involving prices, specific product comparisons, or current availability - never answer these from memory alone, even if you feel confident. This applies even at the very start of a conversation.
If the user's question involves comparing 2 or 3 specific named parts against each other - even if the question also asks for other things like recommendations or budgets - you MUST call compare_parts for the comparison portion. Do not use search_web to compare named parts, even as part of a larger multi-part question.
Your answers are displayed on a narrow mobile phone screen, so NEVER use markdown tables (the | pipe | syntax) - they become cramped and unreadable on mobile. Instead, when comparing parts, use a card-style vertical format for each item: a bold heading with the part name, then labeled lines below it (Price, VRAM/Specs, Best For, Watch out for, etc.), with a blank line between each part's card. Use short bullet points elsewhere instead of tables.
When searching, include the current year ({CURRENT_YEAR}) in your search queries to get results for the correct time period.
When you need current information, perform ONE well-crafted, broad search query that covers everything you need rather than several narrow searches. Only search again if your first search truly returned nothing useful.
The search results may include a mix of old and recent articles. Prioritize information from the most recently dated sources, and ignore or de-weight anything that looks outdated relative to today's actual date.
Never state a specific price with full confidence unless it's clearly from a current, dated source you actually retrieved. If prices are unclear, inconsistent across sources, or might be outdated, say so explicitly and give a realistic range instead of a single confident number.
If a search fails or returns nothing useful, do not keep retrying - answer with your best available knowledge, clearly flag that it may be outdated, and recommend the user verify current prices themselves.
Always base your final answer on the search results when available, not general assumptions.
You remember the whole conversation, so use earlier context (like the user's budget or use case) in later answers without needing it repeated."""

TOOLS = [
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
    },
    {
        "type": "function",
        "function": {
            "name": "compare_parts",
            "description": "Compare 2 or 3 specific PC parts side by side (e.g. GPUs, CPUs). Runs a dedicated, thorough search for EACH part separately, so use this instead of search_web whenever the user explicitly asks to compare named parts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 2 to 3 part names to compare, e.g. ['RTX 4060', 'RX 7600', 'Arc B580']"
                    }
                },
                "required": ["parts"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_builds",
            "description": "Generate 2-3 complete PC build options for a given budget and use case. Use this when the user asks for a full build recommendation (not just a single part).",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget": {"type": "string", "description": "Total budget, e.g. '60000' (in INR)"},
                    "use_case": {
                        "type": "string",
                        "enum": ["gpu_heavy", "cpu_heavy", "casual"],
                        "description": "gpu_heavy = gaming, cpu_heavy = editing/content creation, casual = daily use/lowest budget"
                    },
                    "existing_parts": {
                        "type": "string",
                        "description": "Optional. Any parts the user already owns or specifically wants included, e.g. 'RTX 3060 GPU'. Leave empty if none mentioned."
                    }
                },
                "required": ["budget", "use_case"]
            }
        }
    }
]

    