from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AttendeeAudioSettings(BaseModel):
    url: str
    sample_rate: int = 24000


class AttendeeWebsocketSettings(BaseModel):
    audio: AttendeeAudioSettings


class AttendeeScheduleBotRequest(BaseModel):
    meeting_url: str
    bot_name: str = "ezscreener"
    join_at: Optional[str] = None
    transcription_settings: Dict[str, Any] = Field(default_factory=dict)
    websocket_settings: Optional[AttendeeWebsocketSettings] = None


class AttendeeScheduleBotResponse(BaseModel):
    id: str
    status: str = "scheduled"
    meeting_url: str
    bot_name: Optional[str] = "ezscreener"


class AttendeeBotStatusResponse(BaseModel):
    id: str
    status: str
    meeting_url: str
    duration_seconds: Optional[int] = 0


class DispatchBotRequest(BaseModel):
    interview_session_id: str
    meeting_url: Optional[str] = None


class InterviewSessionDetailResponse(BaseModel):
    id: str
    application_id: str
    scheduled_by: Optional[str] = None
    interview_type: str = "screening_ai"
    status: str
    scheduled_at: Optional[str] = None
    generated_questions: Optional[List[Dict[str, Any]]] = None
    interview_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DispatchBotResponse(BaseModel):
    bot_id: str
    interview_session_id: str
    status: str = "scheduled"
    meeting_url: str
    scheduled_at: Optional[str] = None
    dispatched_at: str


class BotStatusResponse(BaseModel):
    bot_id: str
    status: str
    meeting_url: str
    duration_seconds: Optional[int] = None
