from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from src.models import User
from src.services.wallet_service import wallet_service
from src.services.bet_service import bet_service
# НОВОЕ:
from src.services.personality_engine import PersonalityEngine
# Импортируем клавиатуры
from src.utils.keyboards import get_main_menu_keyboard
from src.utils.ban_check import check_if_banned
from src.config import settings

def create_profile_keyboard(user, is_admin: bool = False) -> InlineKeyboardBuilder:
    """Создает клавиатуру для профиля"""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопку админ-панели для админов
    if is_admin:
        builder.button(text="🔐 Админ-панель", callback_data="admin:panel")
    
    # Добавляем кнопки для VIP пользователей
    if user.is_vip:
        builder.button(text="🏆 Лидерборды", callback_data="leaderboard:menu")
        builder.button(text="💳 Кредиты", callback_data="credits:menu")
        builder.button(text="⭐ VIP бонусы", callback_data="vip:bonuses")
    
    # Добавляем кнопку лидербордов для всех пользователей
    if not user.is_vip:
        builder.button(text="🏆 Лидерборды", callback_data="leaderboard:menu")
    
    return builder


router = Router()

@router.message(Command('profile'))
async def cmd_profile(message: Message):
    """Профиль игрока"""
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

        # Получаем данные
        balance = await wallet_service.get_balance(user.id)
        stats = await bet_service.get_user_stats(user.id)

        # Определяем уровень
        total_wagered = stats['total_wagered_cents']
        if total_wagered >= 10000000:
            level = "👑 Крупье"
        elif total_wagered >= 2000000:
            level = "💎 Хайроллер"
        elif total_wagered >= 500000:
            level = "🥇 Дэпнул сарай"
        elif total_wagered >= 100000:
            level = "🥈 Взял ипотеку"
        else:
            level = "🥉 Бомж"

        # Определяем статус
        if telegram_id == settings.ADMIN_ID:
            status = "🔐 Администратор"
        elif user.is_vip:
            status = "⭐ VIP"
        else:
            status = "👤 Пользователь"

        text = (
            f"👤 <b>Профиль игрока</b>\n\n"
            f"🆔 {user.first_name or 'Игрок'}\n"
            f"💰 Баланс: <b>${balance / 100:.2f}</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"├ Всего ставок: {stats['total_bets']}\n"
            f"├ Всего поставлено: ${stats['total_wagered_cents'] / 100:.2f}\n"
            f"├ Всего выиграно: ${stats['total_won_cents'] / 100:.2f}\n"
            f"├ Винрейт: {stats['winrate']:.1f}%\n"
            f"└ Уровень: {level}\n\n"
            f"🎖️ <b>Статус:</b> {status}"
        )
        
        # Создаем клавиатуру с кнопками
        builder = create_profile_keyboard(user, message.from_user.id == settings.ADMIN_ID)
        
        # Если есть кнопки, отправляем с клавиатурой
        if builder.buttons:
            builder.adjust(2)  # По 2 кнопки в ряд
            await message.answer(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text)
        # --- ОТПРАВКА МЕНЮ ---
        # Проверяем тип чата перед отправкой меню
        # if message.chat.type in ['group', 'supergroup']:
        #     # В группе меню НЕ отправляем
        #     pass
        # else:
        #     # В ЛС меню отправляем
        #     await message.answer("Меню:", reply_markup=get_main_menu_keyboard())
        # УБРАНО: не отправляем меню после /profile

# ТЕКСТОВЫЙ ТРИГГЕР для профиля - игнорируется в группах
@router.message(lambda message: message.text == '👤 Профиль')
async def trigger_profile(message: Message):
    """Обрабатывает текстовый триггер '👤 Профиль'"""
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

        # Получаем данные
        balance = await wallet_service.get_balance(user.id)
        stats = await bet_service.get_user_stats(user.id)

        # Определяем уровень
        total_wagered = stats['total_wagered_cents']
        if total_wagered >= 10000000:
            level = "👑 Крупье"
        elif total_wagered >= 2000000:
            level = "💎 Хайроллер"
        elif total_wagered >= 500000:
            level = "🥇 Дэпнул сарай"
        elif total_wagered >= 100000:
            level = "🥈 Взял ипотеку"
        else:
            level = "🥉 Бомж"

        # Определяем статус
        if telegram_id == settings.ADMIN_ID:
            status = "🔐 Администратор"
        elif user.is_vip:
            status = "⭐ VIP"
        else:
            status = "👤 Пользователь"

        text = (
            f"👤 <b>Профиль игрока</b>\n\n"
            f"🆔 {user.first_name or 'Игрок'}\n"
            f"💰 Баланс: <b>${balance / 100:.2f}</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"├ Всего ставок: {stats['total_bets']}\n"
            f"├ Всего поставлено: ${stats['total_wagered_cents'] / 100:.2f}\n"
            f"├ Всего выиграно: ${stats['total_won_cents'] / 100:.2f}\n"
            f"├ Винрейт: {stats['winrate']:.1f}%\n"
            f"└ Уровень: {level}\n\n"
            f"🎖️ <b>Статус:</b> {status}"
        )
        
        # Создаем клавиатуру с кнопками
        builder = create_profile_keyboard(user, message.from_user.id == settings.ADMIN_ID)
        
        # Если есть кнопки, отправляем с клавиатурой
        if builder.buttons:
            builder.adjust(2)  # По 2 кнопки в ряд
            await message.answer(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text)

# СОКРАЩЕННЫЕ КОМАНДЫ для профиля - только в ЛС
@router.message(lambda message: message.text and message.text.lower() in ['профиль'])
async def shortcut_profile(message: Message):
    """Обрабатывает сокращенную команду 'профиль'"""
    # Только для личных сообщений
    if message.chat.type in ['group', 'supergroup']:
        return
    await cmd_profile(message)

# РУССКАЯ КОМАНДА /профиль
@router.message(Command('профиль'))
async def cmd_profile_ru(message: Message):
    """Обрабатывает русскую команду /профиль"""
    await cmd_profile(message)

# АЛИАС ДЛЯ ПРОФИЛЯ БЕЗ СЛЭША
@router.message(lambda message: message.text and message.text.lower() == 'профиль')
async def profile_alias(message: Message):
    """Обрабатывает алиас 'профиль' без слэша"""
    await cmd_profile(message)

@router.message(Command('balance'))
async def cmd_balance(message: Message):
    """Просмотр баланса"""
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

        balance = await wallet_service.get_balance(user.id)
        # НОВОЕ: Используем персональность
        # Это не совсем событие, но можно сделать приветствие при запросе баланса
        text = f"💰 Твой баланс: <b>${balance / 100:.2f}</b>"
        # Если хочешь использовать персональность, можно вызвать что-то вроде:
        # context = {'balance': balance}
        # text = await PersonalityEngine.get_message('balance_check', user, context)
        # if 'balance_check' not in [...]:
        #     text = f"💰 Твой баланс: <b>${balance / 100:.2f}</b>"

        await message.answer(text)

# ТЕКСТОВЫЙ ТРИГГЕР для баланса - игнорируется в группах
@router.message(lambda message: message.text == '💰 Баланс')
async def trigger_balance(message: Message):
    """Обрабатывает текстовый триггер '💰 Баланс'"""
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

        balance = await wallet_service.get_balance(user.id)
        # НОВОЕ: Используем персональность
        # Это не совсем событие, но можно сделать приветствие при запросе баланса
        text = f"💰 Твой баланс: <b>${balance / 100:.2f}</b>"
        # Если хочешь использовать персональность, можно вызвать что-то вроде:
        # context = {'balance': balance}
        # text = await PersonalityEngine.get_message('balance_check', user, context)
        # if 'balance_check' not in [...]:
        #     text = f"💰 Твой баланс: <b>${balance / 100:.2f}</b>"

        await message.answer(text)

# СОКРАЩЕННЫЕ КОМАНДЫ для баланса - только в ЛС
@router.message(lambda message: message.text and message.text.lower() in ['б', 'баланс'])
async def shortcut_balance(message: Message):
    """Обрабатывает сокращенные команды 'б' и 'баланс'"""
    # Только для личных сообщений
    if message.chat.type in ['group', 'supergroup']:
        return
    await cmd_balance(message)

# РУССКАЯ КОМАНДА /баланс
@router.message(Command('баланс'))
async def cmd_balance_ru(message: Message):
    """Обрабатывает русскую команду /баланс"""
    await cmd_balance(message)
