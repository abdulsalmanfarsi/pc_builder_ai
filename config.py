import datetime
import os
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

TODAY = datetime.date.today().strftime("%B %d, %Y")
CURRENT_YEAR = str(datetime.date.today().year)

SYSTEM_PROMPT = f"""
You are a knowledgeable PC building advisor.

Whenever you recommend a complete PC build, you MUST format the build specs using this EXACT template:

[BUILD]
Name: Short descriptive build name
Use Case: Primary workload/gaming goal
CPU: Component model
GPU: Component model
Motherboard: Component model
RAM: Capacity and speed
Storage: Capacity and type
PSU: Wattage and efficiency rating
Cooler: Cooler model
Case: Cabinet model
Estimated Total: Price in Indian Rupees
[/BUILD]

Provide normal markdown descriptions before or after the build block.
Today's date is {TODAY}.
"""

# Tool schemas provided to the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the live web for current PC hardware prices, availability, or reviews.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_parts",
            "description": "Compare specs and pricing of up to 3 PC components.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of part names",
                    }
                },
                "required": ["parts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_builds",
            "description": "Search for component builds based on budget and workload.",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget": {"type": "string", "description": "Budget amount"},
                    "use_case": {
                        "type": "string",
                        "enum": ["gpu_heavy", "cpu_heavy", "casual"],
                    },
                    "existing_parts": {"type": "string"},
                },
                "required": ["budget", "use_case"],
            },
        },
    },
]