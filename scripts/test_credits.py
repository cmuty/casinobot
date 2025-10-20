#!/usr/bin/env python3
"""
Тест системы кредитов
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_db, close_db
from src.services.rating_service import CreditService

async def test_credits():
    """Тестирование системы кредитов"""
    try:
        print("🔧 Инициализация базы данных...")
        await init_db()
        
        print("💳 Тестирование системы кредитов...")
        
        # Тест получения доступных кредитов
        print("📊 Получение доступных кредитов...")
        available_credits = await CreditService.get_available_credits(1)  # user_id = 1
        print(f"✅ Доступные кредиты: {len(available_credits)}")
        
        for credit in available_credits:
            print(f"   - {credit['limit_type']}: ${credit['amount']/100:.0f}")
        
        # Тест взятия кредита
        print("💰 Тестирование взятия кредита...")
        success = await CreditService.take_credit(1, 100000, 'daily_1k')  # $1000
        print(f"✅ Кредит взят: {success}")
        
        # Тест получения кредитов пользователя
        print("📋 Получение кредитов пользователя...")
        user_credits = await CreditService.get_user_credits(1)
        print(f"✅ Кредиты пользователя: {len(user_credits)}")
        
        for credit in user_credits:
            print(f"   - ${credit['amount']/100:.0f} к возврату: ${credit['amount_to_repay']/100:.0f}")
        
        print("🎉 Все тесты прошли успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(test_credits())
