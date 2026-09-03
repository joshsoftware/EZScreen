"""Shared pytest configuration for ai-core-services.

Sets missing Settings fields so collection can import modules that load config.
"""

from __future__ import annotations

import os

# Defaults for local/unit tests when .env is incomplete (do not override real values).
_TEST_ENV_DEFAULTS = {
    "WEBHOOK_URL": "http://localhost:8002/screening/webhook",
    "CORE_API_URL": "http://localhost:8000",
    "WEBSOCKET_URL": "ws://localhost:8002/attendee-websocket",
    "SERVICE_NAME": "ai-core-services",
    "PORT": "8002",
    "ENVIRONMENT": "test",
    "LOG_LEVEL": "INFO",
    "OLLAMA_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "test-model",
    "OLLAMA_API_KEY": "test-key",
    "ATTENDEE_API_KEY": "",
    "ATTENDEE_API_URL": "https://api.attendee.dev/v1",
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/ezscreen",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "minio",
    "MINIO_SECRET_KEY": "minio",
    "MINIO_BUCKET_NAME": "resumes",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)
