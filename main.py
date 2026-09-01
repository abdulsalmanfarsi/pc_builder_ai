"""
FastAPI server exposing the PC Builder AI as a web API.
Run with: uvicorn main:app --reload
"""
from fastapi import FastAPI
from pydantic import BaseModel
from tavily import TavilyClient
from config import TAVILY_API_KEY, SYSTEM_PROMPT
from core_engine import run_conversation
from typing import Optional

app = FastAPI(title="PC Builder Advisor API")

# Just need the Tavily client - Gemini is called via HTTP
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


# This defines the SHAPE of data we expect the client (mobile app) to send us.
# FastAPI uses this to automatically check the request is formatted correctly.
class AskRequest(BaseModel):
    question: str
    history: Optional[list] = None  # optional - if not given, we start a fresh conversation


@app.api_route("/", methods=["GET", "HEAD"])
def health_check():
    """A simple endpoint to check the server is alive. Visit this in a browser.
    Supports both GET and HEAD, since uptime monitors often use HEAD requests."""
    return {"status": "PC Builder API is running"}


@app.post("/ask")
def ask(request: AskRequest):
    """The main endpoint - takes a question (and optional prior history),
    runs the AI + tool-calling loop, and returns the answer + updated history."""

    # If no history was sent, start a brand new conversation with the system prompt
    history = request.history if request.history else [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    result = run_conversation(tavily_client, history, request.question)
    return result
