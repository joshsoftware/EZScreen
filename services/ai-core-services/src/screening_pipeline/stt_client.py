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
        self.speech_buffer = bytearray() # Accumulates the full audio for the API
        self.is_speaking = False
        self.silence_frames = 0
        self.MAX_SILENCE_FRAMES = 50  # ~1.5 seconds of silence before chunking (assuming 30ms frames)
        self.is_connected = True
        
        self.process_task = None
        
    async def connect(self):
        """Initialize HTTP client for Whisper."""
        logger.info("Initializing Whisper Cloud STT Client")
        self.is_connected = True

    def _downsample_to_16k(self, pcm_bytes: bytes, orig_rate: int) -> bytes:
        """
        WebRTC VAD supports 16kHz. We convert 48kHz or 24kHz down to 16kHz.
        If it's already 16kHz, return as is.
        """
        if orig_rate == 16000:
            return pcm_bytes
            
        samples = struct.unpack(f"<{len(pcm_bytes)//2}h", pcm_bytes)
        
        if orig_rate == 48000:
            # 48k to 16k: keep 1 every 3
            downsampled = [samples[i] for i in range(0, len(samples), 3)]
        elif orig_rate == 24000:
            # 24k to 16k: drop 1 every 3
            downsampled = [samples[i] for i in range(len(samples)) if i % 3 != 2]
        else:
            # Fallback (unsupported rate, just return it and hope)
            return pcm_bytes
            
        return struct.pack(f"<{len(downsampled)}h", *downsampled)

    async def send_audio(self, pcm_bytes: bytes, sample_rate: int = 24000):
        """Receive raw PCM audio from websocket at the given sample rate."""
        if not self.is_connected:
            return
            
        if not hasattr(self, '_logged_rate'):
            logger.info(f"STT receiving audio at sample rate: {sample_rate}")
            self._logged_rate = True
            
        # We need 30ms chunks for VAD. 
        try:
            chunk_size = int(int(sample_rate) * 2 * 0.03)
        except Exception:
            chunk_size = 1440 # fallback to 24kHz
        
        # Buffer incoming bytes
        self.audio_buffer.extend(pcm_bytes)
        self.speech_buffer.extend(pcm_bytes)
        
        while len(self.audio_buffer) >= chunk_size:
            frame = self.audio_buffer[:chunk_size]
            self.audio_buffer = self.audio_buffer[chunk_size:]
            
            # VAD check requires 16kHz
            frame_16k = self._downsample_to_16k(frame, int(sample_rate))
            
            try:
                is_speech = self.vad.is_speech(frame_16k, 16000)
            except Exception as e:
                logger.error(f"VAD error: {e}. frame len: {len(frame_16k)}")
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
        audio_chunk = bytes(self.speech_buffer)
        self.speech_buffer = bytearray()
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
                    'model': 'whisper-large-v3', # Groq's active model name
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
