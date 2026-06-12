"""Redis-backed sliding-window rate limiting."""
import time
from uuid import uuid4

from fastapi import HTTPException
from redis import Redis

from app.config import settings


def check_rate_limit(redis_client: Redis, user_id: str) -> dict:
    now = time.time()
    window_start = now - settings.rate_limit_window_seconds
    key = f"rate:{user_id}"

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    _, current = pipe.execute()

    reset_at = int(now + settings.rate_limit_window_seconds)
    if current >= settings.rate_limit_per_minute:
        oldest = redis_client.zrange(key, 0, 0, withscores=True)
        retry_after = settings.rate_limit_window_seconds
        if oldest:
            retry_after = max(1, int(oldest[0][1] + settings.rate_limit_window_seconds - now) + 1)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": settings.rate_limit_per_minute,
                "window_seconds": settings.rate_limit_window_seconds,
                "retry_after_seconds": retry_after,
            },
            headers={
                "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(retry_after),
            },
        )

    member = f"{now}:{uuid4().hex}"
    pipe = redis_client.pipeline()
    pipe.zadd(key, {member: now})
    pipe.expire(key, settings.rate_limit_window_seconds)
    pipe.execute()

    remaining = settings.rate_limit_per_minute - current - 1
    return {
        "limit": settings.rate_limit_per_minute,
        "remaining": max(0, remaining),
        "reset_at": reset_at,
    }
