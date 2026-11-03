"""FastAPI backend.

    POST /chat        {question, category?, top_k?, history?}  -> answer / clarify / escalate + sources
    POST /search      retrieval only (debugging / evaluation)
    GET  /health      status of the knowledge base and LLM provider
    GET  /categories  categories with chunk counts

Run:  uvicorn jklu.api:app --port 8000      (or just `python run.py`)
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import List, Literal, Optional
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config as C
from .utils import log

_agent = None
_lock = threading.Lock()
_load_error: str | None = None


def get_agent():
    """Lazy, thread-safe singleton; builds the index first if it is missing."""
    global _agent, _load_error
    if _agent is not None:
        return _agent
    with _lock:
        if _agent is None:
            try:
                from .agent import JKLUAgent
                from .index import ensure_index, index_is_current
                chunks_ok = C.CHUNKS_PATH.is_file() and C.CHUNKS_PATH.stat().st_size > 100
                if not chunks_ok:
                    log.warning("chunks.jsonl missing or empty - attempting emergency offline ingestion...")
                    from .ingest import run_ingestion
                    run_ingestion(offline=True)
                    if not C.CHUNKS_PATH.is_file() or C.CHUNKS_PATH.stat().st_size == 0:
                        raise RuntimeError("chunks.jsonl is empty - run the ingestion phase first (python scripts/prepare_kb.py)")
                if not index_is_current(want_semantic=True):
                    log.info("Vector index not current - building index...")
                    ensure_index(force=False, allow_semantic=True)
                _agent = JKLUAgent()
                _load_error = None
            except Exception as exc:
                _load_error = f"{type(exc).__name__}: {exc}"
                log.error("agent failed to load: %s", _load_error)
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # If the knowledge base was pre-built, load synchronously so the chatbot is instantly ready.
    # Otherwise run in background thread so Uvicorn binds port quickly to avoid cloud provider timeouts.
    chunks_ok = C.CHUNKS_PATH.is_file() and C.CHUNKS_PATH.stat().st_size > 100
    faiss_ok = C.FAISS_PATH.is_file() or C.FAISS_PATH.with_name(C.FAISS_PATH.name + ".npy").is_file()
    if chunks_ok and faiss_ok:
        try:
            get_agent()
        except Exception as exc:
            log.error("Startup agent load failed: %s", exc)
    else:
        threading.Thread(target=get_agent, daemon=True, name="agent-init").start()
    yield


app = FastAPI(title="JKLU University Information Agent", version="2.0", lifespan=lifespan)
_raw_origins = os.environ.get("JKLU_CORS_ORIGINS", "").strip()
if _raw_origins == "*":
    _ORIGINS = ["*"]
elif _raw_origins:
    _ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    _ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app" if _raw_origins != "*" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    category: Optional[str] = None
    top_k: int = Field(default=C.TOP_K, ge=1, le=10)
    history: Optional[List[Turn]] = None


@app.get("/health")
@app.get("/api/health")
def health():
    agent = get_agent()
    return {
        "status": "ok" if agent else "unavailable",
        "error": _load_error,
        "chunks": len(agent.kb.chunks) if agent else 0,
        "retrieval": ("semantic+bm25" if agent.kb.semantic else "lexical+bm25") if agent else None,
        "llm_provider": agent.generator.provider if agent else None,
    }


@app.get("/categories")
@app.get("/api/categories")
def categories():
    agent = get_agent()
    if not agent:
        raise HTTPException(503, _load_error or "knowledge base not ready")
    counts = Counter(c["category"] for c in agent.kb.chunks)
    return {"categories": [{"name": c, "chunks": counts.get(c, 0)} for c in C.CATEGORIES]}


@app.post("/chat")
@app.post("/api/chat")
def chat(req: ChatRequest):
    agent = get_agent()
    if not agent:
        raise HTTPException(503, _load_error or "knowledge base not ready - run `python run.py`")
    history = [(t.model_dump() if hasattr(t, 'model_dump') else t.dict()) for t in req.history][-C.MAX_HISTORY_TURNS:] if req.history else None
    res = agent.ask(req.question, category=req.category, top_k=req.top_k, history=history)
    if "timings" in res:
        t_ser = time.perf_counter()
        _ = json.dumps(res, default=str)
        res["timings"]["response_serialization_ms"] = round((time.perf_counter() - t_ser) * 1000, 2)
    return res


@app.post("/chat/stream")
@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    agent = get_agent()
    if not agent:
        raise HTTPException(503, _load_error or "knowledge base not ready - run `python run.py`")

    history = [(t.model_dump() if hasattr(t, 'model_dump') else t.dict()) for t in req.history][-C.MAX_HISTORY_TURNS:] if req.history else None

    async def event_generator():
        # 1. status event
        yield f"event: status\ndata: {json.dumps({'message': 'Searching verified JKLU records…'})}\n\n"

        # Ask agent
        res = agent.ask(req.question, category=req.category, top_k=req.top_k, history=history)

        # 2. evidence event
        evidence_items = []
        for s in (res.get("sources") or [])[:5]:
            is_live = s.get("source_type") == "live" or s.get("is_live")
            evidence_items.append({
                "n": s.get("n", 1),
                "title": s.get("title") or "Verified Document",
                "url": s.get("url") or s.get("source_url"),
                "snippet": s.get("snippet") or (s.get("text") or "")[:180],
                "score": s.get("score") or s.get("similarity_score", 1.0),
                "tag": "Live from jklu.edu.in" if is_live else "Verified document",
            })
        yield f"event: evidence\ndata: {json.dumps({'evidence': evidence_items})}\n\n"

        # 3. token stream event
        full_answer = res.get("answer", "")
        # Stream answer in chunks of words for perceived speed
        words = re.findall(r"\S+|\s+", full_answer)
        chunk_buf = []
        for w in words:
            chunk_buf.append(w)
            if len(chunk_buf) >= 4 or "\n" in w:
                yield f"event: token\ndata: {json.dumps({'token': ''.join(chunk_buf)})}\n\n"
                chunk_buf = []
        if chunk_buf:
            yield f"event: token\ndata: {json.dumps({'token': ''.join(chunk_buf)})}\n\n"

        # 4. done event
        done_payload = dict(res)
        done_payload["response_serialization_ms"] = 0.5
        yield f"event: done\ndata: {json.dumps(done_payload, default=str)}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.post("/search")
@app.post("/api/search")
def search(req: ChatRequest):
    agent = get_agent()
    if not agent:
        raise HTTPException(503, _load_error or "knowledge base not ready")
    out = agent.kb.search(req.question, top_k=req.top_k, category=req.category)
    for r in out["results"]:
        r["text"] = r["text"][:600]
    return out


# ------------------------------------------------------------------ feedback
class FeedbackRequest(BaseModel):
    request_id: Optional[str] = Field(default=None, max_length=40)
    rating: Optional[Literal["up", "down"]] = None
    comment: Optional[str] = Field(default=None, max_length=500)
    question: Optional[str] = Field(default=None, max_length=300)
    status: Optional[str] = Field(default=None, max_length=20)


_fb_lock = threading.Lock()
FEEDBACK_PATH = C.DATA_DIR / "feedback.jsonl"


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    """Stores thumbs up/down and free-text feedback locally (data/feedback.jsonl). Updates Self-Agentic RAG memory."""
    if req.rating is None and not (req.comment or "").strip():
        raise HTTPException(422, "Provide a rating or a comment.")
    row = {"ts": int(time.time()), **(req.model_dump() if hasattr(req, "model_dump") else req.dict())}
    try:
        with _fb_lock:
            FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FEEDBACK_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        # Reinforce or down-rank Self-Agentic RAG learned memory
        agent = get_agent()
        if agent and hasattr(agent, "memory") and req.rating:
            agent.memory.record_feedback(req.request_id, req.rating, req.question)
    except OSError as exc:
        raise HTTPException(500, f"Could not store feedback: {exc.__class__.__name__}")
    return {"ok": True}


@app.get("/api/learning/stats")
def learning_stats():
    """Returns real-time statistics and learned query clusters from Self-Agentic RAG."""
    agent = get_agent()
    if not agent or not hasattr(agent, "memory"):
        return {"total_clusters": 0, "total_phrasings_learned": 0, "total_hits": 0, "clusters": []}
    return agent.memory.stats()


# -------------------------------------------------------------- web UI (static)
# New React UI (frontend/dist, built from frontend/ui). The earlier plain-JS UI stays available at /classic.
DIST_DIR = C.ROOT / "frontend" / "ui" / "dist" if (C.ROOT / "frontend" / "ui" / "dist" / "index.html").is_file() else (C.ROOT / "frontend" / "dist")
WEB_DIR = C.ROOT / "frontend" / "web"

if (DIST_DIR / "index.html").is_file():
    if (DIST_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(DIST_DIR / "index.html", headers={"Cache-Control": "no-cache"})

if (WEB_DIR / "index.html").is_file():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/classic", include_in_schema=False)
    def classic():
        return FileResponse(WEB_DIR / "index.html")

    if not (DIST_DIR / "index.html").is_file():      # no React build present: fall back to the classic UI at "/"
        @app.get("/", include_in_schema=False)
        def index_classic():
            return FileResponse(WEB_DIR / "index.html")
