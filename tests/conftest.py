"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN_NOT_REAL")
os.environ.setdefault("OWNER_ID", "1000")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session", autouse=True)
def _configure() -> None:
    from app.config import load_settings

    load_settings(dotenv=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine(tmp_path: Path):
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db.base import dispose_engine, engine as global_engine
    from app.db.models import Base

    url = f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}"
    test_engine = create_async_engine(url)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # point the module level engine helpers at the test engine
    import app.db.base as base_module

    previous = base_module.engine, base_module.SessionLocal
    base_module.engine = test_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    base_module.SessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    yield test_engine
    await test_engine.dispose()
    base_module.engine, base_module.SessionLocal = previous


@pytest.fixture
async def session(db_engine):
    from sqlalchemy.ext.asyncio import AsyncSession

    import app.db.base as base_module

    async with base_module.SessionLocal() as session:  # type: ignore[misc]
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def _database(db_engine):  # every test gets its own temporary sqlite file
    from app.core import cache, ratelimit

    cache.clear_all()      # caches are process wide: never leak state between tests
    ratelimit.reset_all()  # ... and so are the sliding windows
    return db_engine


@pytest.fixture(scope="session")
def dispatcher():
    """The real dispatcher is built once: routers are module level singletons."""
    from app.main import build_dispatcher

    return build_dispatcher()
