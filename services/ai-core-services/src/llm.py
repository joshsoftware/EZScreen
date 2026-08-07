import httpx
from typing import Optional, Dict, Any, List
from src.core.config import settings
from src.core.logger import logger


class OllamaClient:
    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.url = (url or settings.OLLAMA_URL).rstrip("/")
        self.default_model = model or settings.OLLAMA_MODEL
        self.api_key = api_key or settings.OLLAMA_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        stream: bool = False,
        timeout: float = 90.0,
    ) -> str:
        """
        Sends prompt generation request to Ollama Cloud/Remote endpoint.
        Uses OLLAMA_MODEL from env by default.
        """
        target_model = model or self.default_model
        endpoint_url = f"{self.url}/api/generate"
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        logger.info(f"Sending prompt to Ollama Cloud model '{target_model}' at {endpoint_url}")
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint_url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        timeout: float = 90.0,
    ) -> Dict[str, Any]:
        """
        Sends chat conversation history to Ollama Cloud/Remote endpoint.
        Uses OLLAMA_MODEL from env by default.
        """
        target_model = model or self.default_model
        endpoint_url = f"{self.url}/api/chat"
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        logger.info(f"Sending chat payload to Ollama Cloud model '{target_model}' at {endpoint_url}")
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint_url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            return response.json()


# Direct LLM Client instance configured via environment variables
llm_client = OllamaClient()
