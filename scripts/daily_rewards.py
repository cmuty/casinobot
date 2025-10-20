#!/usr/bin/env python3
"""
Скрипт для ежедневного расчета наград за лидерборд
"""

import asyncio
import logging
from src.database import init_db, close_db
from src.services.rating_service import RatingService, CreditService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def daily_rewards_calculation():
    """Вычисляет ежедневные награды за лидерборд"""
    try:
        await init_db()
        logger.info("🏆 Начинаем расчет ежедневных наград...")
        
        # Вычисляем награды за дневной лидерборд
        await RatingService.calculate_daily_rewards()
        logger.info("✅ Ежедневные награды рассчитаны")
        
        # Проверяем просроченные кредиты
        await CreditService.check_overdue_credits()
        logger.info("✅ Просроченные кредиты проверены")
        
        logger.info("🎉 Ежедневные задачи выполнены!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета наград: {e}")
    finally:
        await close_db()


if __name__ == '__main__':
    asyncio.run(daily_rewards_calculation())
