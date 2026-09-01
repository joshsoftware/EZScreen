import asyncio
import httpx
from typing import AsyncGenerator
from src.core.logger import logger

import os
import numpy as np
from src.core.config import settings

class LocalKokoroTTSClient:
    """Generates PCM audio using a local Kokoro-82M ONNX model."""
    
    def __init__(self, model_dir: str = ".models"):
        self.model_dir = model_dir
        self.model_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
        self.voices_path = os.path.join(model_dir, "voices-v1.0.bin")
        self.kokoro = None
        self._download_lock = asyncio.Lock()
        
    async def _ensure_models(self):
        """Downloads the ONNX model and voices binary if they don't exist."""
        if os.path.exists(self.model_path) and os.path.exists(self.voices_path):
            if self.kokoro is None:
                from kokoro_onnx import Kokoro
                self.kokoro = Kokoro(self.model_path, self.voices_path)
            return

        async with self._download_lock:
            # Double check in case another task downloaded it while we were waiting
            if os.path.exists(self.model_path) and os.path.exists(self.voices_path):
                if self.kokoro is None:
                    from kokoro_onnx import Kokoro
                    self.kokoro = Kokoro(self.model_path, self.voices_path)
                return
                
            logger.info("Downloading local Kokoro-82M model files (~80MB)... This only happens once.")
            os.makedirs(self.model_dir, exist_ok=True)
            
            async with httpx.AsyncClient(follow_redirects=True) as client:
                # Download ONNX
                logger.info("Downloading kokoro-v1.0.onnx...")
                resp = await client.get("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx", timeout=300.0)
                resp.raise_for_status()
                with open(self.model_path, "wb") as f:
                    f.write(resp.content)
                    
                # Download voices
                logger.info("Downloading voices-v1.0.bin...")
                resp = await client.get("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", timeout=60.0)
                resp.raise_for_status()
                with open(self.voices_path, "wb") as f:
                    f.write(resp.content)
                    
            logger.info("Kokoro models downloaded successfully!")
            from kokoro_onnx import Kokoro
            self.kokoro = Kokoro(self.model_path, self.voices_path)
            
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Yields raw PCM chunks (24kHz) for the given text."""
        try:
            await self._ensure_models()
            
            logger.debug(f"Synthesizing TTS locally: {text[:30]}...")
            
            loop = asyncio.get_running_loop()
            samples, sample_rate = await loop.run_in_executor(
                None, 
                lambda: self.kokoro.create(text, voice="af_bella", speed=1.0, lang="en-us")
            )
            
            # kokoro-onnx returns a float array in [-1.0, 1.0]. Convert to 16-bit PCM bytes
            audio_int16 = (samples * 32767).astype(np.int16)
            pcm_bytes = audio_int16.tobytes()
            
            # Yield in 2400-byte chunks
            chunk_size = 2400
            for i in range(0, len(pcm_bytes), chunk_size):
                yield pcm_bytes[i:i+chunk_size]
                # Small sleep to yield control to the event loop
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Local Kokoro TTS synthesis failed: {e}")
            yield b'\x00' * 2400
            await asyncio.sleep(0.05)
