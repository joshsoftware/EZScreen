"""HTTP client for ai-core → core-api screening persistence callbacks."""

from __future__ import annotations

import httpx

from src.core.config import settings

__all__ = ["core_api_url", "internal_headers", "post_json"]

_INTERNAL_HEADER = "X-Internal-Service-Token"


def internal_headers() -> dict[str, str]:
    token = (settings.internal_service_token or "").strip()
    if not token:
        return {}
    return {_INTERNAL_HEADER: token}


def core_api_url(path: str) -> str:
    base = settings.core_api_base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def post_json(
    path: str,
    payload: dict,
    *,
    timeout: float = 30.0,
) -> httpx.Response:
    with httpx.Client(timeout=timeout) as client:
        return client.post(
            core_api_url(path),
            json=payload,
            headers=internal_headers(),
        )
