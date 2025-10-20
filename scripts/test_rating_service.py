#!/usr/bin/env python3
"""
Скрипт для проверки работы рейтингов
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_db, close_db
from src.services.rating_service import RatingService

async def test_rating_service():
    """Тестирование сервиса рейтингов"""
    try:
        print("🔧 Инициализация базы данных...")
        await init_db()
        
        print("📊 Тестирование RatingService...")
        
        # Тест получения лидерборда
        print("📈 Получение дневного лидерборда...")
        leaderboard = await RatingService.get_leaderboard('daily', 10)
        print(f"✅ Лидерборд получен: {len(leaderboard)} записей")
        
        # Тест получения недельного лидерборда
        print("📈 Получение недельного лидерборда...")
        leaderboard = await RatingService.get_leaderboard('weekly', 10)
        print(f"✅ Лидерборд получен: {len(leaderboard)} записей")
        
        # Тест получения месячного лидерборда
        print("📈 Получение месячного лидерборда...")
        leaderboard = await RatingService.get_leaderboard('monthly', 10)
        print(f"✅ Лидерборд получен: {len(leaderboard)} записей")
        
        print("🎉 Все тесты прошли успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(test_rating_service())
