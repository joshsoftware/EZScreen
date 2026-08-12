from src.llm.schemas import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMChatMessage,
    LLMChatRequest,
    LLMChatResponse,
)
from src.llm.client import OllamaClient

llm_client = OllamaClient()

__all__ = [
    "llm_client",
    "OllamaClient",
    "LLMGenerateRequest",
    "LLMGenerateResponse",
    "LLMChatMessage",
    "LLMChatRequest",
    "LLMChatResponse",
]
