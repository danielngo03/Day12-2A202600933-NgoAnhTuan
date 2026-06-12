"""Redis-backed monthly budget guard."""
from datetime import datetime, timezone

from fastapi import HTTPException
from redis import Redis

from app.config import settings


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def budget_key(user_id: str) -> str:
    return f"budget:{user_id}:{current_month()}"


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1000) * 0.00015
    output_cost = (output_tokens / 1000) * 0.0006
    return max(settings.estimated_request_cost_usd, input_cost + output_cost)


def check_and_record_budget(redis_client: Redis, user_id: str, estimated_cost: float) -> dict:
    key = budget_key(user_id)
    current = float(redis_client.get(key) or 0.0)

    if current + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(current, 6),
                "estimated_cost_usd": round(estimated_cost, 6),
                "budget_usd": settings.monthly_budget_usd,
                "resets_at": "first day of next UTC month",
            },
        )

    new_total = float(redis_client.incrbyfloat(key, estimated_cost))
    redis_client.expire(key, 32 * 24 * 3600)

    return {
        "used_usd": round(new_total, 6),
        "budget_usd": settings.monthly_budget_usd,
        "remaining_usd": round(max(0.0, settings.monthly_budget_usd - new_total), 6),
    }


def get_budget(redis_client: Redis, user_id: str) -> dict:
    used = float(redis_client.get(budget_key(user_id)) or 0.0)
    return {
        "user_id": user_id,
        "month": current_month(),
        "used_usd": round(used, 6),
        "budget_usd": settings.monthly_budget_usd,
        "remaining_usd": round(max(0.0, settings.monthly_budget_usd - used), 6),
    }
