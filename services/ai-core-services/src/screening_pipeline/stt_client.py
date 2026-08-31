import asyncio
from typing import Callable
from src.core.logger import logger

class DeepgramSTTClient:
    """Streams PCM audio to Deepgram via WebSocket and emits transcription events."""
    
    def __init__(self, api_key: str, on_transcript: Callable[[str], None]):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._is_connected = False
    
    async def connect(self):
        """Establish WebSocket connection to STT namespace."""
        logger.info("Initializing STT connection")
        self._is_connected = True
    
    async def send_audio(self, pcm_bytes: bytes):
        """Send raw PCM chunk to STT."""
        if not self._is_connected:
            return
        pass
    
    async def close(self):
        """Gracefully close STT connection."""
        self._is_connected = False
        logger.info("Closed STT connection")
