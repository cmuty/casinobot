#!/usr/bin/env python3
"""
Скрипт для тестирования Redis подключения
"""

import asyncio
import logging
from src.redis_db import init_redis, close_redis, db
from src.models_redis import User, Wallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_redis_connection():
    """Тестирование подключения к Redis"""
    try:
        await init_redis()
        logger.info("✅ Redis подключение успешно установлено")
        
        # Тестируем создание пользователя
        test_user = User(
            telegram_id=123456789,
            username="test_user",
            first_name="Test",
            language_code="en"
        )
        
        await db.set_user(test_user.telegram_id, test_user.to_dict())
        logger.info("✅ Пользователь создан в Redis")
        
        # Тестируем получение пользователя
        retrieved_user = await db.get_user(test_user.telegram_id)
        if retrieved_user:
            logger.info(f"✅ Пользователь получен: {retrieved_user['username']}")
        else:
            logger.error("❌ Пользователь не найден")
        
        # Тестируем создание кошелька
        test_wallet = Wallet(
            user_id=test_user.telegram_id,
            balance_cents=10000
        )
        
        await db.set_wallet(test_wallet.user_id, test_wallet.to_dict())
        logger.info("✅ Кошелек создан в Redis")
        
        # Тестируем операции с балансом
        new_balance = await db.increment_balance(test_user.telegram_id, 5000)
        logger.info(f"✅ Баланс увеличен до: {new_balance}")
        
        # Тестируем получение баланса
        balance = await db.get_balance(test_user.telegram_id)
        logger.info(f"✅ Текущий баланс: {balance}")
        
        # Очищаем тестовые данные
        await db.delete_user(test_user.telegram_id)
        logger.info("✅ Тестовые данные очищены")
        
        logger.info("🎉 Все тесты Redis прошли успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования Redis: {e}")
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(test_redis_connection())
