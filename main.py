"""
FastAPI server exposing the PC Builder AI as a web API.
Run with: uvicorn main:app --reload
"""
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from tavily import TavilyClient
from config import NVIDIA_API_KEY, TAVILY_API_KEY, SYSTEM_PROMPT
from core_engine import run_conversation
from typing import Optional

app = FastAPI(title="PC Builder Advisor API")

# These clients are created once when the server starts, and reused for every request
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
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
    return {"status": "PC Builder API is running - test branch"}


@app.post("/ask")
def ask(request: AskRequest):
    """The main endpoint - takes a question (and optional prior history),
    runs the AI + tool-calling loop, and returns the answer + updated history."""
    
    # If no history was sent, start a brand new conversation with the system prompt
    history = request.history if request.history else [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    result = run_conversation(client, tavily_client, history, request.question)
    return result