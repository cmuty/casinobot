from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import logging

logger = logging.getLogger(__name__)

# Создаём переменные для engine и session_maker
# Они будут инициализированы в init_db()
engine = None
async_session_maker = None


class Base(DeclarativeBase):
    """Базовая модель"""
    pass


async def init_db():
    """Инициализация базы данных"""
    global engine, async_session_maker
    
    # Импортируем settings здесь, чтобы избежать циклического импорта
    from src.config import settings
    
    # Создаём engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
    
    # Создаём session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ Все таблицы созданы")


async def close_db():
    """Закрытие соединений с БД"""
    if engine:
        await engine.dispose()


async def get_session() -> AsyncSession:
    """Получить сессию БД"""
    if not async_session_maker:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with async_session_maker() as session:
        yield session