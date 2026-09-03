from backend.database import async_session_factory
from sqlalchemy import text


async def test_db_connection():
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
