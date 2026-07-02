import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import ChatRequest, ChatResponse
from .retrieval import CatalogIndex
from .agent import handle_chat

app = FastAPI(title="SHL Assessment Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CATALOG_PATH = os.environ.get("CATALOG_PATH", "data/catalog.json")
if not Path(CATALOG_PATH).exists():
    # fall back to the small bootstrap sample so the service still boots
    CATALOG_PATH = "data/catalog.sample.json"

_index = CatalogIndex(CATALOG_PATH)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply, recommendations, end_of_conversation = handle_chat(req.messages, _index)
    return ChatResponse(
        reply=reply,
        recommendations=recommendations,
        end_of_conversation=end_of_conversation,
    )
