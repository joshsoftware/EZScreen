from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.orchestrator import InterviewOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_start_aborts_without_session():
    ws = MagicMock()
    orch = InterviewOrchestrator(
        "missing-session",
        ws,
        stt_client=MagicMock(),
        tts_client=MagicMock(),
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=MagicMock(),
    )

    with patch(
        "src.screening_pipeline.orchestrator.interview_session_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        await orch.start()

    assert orch.is_active is False
