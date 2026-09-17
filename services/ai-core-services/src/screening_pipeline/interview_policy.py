"""Shared interface between interview business policy and realtime runtimes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class InterviewPolicy(Protocol):
    """Operations a realtime runtime may invoke on interview policy."""

    async def start(self) -> None:
        """Load the session and begin the greeting flow."""

    def handle_candidate_speech(self, transcript: str) -> None:
        """Submit one completed candidate utterance for processing."""

    def handle_candidate_activity(self) -> None:
        """Notify policy that candidate speech activity has started."""

    async def speak(self, text: str) -> None:
        """Deliver policy-generated speech through the active runtime."""

    async def cleanup(self) -> None:
        """Finalize the interview and release runtime resources."""