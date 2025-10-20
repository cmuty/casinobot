from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
from src.models import User
from src.services.wallet_service import wallet_service
# НОВОЕ:
from src.services.personality_engine import PersonalityEngine
# Импортируем клавиатуры
from src.utils.keyboards import get_main_menu_keyboard
from src.utils.ban_check import check_if_banned

router = Router()

@router.message(Command('bonus'))
async def cmd_bonus(message: Message):
    """Ежедневный бонус"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    from src.database import async_session_maker
    telegram_id = message.from_user.id

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

        now = datetime.utcnow()
        last_bonus = user.last_bonus_claimed_at

        # Проверка кулдауна
        if last_bonus and (now - last_bonus).total_seconds() < 86400:
            next_bonus = last_bonus + timedelta(hours=24)
            remaining = next_bonus - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            # НОВОЕ: Используем персональность (например, cooldown)
            # Пока используем стандартное сообщение
            await message.answer(
                f"⏰ Ежедневный бонус уже получен!\n"
                f"Следующий бонус через: <b>{hours}ч {minutes}м</b>"
            )
            return

        # Streak bonus
        if last_bonus and (now - last_bonus).days == 1:
            user.bonus_streak += 1
        elif not last_bonus or (now - last_bonus).days > 1:
            user.bonus_streak = 1

        streak_multiplier = 1 + min(user.bonus_streak - 1, 6) * 0.1

        # Генерация суммы
        base_amount = secrets.randbelow(9000) + 1000  # $10-$100
        bonus_amount = int(base_amount * streak_multiplier)

        # Начисление
        await wallet_service.credit(user.id, bonus_amount, 'daily_bonus')
        user.last_bonus_claimed_at = now
        await session.commit()

        balance = await wallet_service.get_balance(user.id)

        streak_info = ""
        if user.bonus_streak > 1:
            streak_info = f"\n🔥 Продолжай заходить каждый день!\nТекущий множитель: +{int((streak_multiplier - 1) * 100)}%"

        # НОВОЕ: Используем персональность
        text = await PersonalityEngine.get_message('daily_bonus', user)
        # Добавляем детали к сообщению персональности
        text += f"\n💰 +${bonus_amount / 100:.2f}\n"
        text += f"🔥 Серия: {user.bonus_streak} {'день' if user.bonus_streak == 1 else 'дней'} подряд"
        text += f"{streak_info}\n"
        text += f"💵 Баланс: <b>${balance / 100:.2f}</b>"

        await message.answer(text)

# ТЕКСТОВЫЙ ТРИГГЕР для бонуса - игнорируется в группах
@router.message(lambda message: message.text == '🎁 Бонус')
async def trigger_bonus(message: Message):
    """Обрабатывает текстовый триггер '🎁 Бонус'"""
    # Проверяем тип чата: если группа — игнорируем (ничего не отвечаем)
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
        return
    
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    # Если ЛС - выполняем ту же логику, что и для команды
    from src.database import async_session_maker
    telegram_id = message.from_user.id

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

        now = datetime.utcnow()
        last_bonus = user.last_bonus_claimed_at

        # Проверка кулдауна
        if last_bonus and (now - last_bonus).total_seconds() < 86400:
            next_bonus = last_bonus + timedelta(hours=24)
            remaining = next_bonus - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            # НОВОЕ: Используем персональность (например, cooldown)
            # Пока используем стандартное сообщение
            await message.answer(
                f"⏰ Ежедневный бонус уже получен!\n"
                f"Следующий бонус через: <b>{hours}ч {minutes}м</b>"
            )
            return

        # Streak bonus
        if last_bonus and (now - last_bonus).days == 1:
            user.bonus_streak += 1
        elif not last_bonus or (now - last_bonus).days > 1:
            user.bonus_streak = 1

        streak_multiplier = 1 + min(user.bonus_streak - 1, 6) * 0.1

        # Генерация суммы
        base_amount = secrets.randbelow(9000) + 1000  # $10-$100
        bonus_amount = int(base_amount * streak_multiplier)

        # Начисление
        await wallet_service.credit(user.id, bonus_amount, 'daily_bonus')
        user.last_bonus_claimed_at = now
        await session.commit()

        balance = await wallet_service.get_balance(user.id)

        streak_info = ""
        if user.bonus_streak > 1:
            streak_info = f"\n🔥 Продолжай заходить каждый день!\nТекущий множитель: +{int((streak_multiplier - 1) * 100)}%"

        # НОВОЕ: Используем персональность
        text = await PersonalityEngine.get_message('daily_bonus', user)
        # Добавляем детали к сообщению персональности
        text += f"\n💰 +${bonus_amount / 100:.2f}\n"
        text += f"🔥 Серия: {user.bonus_streak} {'день' if user.bonus_streak == 1 else 'дней'} подряд"
        text += f"{streak_info}\n"
        text += f"💵 Баланс: <b>${balance / 100:.2f}</b>"

        await message.answer(text)
