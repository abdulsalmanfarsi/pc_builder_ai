"""
FastAPI server exposing the PC Builder AI as a web API.
Run with: uvicorn main:app --reload
"""

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
from tavily import TavilyClient

from config import TAVILY_API_KEY, SYSTEM_PROMPT
from core_engine import run_conversation


app = FastAPI(title="PC Builder Advisor API")


# ==========================================
# TAVILY CLIENT
# ==========================================

tavily_client = TavilyClient(
    api_key=TAVILY_API_KEY
)


# ==========================================
# REQUEST MODEL
# ==========================================

class AskRequest(BaseModel):
    question: str
    history: Optional[list] = None

    # User's selected market
    country: str = ""
    currency: str = ""


# ==========================================
# HEALTH CHECK
# ==========================================

@app.api_route(
    "/",
    methods=["GET", "HEAD"]
)
def health_check():
    """
    Simple endpoint to verify that the API is running.
    """

    return {
        "status": "PC Builder API is running"
    }


# ==========================================
# ASK AI
# ==========================================

@app.post("/ask")
def ask(request: AskRequest):
    """
    Takes a user question and optional conversation history,
    then runs the AI tool-calling loop.
    """

    # Start a fresh conversation if no history exists
    history = (
        request.history
        if request.history
        else [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]
    )

    result = run_conversation(
        tavily_client=tavily_client,
        history=history,
        question=request.question,

        # Market information from frontend
        country=request.country,
        currency=request.currency,
    )

    return result