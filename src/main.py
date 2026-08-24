import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from .agents.resource_agent import (
    DENSE_MODEL_NAME,
    RERANKER_MODEL_NAME,
    SPARSE_MODEL_NAME,
    ResourceAgent,
)
from .logging_config import configure_logging
from .models import RoadmapRequest, RoadmapResponse, validate_goal_value
from .roadmap_engine import generate_roadmap, stream_roadmap_events

configure_logging()
logger = structlog.get_logger(__name__)

RATE_LIMIT = os.getenv("RATE_LIMIT", "5/minute")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the retrieval models (dense embedder, sparse embedder, reranker)
    # once at startup instead of lazily on first request, so request
    # latency doesn't include a first-hit model load, and /health can
    # honestly report whether they're ready.
    try:
        ResourceAgent._shared_dense_model = await asyncio.to_thread(TextEmbedding, DENSE_MODEL_NAME)
        ResourceAgent._shared_sparse_model = await asyncio.to_thread(SparseTextEmbedding, SPARSE_MODEL_NAME)
        ResourceAgent._shared_reranker = await asyncio.to_thread(TextCrossEncoder, RERANKER_MODEL_NAME)
        app.state.model_loaded = True
        logger.info(
            "startup.retrieval_models_loaded",
            dense_model=DENSE_MODEL_NAME,
            sparse_model=SPARSE_MODEL_NAME,
            reranker_model=RERANKER_MODEL_NAME,
        )
    except Exception as e:
        app.state.model_loaded = False
        logger.error("startup.retrieval_models_failed", error=str(e))
    yield


app = FastAPI(title="OpenRoadMap API", lifespan=lifespan)
app.state.model_loaded = False
app.state.limiter = limiter


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


app.add_middleware(CorrelationIdMiddleware)

# CORS: allow_origins=["*"] + allow_credentials=True is spec-invalid (browsers
# reject the combination, so credentials silently did nothing). No sessions
# exist in this API, so allow_credentials is dropped entirely rather than
# fixed - it isn't needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    correlation_id = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=429,
        content={
            "error": f"Rate limit exceeded ({exc.detail}). Please slow down and try again shortly.",
            "correlation_id": correlation_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error. Please try again later.",
            "correlation_id": correlation_id,
        },
    )


@app.post("/generate-roadmap", response_model=RoadmapResponse)
@limiter.limit(RATE_LIMIT)
async def create_roadmap(request: Request, payload: RoadmapRequest):
    # Any exception here is caught by the global unhandled_exception_handler
    # below, which logs the full error server-side with the request's
    # correlation id and returns only a generic message + that id to the
    # client (never the raw exception text).
    return await generate_roadmap(payload.goal)


def _sse_format(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def _sse_event_generator(goal: str, correlation_id: str):
    try:
        async for event, payload in stream_roadmap_events(goal):
            yield _sse_format(event, payload)
    except Exception as e:
        logger.error(
            "stream_roadmap.failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        yield _sse_format(
            "error",
            {
                "error": "Failed to generate roadmap. Please try again later.",
                "correlation_id": correlation_id,
            },
        )


@app.get("/v1/roadmap/stream")
@limiter.limit(RATE_LIMIT)
async def stream_roadmap(request: Request, goal: str = Query(...)):
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        goal = validate_goal_value(goal)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return StreamingResponse(
        _sse_event_generator(goal, correlation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Correlation-ID": correlation_id or ""},
    )


@app.get("/health")
async def health_check():
    model_loaded = bool(getattr(app.state, "model_loaded", False))
    return {"status": "ok" if model_loaded else "degraded", "embedding_model_loaded": model_loaded}


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
