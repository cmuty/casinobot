"""
Скрипт инициализации базы данных
Запуск: python scripts/init_db.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, engine
from src.models import User, Wallet, Transaction, Bet, UserAchievement
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Инициализация БД"""
    try:
        logger.info("🔧 Инициализация базы данных...")
        
        # Создаём таблицы
        await init_db()
        
        logger.info("✅ База данных успешно инициализирована!")
        logger.info("📋 Созданные таблицы:")
        logger.info("  - users")
        logger.info("  - wallets")
        logger.info("  - transactions")
        logger.info("  - bets")
        logger.info("  - user_achievements")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())