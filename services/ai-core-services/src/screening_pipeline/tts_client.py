import asyncio
import httpx
from typing import AsyncGenerator
from src.core.logger import logger

class KokoroCloudTTSClient:
    """Generates PCM audio from text using the Kokoro Cloud API."""
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url or "https://api.replicate.com/v1/predictions"
        self.api_key = api_key
    
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Yields raw PCM chunks (24kHz) for the given text.
        """
        if not self.api_key:
            logger.warning("KOKORO_API_KEY is not set, defaulting to silence stub.")
            yield b'\x00' * 2400
            await asyncio.sleep(0.05)
            return

        logger.debug(f"Synthesizing TTS via Kokoro: {text[:30]}...")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # NOTE: This payload format is an example (e.g. Replicate format). 
        # Update this to match your exact Kokoro Cloud API provider.
        payload = {
            "input": {
                "text": text,
                "voice": "af_bella" # Default kokoro voice
            }
        }
        
        try:
            # For APIs that stream the audio back immediately (like standard TTS APIs)
            async with httpx.AsyncClient() as client:
                # If the API returns a direct stream of bytes (WAV/PCM)
                async with client.stream("POST", self.api_url, json=payload, headers=headers, timeout=15.0) as response:
                    response.raise_for_status()
                    
                    # Note: If Kokoro returns a WAV file with headers, 
                    # the first few chunks will contain the WAV header. 
                    # A robust implementation would strip the 44-byte WAV header here.
                    is_first_chunk = True
                    async for chunk in response.aiter_bytes(chunk_size=2400):
                        if is_first_chunk and chunk.startswith(b'RIFF'):
                            # Strip 44 byte WAV header safely
                            chunk = chunk[44:]
                            is_first_chunk = False
                        yield chunk
        except Exception as e:
            logger.error(f"Kokoro TTS synthesis failed: {e}")
            # Fallback to silence if API fails
            yield b'\x00' * 2400
            await asyncio.sleep(0.05)
