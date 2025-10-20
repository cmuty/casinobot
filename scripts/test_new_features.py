#!/usr/bin/env python3
"""
Тестовый скрипт для проверки новых функций
"""

import asyncio
import logging
from src.database import init_db, close_db, async_session_maker
from src.models import User
from src.services.rating_service import RatingService, CreditService, VIPService
from src.services.wallet_service import wallet_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_new_features():
    """Тестирует новые функции"""
    try:
        await init_db()
        logger.info("🧪 Начинаем тестирование новых функций...")
        
        # Создаем тестового пользователя
        async with async_session_maker() as session:
            # Ищем первого пользователя
            result = await session.execute("SELECT * FROM users LIMIT 1")
            user_data = result.fetchone()
            
            if not user_data:
                logger.warning("❌ Нет пользователей для тестирования")
                return
            
            user_id = user_data[0]  # ID пользователя
            logger.info(f"👤 Тестируем с пользователем ID: {user_id}")
            
            # Тест 1: Обновление рейтинга
            logger.info("📊 Тест 1: Обновление рейтинга...")
            await RatingService.update_user_rating(user_id, 1000, 2000, 'daily')
            logger.info("✅ Рейтинг обновлен")
            
            # Тест 2: Получение лидерборда
            logger.info("🏆 Тест 2: Получение лидерборда...")
            leaderboard = await RatingService.get_leaderboard('daily', 5)
            logger.info(f"✅ Лидерборд получен: {len(leaderboard)} игроков")
            
            # Тест 3: VIP бонус
            logger.info("💎 Тест 3: VIP бонус...")
            original_win = 1000
            vip_win = await VIPService.apply_vip_bonus(user_id, original_win)
            logger.info(f"✅ VIP бонус: {original_win} -> {vip_win}")
            
            # Тест 4: Проверка кредитов (если пользователь VIP)
            user_result = await session.execute("SELECT is_vip FROM users WHERE id = %s", (user_id,))
            is_vip = user_result.fetchone()[0] if user_result.fetchone() else False
            
            if is_vip:
                logger.info("💳 Тест 4: Проверка кредитов...")
                can_take, message = await CreditService.can_take_credit(user_id, 'daily_1k')
                logger.info(f"✅ Кредит доступен: {can_take}, сообщение: {message}")
            else:
                logger.info("💳 Тест 4: Пользователь не VIP, кредиты недоступны")
            
            logger.info("🎉 Все тесты пройдены успешно!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
    finally:
        await close_db()


if __name__ == '__main__':
    asyncio.run(test_new_features())
