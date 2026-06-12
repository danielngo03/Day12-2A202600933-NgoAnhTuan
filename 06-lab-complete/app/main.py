"""Production AI Agent combining Day 12 deployment concepts."""
import json
import logging
import re
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis
import uvicorn

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_and_record_budget, estimate_cost, get_budget
from app.rate_limiter import check_rate_limit
from utils.mock_llm import ask as llm_ask


class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }
        message = record.getMessage()
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict):
                payload.update(parsed)
            else:
                payload["message"] = message
        except json.JSONDecodeError:
            payload["message"] = message
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(
    level=logging.DEBUG if settings.debug else getattr(logging, settings.log_level.upper(), logging.INFO),
    handlers=[handler],
    force=True,
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = f"agent-{uuid4().hex[:8]}"
_is_ready = False


def json_log(event: str, **fields):
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def history_key(user_id: str) -> str:
    return f"history:{user_id}"


def load_history(redis_client: Redis, user_id: str) -> list[dict]:
    raw_messages = redis_client.lrange(history_key(user_id), 0, -1)
    return [json.loads(item) for item in raw_messages]


def append_history(redis_client: Redis, user_id: str, role: str, content: str) -> None:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    key = history_key(user_id)
    pipe = redis_client.pipeline()
    pipe.rpush(key, json.dumps(message, ensure_ascii=False))
    pipe.ltrim(key, -settings.max_history_messages, -1)
    pipe.expire(key, settings.history_ttl_seconds)
    pipe.execute()


def answer_with_context(question: str, history: list[dict]) -> str:
    question_lower = question.lower()
    if "what did i just say" in question_lower or "what was my last" in question_lower:
        for message in reversed(history):
            if message.get("role") == "user":
                return f'You just said: "{message["content"]}".'
    if "what is my name" in question_lower or "what's my name" in question_lower:
        for message in reversed(history):
            if message.get("role") != "user":
                continue
            match = re.search(r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{0,60})", message["content"], re.I)
            if match:
                name = match.group(1).strip(" .")
                return f"Your name is {name}."
    return llm_ask(question)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()
    app.state.redis = redis_client
    _is_ready = True
    json_log(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        instance_id=INSTANCE_ID,
        redis_url_configured=bool(settings.redis_url),
    )

    yield

    _is_ready = False
    json_log("graceful_shutdown", instance_id=INSTANCE_ID)
    redis_client.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    start = time.time()
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        redis_client.incr("metrics:total_requests")

    try:
        response: Response = await call_next(request)
    except Exception:
        if redis_client:
            redis_client.incr("metrics:error_count")
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Instance-ID"] = INSTANCE_ID
    if "server" in response.headers:
        del response.headers["server"]
    json_log(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round((time.time() - start) * 1000, 1),
    )
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field("default-user", min_length=1, max_length=100)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_length: int
    rate_limit: dict
    budget: dict
    served_by: str
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "usage": "GET /usage/{user_id} (requires X-API-Key)",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
):
    redis_client = get_redis(request)
    rate_info = check_rate_limit(redis_client, body.user_id)

    history_before = load_history(redis_client, body.user_id)
    input_tokens = max(1, len(body.question.split()) * 2)
    estimated = estimate_cost(input_tokens=input_tokens, output_tokens=80)
    budget_info = check_and_record_budget(redis_client, body.user_id, estimated)

    append_history(redis_client, body.user_id, "user", body.question)
    answer = answer_with_context(body.question, history_before)
    append_history(redis_client, body.user_id, "assistant", answer)
    history_after = load_history(redis_client, body.user_id)

    json_log(
        "agent_response",
        user_id=body.user_id,
        question_length=len(body.question),
        answer_length=len(answer),
        history_messages=len(history_after),
        budget_used_usd=budget_info["used_usd"],
    )

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_length=len(history_after),
        rate_limit=rate_info,
        budget=budget_info,
        served_by=INSTANCE_ID,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/ask", tags=["Agent"])
def ask_requires_post(_api_key: str = Depends(verify_api_key)):
    raise HTTPException(status_code=405, detail="Use POST /ask with a JSON body.")


@app.get("/history/{user_id}", tags=["Agent"])
def get_history(
    user_id: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
):
    history = load_history(get_redis(request), user_id)
    return {"user_id": user_id, "messages": history, "count": len(history)}


@app.delete("/history/{user_id}", tags=["Agent"])
def clear_history(
    user_id: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
):
    deleted = get_redis(request).delete(history_key(user_id))
    return {"user_id": user_id, "deleted": bool(deleted)}


@app.get("/usage/{user_id}", tags=["Operations"])
def usage(
    user_id: str,
    request: Request,
    _api_key: str = Depends(verify_api_key),
):
    return get_budget(get_redis(request), user_id)


@app.get("/health", tags=["Operations"])
def health(request: Request):
    redis_status = "unknown"
    try:
        get_redis(request).ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "checks": {"redis": redis_status, "llm": "mock" if not settings.openai_api_key else "openai"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready(request: Request):
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Application is not ready.")
    try:
        get_redis(request).ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis not ready: {exc}") from exc
    return {"ready": True, "instance_id": INSTANCE_ID}


@app.get("/metrics", tags=["Operations"])
def metrics(request: Request, _api_key: str = Depends(verify_api_key)):
    redis_client = get_redis(request)
    total_requests = int(redis_client.get("metrics:total_requests") or 0)
    error_count = int(redis_client.get("metrics:error_count") or 0)
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": total_requests,
        "error_count": error_count,
        "instance_id": INSTANCE_ID,
    }


def _handle_signal(signum, _frame):
    json_log("signal_received", signum=signum, message="uvicorn will run graceful shutdown")


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
