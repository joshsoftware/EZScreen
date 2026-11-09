from typing import Optional
from sqlalchemy import select, text
from src.core.logger import logger
from src.db.connection import AsyncSessionLocal
from src.db.models import DBInterviewAnalysis, DBInterviewSession
from src.meeting_bot.schemas import InterviewSessionDetailResponse


class InterviewSessionRepository:
    """Read-only repository for querying interview_session records from PostgreSQL."""

    async def _scalar_one_or_none(self, query):
        """Run a query against either an async or sync session (see db.connection)."""
        session = AsyncSessionLocal()
        if hasattr(session, "__aenter__"):
            async with session:
                result = await session.execute(query)
                return result.scalar_one_or_none()
        with session:
            result = session.execute(query)
            return result.scalar_one_or_none()

    async def get_by_id(self, session_id: str) -> Optional[InterviewSessionDetailResponse]:
        """Fetch complete interview_session details by session_id."""
        try:
            db_obj = await self._scalar_one_or_none(
                select(DBInterviewSession).where(DBInterviewSession.id == session_id)
            )
            if not db_obj:
                return None

            return db_obj.to_response()
        except Exception as err:
            logger.warning(
                "Repository failed to fetch interview session record",
                extra={"session_id": session_id, "error": str(err)}
            )
            return None

    async def get_saved_evaluations(self, session_id: str) -> list[dict]:
        """Per-question evaluations core-api has stored for this session.

        Empty when there are none or the read fails: the caller then starts
        the interview from the beginning, as before.
        """
        try:
            analysis_result = await self._scalar_one_or_none(
                select(DBInterviewAnalysis.analysis_result).where(
                    DBInterviewAnalysis.interview_session_id == session_id
                )
            )
        except Exception as err:
            logger.warning(
                "Repository failed to fetch saved evaluations",
                extra={"session_id": session_id, "error": str(err)},
            )
            return []
        evaluations = (
            analysis_result.get("evaluations") if isinstance(analysis_result, dict) else None
        )
        if not isinstance(evaluations, list):
            return []
        return [item for item in evaluations if isinstance(item, dict)]

    async def get_by_bot_id(self, bot_id: str) -> Optional[InterviewSessionDetailResponse]:
        """Fetch session by bot_id inside interview_metadata."""
        try:
            db_obj = await self._scalar_one_or_none(
                select(DBInterviewSession).where(
                    DBInterviewSession.interview_metadata['bot_id'].astext == bot_id
                )
            )
            if not db_obj:
                return None
            return db_obj.to_response()
        except Exception as err:
            logger.error("Repository failed to fetch session by bot_id", extra={"bot_id": bot_id, "error": str(err)})
            return None


    async def get_candidate_name(self, application_id: str) -> tuple[str | None, str | None]:
        """The candidate's (first_name, last_name) for an application.

        (None, None) when it can't be read: the bot then cannot recognise the
        candidate by name and relies on its speech fallback.
        """
        query = text(
            "SELECT u.first_name, u.last_name FROM applications a "
            "JOIN users u ON u.id = a.candidate_id WHERE a.id = :application_id"
        )
        params = {"application_id": str(application_id)}
        try:
            session = AsyncSessionLocal()
            if hasattr(session, "__aenter__"):
                async with session:
                    row = (await session.execute(query, params)).first()
            else:
                with session:
                    row = session.execute(query, params).first()
        except Exception as err:
            logger.warning(
                "Repository failed to fetch the candidate's name",
                extra={"application_id": str(application_id), "error": str(err)},
            )
            return None, None
        if not row:
            return None, None
        return row[0], row[1]


interview_session_repo = InterviewSessionRepository()
