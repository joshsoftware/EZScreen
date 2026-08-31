import asyncio
from typing import AsyncGenerator
from src.core.logger import logger

class TTSClient:
    """Generates PCM audio from text using a TTS provider."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Yields raw PCM chunks (24kHz) for the given text.
        """
        logger.debug(f"Synthesizing TTS: {text[:30]}...")
        
        # Stub: just yield a dummy 2400-byte frame of silence to simulate output
        dummy_chunk = b'\x00' * 2400
        yield dummy_chunk
        await asyncio.sleep(0.05)
