#!/usr/bin/env python3
"""
Скрипт для создания новых таблиц рейтингов и кредитов
"""

import asyncio
import logging
from src.database import init_db, close_db, async_session_maker
from src.models.rating import UserRating, LeaderboardReward, UserCredit, CreditLimit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_rating_tables():
    """Создает таблицы для рейтингов и кредитов"""
    try:
        await init_db()
        logger.info("✅ Новые таблицы созданы успешно")
        
        # Проверяем, что таблицы созданы
        async with async_session_maker() as session:
            # Проверяем таблицу рейтингов
            result = await session.execute("SHOW TABLES LIKE 'user_ratings'")
            if result.fetchone():
                logger.info("✅ Таблица user_ratings создана")
            
            # Проверяем таблицу наград
            result = await session.execute("SHOW TABLES LIKE 'leaderboard_rewards'")
            if result.fetchone():
                logger.info("✅ Таблица leaderboard_rewards создана")
            
            # Проверяем таблицу кредитов
            result = await session.execute("SHOW TABLES LIKE 'user_credits'")
            if result.fetchone():
                logger.info("✅ Таблица user_credits создана")
            
            # Проверяем таблицу лимитов кредитов
            result = await session.execute("SHOW TABLES LIKE 'credit_limits'")
            if result.fetchone():
                logger.info("✅ Таблица credit_limits создана")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")
    finally:
        await close_db()


if __name__ == '__main__':
    asyncio.run(create_rating_tables())
