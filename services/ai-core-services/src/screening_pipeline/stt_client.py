import asyncio
import io
import wave
import httpx
import webrtcvad
import struct
from typing import Callable
from src.core.logger import logger

class WhisperCloudSTTClient:
    """
    Accumulates 24kHz PCM audio from the WebSocket, uses WebRTC VAD to detect
    when the candidate stops speaking, and uploads the chunk to Whisper API.
    """
    
    def __init__(self, api_url: str, api_key: str, on_transcript: Callable[[str], None]):
        self.api_url = api_url or "https://api.groq.com/openai/v1/audio/transcriptions"
        self.api_key = api_key
        self.on_transcript = on_transcript
        
        self.vad = webrtcvad.Vad(3) # Aggressiveness 3 (highest)
        self.audio_buffer = bytearray()
        self.is_speaking = False
        self.silence_frames = 0
        self.MAX_SILENCE_FRAMES = 50  # ~1.5 seconds of silence before chunking (assuming 30ms frames)
        self.is_connected = True
        
        self.process_task = None
        
    async def connect(self):
        """Initialize HTTP client for Whisper."""
        logger.info("Initializing Whisper Cloud STT Client")
        self.is_connected = True

    def _downsample_24k_to_16k(self, pcm_bytes: bytes) -> bytes:
        """
        WebRTC VAD only supports 8kHz, 16kHz, 32kHz, 48kHz.
        We drop every 3rd sample to convert 24kHz to 16kHz.
        """
        samples = struct.unpack(f"<{len(pcm_bytes)//2}h", pcm_bytes)
        downsampled = [samples[i] for i in range(len(samples)) if i % 3 != 2]
        return struct.pack(f"<{len(downsampled)}h", *downsampled)

    async def send_audio(self, pcm_bytes: bytes):
        """Receive raw 24kHz PCM audio from websocket."""
        if not self.is_connected:
            return
            
        # We process in 30ms chunks. 24000Hz * 16-bit (2 bytes) * 0.03 = 1440 bytes
        chunk_size = 1440
        
        # Buffer incoming bytes
        self.audio_buffer.extend(pcm_bytes)
        
        while len(self.audio_buffer) >= chunk_size:
            frame = self.audio_buffer[:chunk_size]
            self.audio_buffer = self.audio_buffer[chunk_size:]
            
            # VAD check requires 16kHz (30ms = 960 bytes)
            frame_16k = self._downsample_24k_to_16k(frame)
            
            try:
                is_speech = self.vad.is_speech(frame_16k, 16000)
            except Exception as e:
                is_speech = False
                
            if is_speech:
                self.is_speaking = True
                self.silence_frames = 0
            elif self.is_speaking:
                self.silence_frames += 1
                
            # If they stopped speaking for MAX_SILENCE_FRAMES, process the chunk!
            if self.is_speaking and self.silence_frames > self.MAX_SILENCE_FRAMES:
                asyncio.create_task(self._process_chunk_and_reset())

    async def _process_chunk_and_reset(self):
        """Takes the current buffer, creates a WAV, and sends to Whisper."""
        self.is_speaking = False
        self.silence_frames = 0
        
        # Deep copy buffer to clear it for the next sentence
        audio_chunk = bytes(self.audio_buffer)
        self.audio_buffer = bytearray()
        
        if len(audio_chunk) < 24000:  # Ignore clips less than 0.5s
            return
            
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(audio_chunk)
            
        wav_bytes = wav_io.getvalue()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                files = {
                    'file': ('audio.wav', wav_bytes, 'audio/wav')
                }
                data = {
                    'model': 'distil-whisper-large-v3-en', # Groq's model name, update if using another provider
                    'response_format': 'json'
                }
                headers = {
                    'Authorization': f'Bearer {self.api_key}'
                }
                
                logger.debug("Sending audio chunk to Whisper API...")
                resp = await client.post(self.api_url, files=files, data=data, headers=headers)
                
                if resp.status_code == 200:
                    transcript = resp.json().get('text', '').strip()
                    if transcript:
                        logger.debug(f"Whisper Transcript: {transcript}")
                        self.on_transcript(transcript)
                else:
                    logger.error(f"Whisper API error: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to transcribe chunk: {e}")

    async def close(self):
        """Gracefully close STT connection."""
        self.is_connected = False
        logger.info("Closed Whisper STT client")
