from typing import Optional
from sqlalchemy import select
from src.core.logger import logger
from src.db.connection import AsyncSessionLocal
from src.db.models import DBInterviewSession
from src.meeting_bot.schemas import InterviewSessionDetailResponse


class InterviewSessionRepository:
    """Read-only repository for querying interview_session records from PostgreSQL."""

    async def get_by_id(self, session_id: str) -> Optional[InterviewSessionDetailResponse]:
        """Fetch complete interview_session details by session_id."""
        try:
            db_obj = None
            session = AsyncSessionLocal()
            if hasattr(session, "__aenter__"):
                async with session:
                    query = select(DBInterviewSession).where(DBInterviewSession.id == session_id)
                    result = await session.execute(query)
                    db_obj = result.scalar_one_or_none()
            else:
                with session:
                    query = select(DBInterviewSession).where(DBInterviewSession.id == session_id)
                    result = session.execute(query)
                    db_obj = result.scalar_one_or_none()

            if not db_obj:
                return None

            return db_obj.to_response()
        except Exception as err:
            logger.warning(
                "Repository failed to fetch interview session record",
                extra={"session_id": session_id, "error": str(err)}
            )
            return None

    async def get_by_bot_id(self, bot_id: str) -> Optional[InterviewSessionDetailResponse]:
        """Fetch session by bot_id inside interview_metadata."""
        try:
            db_obj = None
            session = AsyncSessionLocal()
            async with session:
                query = select(DBInterviewSession).where(
                    DBInterviewSession.interview_metadata['bot_id'].astext == bot_id
                )
                result = await session.execute(query)
                db_obj = result.scalar_one_or_none()

            if not db_obj:
                return None
            return db_obj.to_response()
        except Exception as err:
            logger.error("Repository failed to fetch session by bot_id", extra={"bot_id": bot_id, "error": str(err)})
            return None


interview_session_repo = InterviewSessionRepository()
