import httpx
from typing import Optional, Dict, Any, List, Union
from src.core.config import settings
from src.core.logger import logger
from src.llm.schemas import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMChatMessage,
    LLMChatRequest,
    LLMChatResponse,
)


class OllamaClient:
    def __init__(self):
        self.url = settings.ollama_url.rstrip("/")
        self.default_model = settings.ollama_model
        self.api_key = settings.ollama_api_key

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        stream: bool = False,
        timeout: float = 90.0,
    ) -> LLMGenerateResponse:
        endpoint_url = f"{self.url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.default_model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        logger.info(
            "Sending prompt to Ollama Cloud",
            extra={"model": self.default_model, "endpoint": endpoint_url, "temperature": temperature}
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(endpoint_url, json=payload, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                return LLMGenerateResponse.model_validate(data)
        except httpx.HTTPError as err:
            logger.error(
                "HTTP error during Ollama generation",
                extra={"model": self.default_model, "endpoint": endpoint_url, "error": str(err)}
            )
            raise

    async def generate_request(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        return await self.generate(
            prompt=request.prompt,
            system=request.system,
            temperature=request.temperature,
            stream=request.stream,
            timeout=request.timeout,
        )

    async def chat(
        self,
        messages: List[Union[Dict[str, str], LLMChatMessage]],
        temperature: float = 0.2,
        timeout: float = 90.0,
    ) -> LLMChatResponse:
        endpoint_url = f"{self.url}/api/chat"
        formatted_messages = [
            m.model_dump() if isinstance(m, LLMChatMessage) else m
            for m in messages
        ]
        payload = {
            "model": self.default_model,
            "messages": formatted_messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        logger.info(
            "Sending chat payload to Ollama Cloud",
            extra={"model": self.default_model, "endpoint": endpoint_url, "message_count": len(messages), "temperature": temperature}
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(endpoint_url, json=payload, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                return LLMChatResponse.model_validate(data)
        except httpx.HTTPError as err:
            logger.error(
                "HTTP error during Ollama chat",
                extra={"model": self.default_model, "endpoint": endpoint_url, "error": str(err)}
            )
            raise

    async def chat_request(self, request: LLMChatRequest) -> LLMChatResponse:
        return await self.chat(
            messages=request.messages,
            temperature=request.temperature,
            timeout=request.timeout,
        )
