from typing import Optional, List
from pydantic import BaseModel, Field


class LLMGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Prompt text to generate completion for")
    system: Optional[str] = Field(default=None, description="Optional system prompt instructions")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0, description="Generation temperature (0.0 to 1.0)")
    stream: bool = Field(default=False, description="Stream output tokens")
    timeout: float = Field(default=90.0, gt=0.0, description="Request timeout in seconds")


class LLMGenerateResponse(BaseModel):
    response: str = Field(..., description="The generated text response content")
    model: str = Field(..., description="The model used for generation")
    done: bool = Field(default=True, description="Whether generation is complete")
    total_duration: Optional[int] = Field(default=None, description="Total generation time in nanoseconds")
    prompt_eval_count: Optional[int] = Field(default=None, description="Number of tokens in prompt evaluation")
    eval_count: Optional[int] = Field(default=None, description="Number of tokens generated")


class LLMChatMessage(BaseModel):
    role: str = Field(..., description="Role of the speaker: assistant, user, or system")
    content: str = Field(..., description="Message text content")


class LLMChatRequest(BaseModel):
    messages: List[LLMChatMessage] = Field(..., description="List of conversation messages")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0, description="Chat temperature (0.0 to 1.0)")
    timeout: float = Field(default=90.0, gt=0.0, description="Request timeout in seconds")


class LLMChatResponse(BaseModel):
    model: str = Field(..., description="The model used for chat")
    message: LLMChatMessage = Field(..., description="The assistant's response message object")
    done: bool = Field(default=True, description="Whether chat completion is complete")
    total_duration: Optional[int] = Field(default=None, description="Total chat duration in nanoseconds")
    prompt_eval_count: Optional[int] = Field(default=None, description="Number of tokens in prompt evaluation")
    eval_count: Optional[int] = Field(default=None, description="Number of tokens generated")
