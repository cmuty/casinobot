from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete as sql_delete, func, and_
from datetime import datetime, timedelta

from src.models import User, Bet, Wallet
from src.config import settings
from src.states import AdminStates
from src.services.wallet_service import wallet_service
from src.utils.keyboards import (
    get_admin_panel_keyboard,
    get_admin_users_keyboard,
    get_admin_banned_keyboard,
    get_admin_back_keyboard
)

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == settings.ADMIN_ID


async def notify_user(bot: Bot, user_telegram_id: int, message_text: str):
    """Отправляет уведомление пользователю"""
    try:
        await bot.send_message(chat_id=user_telegram_id, text=message_text, parse_mode='HTML')
    except Exception as e:
        print(f"Не удалось отправить уведомление пользователю {user_telegram_id}: {e}")


# --- ГЛАВНАЯ КОМАНДА АДМИН-ПАНЕЛИ ---

@router.callback_query(F.data == "admin:panel")
async def show_admin_panel(callback: CallbackQuery):
    """Показывает главную админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к админ-панели", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_panel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:main")
async def back_to_admin_main(callback: CallbackQuery):
    """Возврат в главную админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_panel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:close")
async def close_admin_panel(callback: CallbackQuery):
    """Закрывает админ-панель"""
    await callback.message.delete()
    await callback.answer()


# --- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ---

@router.callback_query(F.data == "admin:users")
async def show_users_menu(callback: CallbackQuery):
    """Показывает меню управления пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_users_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:user_search")
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    """Начало поиска пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите Telegram ID пользователя:",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_search)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_search)
async def process_user_search(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID! Введите число.")
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_telegram_id}</code> не найден.",
                reply_markup=get_admin_users_keyboard()
            )
            await state.clear()
            return
        
        # Получаем баланс
        balance = await wallet_service.get_balance(user.id)
        
        # Получаем последние 10 ставок
        bets_result = await session.execute(
            select(Bet).where(Bet.user_id == user.id)
            .order_by(Bet.created_at.desc())
            .limit(10)
        )
        bets = bets_result.scalars().all()
        
        # Формируем сообщение
        text = f"👤 <b>Информация о пользователе</b>\n\n"
        text += f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        text += f"👤 Имя: {user.first_name or 'Не указано'}\n"
        if user.username:
            text += f"📝 Username: @{user.username}\n"
        text += f"💰 Баланс: <b>${balance / 100:.2f}</b>\n"
        text += f"⭐ VIP: {'Да' if user.is_vip else 'Нет'}\n"
        text += f"🚫 Заблокирован: {'Да' if user.is_banned else 'Нет'}\n"
        text += f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        if bets:
            text += "📊 <b>Последние 10 ставок:</b>\n"
            for i, bet in enumerate(bets, 1):
                result_emoji = "✅" if bet.payout_cents > 0 else "❌"
                profit = bet.payout_cents - bet.stake_cents
                text += f"{i}. {result_emoji} {bet.game_type.upper()} | "
                text += f"Ставка: ${bet.stake_cents / 100:.2f} | "
                text += f"{'Выигрыш' if profit > 0 else 'Проигрыш'}: ${abs(profit) / 100:.2f}\n"
        else:
            text += "📊 <b>Ставок пока нет</b>\n"
        
        await message.answer(text, reply_markup=get_admin_users_keyboard())
    
    await state.clear()


@router.callback_query(F.data == "admin:user_delete")
async def start_user_delete(callback: CallbackQuery, state: FSMContext):
    """Начало удаления пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🗑️ <b>Удаление пользователя</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это действие необратимо!\n\n"
        "Введите Telegram ID пользователя для удаления:",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_delete)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_delete)
async def process_user_delete(message: Message, state: FSMContext, bot: Bot):
    """Обработка удаления пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID! Введите число.")
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_telegram_id}</code> не найден.",
                reply_markup=get_admin_users_keyboard()
            )
            await state.clear()
            return
        
        # Уведомляем пользователя
        await notify_user(
            bot,
            user_telegram_id,
            "⚠️ <b>Ваш аккаунт был удален администратором</b>\n\n"
            "Если вы считаете это ошибкой, обратитесь в поддержку."
        )
        
        # Удаляем пользователя (каскадное удаление очистит связанные записи)
        await session.delete(user)
        await session.commit()
        
        await message.answer(
            f"✅ Пользователь <code>{user_telegram_id}</code> успешно удален из базы данных.",
            reply_markup=get_admin_users_keyboard()
        )
    
    await state.clear()


@router.callback_query(F.data == "admin:user_add_balance")
async def start_add_balance(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи валюты"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 <b>Выдать валюту</b>\n\n"
        "Введите Telegram ID пользователя:",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_add_balance)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_add_balance)
async def process_add_balance_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя для выдачи валюты"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID! Введите число.")
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_telegram_id}</code> не найден.",
                reply_markup=get_admin_users_keyboard()
            )
            await state.clear()
            return
        
        # Сохраняем ID пользователя в состоянии
        await state.update_data(user_id=user.id, user_telegram_id=user_telegram_id)
        await message.answer(
            f"💵 Введите сумму для начисления (в долларах):\n\n"
            f"Например: <code>100</code> (для $100.00)"
        )
        await state.set_state(AdminStates.waiting_amount_add_balance)


@router.message(AdminStates.waiting_amount_add_balance)
async def process_add_balance_amount(message: Message, state: FSMContext, bot: Bot):
    """Обработка суммы для выдачи валюты"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        amount_dollars = float(message.text.strip())
        amount_cents = int(amount_dollars * 100)
        
        if amount_cents <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число.")
        return
    
    data = await state.get_data()
    user_id = data.get('user_id')
    user_telegram_id = data.get('user_telegram_id')
    
    # Начисляем валюту
    await wallet_service.add_funds(user_id, amount_cents, "admin_add")
    new_balance = await wallet_service.get_balance(user_id)
    
    # Уведомляем пользователя
    await notify_user(
        bot,
        user_telegram_id,
        f"💰 <b>Начисление средств</b>\n\n"
        f"Администратор начислил вам <b>${amount_dollars:.2f}</b>\n"
        f"💵 Ваш новый баланс: <b>${new_balance / 100:.2f}</b>"
    )
    
    await message.answer(
        f"✅ Успешно начислено <b>${amount_dollars:.2f}</b> пользователю <code>{user_telegram_id}</code>\n"
        f"💵 Новый баланс: <b>${new_balance / 100:.2f}</b>",
        reply_markup=get_admin_users_keyboard()
    )
    
    await state.clear()


@router.callback_query(F.data == "admin:user_set_balance")
async def start_set_balance(callback: CallbackQuery, state: FSMContext):
    """Начало изменения валюты"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "✏️ <b>Изменить валюту</b>\n\n"
        "Введите Telegram ID пользователя:",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_set_balance)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_set_balance)
async def process_set_balance_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя для изменения валюты"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID! Введите число.")
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_telegram_id}</code> не найден.",
                reply_markup=get_admin_users_keyboard()
            )
            await state.clear()
            return
        
        current_balance = await wallet_service.get_balance(user.id)
        
        # Сохраняем данные в состоянии
        await state.update_data(
            user_id=user.id,
            user_telegram_id=user_telegram_id,
            old_balance=current_balance
        )
        await message.answer(
            f"💵 Текущий баланс: <b>${current_balance / 100:.2f}</b>\n\n"
            f"Введите новую сумму (в долларах):\n"
            f"Например: <code>500</code> (для $500.00)"
        )
        await state.set_state(AdminStates.waiting_amount_set_balance)


@router.message(AdminStates.waiting_amount_set_balance)
async def process_set_balance_amount(message: Message, state: FSMContext, bot: Bot):
    """Обработка новой суммы для изменения валюты"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        new_amount_dollars = float(message.text.strip())
        new_amount_cents = int(new_amount_dollars * 100)
        
        if new_amount_cents < 0:
            await message.answer("❌ Сумма не может быть отрицательной!")
            return
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число.")
        return
    
    data = await state.get_data()
    user_id = data.get('user_id')
    user_telegram_id = data.get('user_telegram_id')
    old_balance = data.get('old_balance')
    
    # Устанавливаем новый баланс
    await wallet_service.set_balance(user_id, new_amount_cents)
    
    # Уведомляем пользователя
    difference = new_amount_cents - old_balance
    if difference > 0:
        action_text = f"увеличил ваш баланс на <b>${abs(difference) / 100:.2f}</b>"
    elif difference < 0:
        action_text = f"уменьшил ваш баланс на <b>${abs(difference) / 100:.2f}</b>"
    else:
        action_text = "установил тот же баланс"
    
    await notify_user(
        bot,
        user_telegram_id,
        f"✏️ <b>Изменение баланса</b>\n\n"
        f"Администратор {action_text}\n"
        f"💵 Ваш новый баланс: <b>${new_amount_cents / 100:.2f}</b>"
    )
    
    await message.answer(
        f"✅ Баланс пользователя <code>{user_telegram_id}</code> изменен\n"
        f"Старый баланс: <b>${old_balance / 100:.2f}</b>\n"
        f"Новый баланс: <b>${new_amount_cents / 100:.2f}</b>",
        reply_markup=get_admin_users_keyboard()
    )
    
    await state.clear()


# --- БЛОКИРОВКИ ---

@router.callback_query(F.data == "admin:banned")
async def show_banned_menu(callback: CallbackQuery):
    """Показывает меню управления блокировками"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🚫 <b>Управление блокировками</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_banned_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:banned_list")
async def show_banned_list(callback: CallbackQuery):
    """Показывает список заблокированных пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.is_banned == True).order_by(User.created_at.desc())
        )
        banned_users = result.scalars().all()
        
        if not banned_users:
            await callback.message.edit_text(
                "📋 <b>Список заблокированных пользователей</b>\n\n"
                "✅ Нет заблокированных пользователей",
                reply_markup=get_admin_banned_keyboard()
            )
        else:
            text = f"📋 <b>Список заблокированных пользователей</b>\n\n"
            text += f"Всего заблокировано: <b>{len(banned_users)}</b>\n\n"
            
            for i, user in enumerate(banned_users[:20], 1):  # Показываем первых 20
                text += f"{i}. ID: <code>{user.telegram_id}</code>"
                if user.username:
                    text += f" | @{user.username}"
                if user.first_name:
                    text += f" | {user.first_name}"
                text += "\n"
            
            if len(banned_users) > 20:
                text += f"\n... и еще {len(banned_users) - 20}"
            
            await callback.message.edit_text(text, reply_markup=get_admin_banned_keyboard())
    
    await callback.answer()


@router.callback_query(F.data == "admin:ban_user")
async def start_ban_user(callback: CallbackQuery, state: FSMContext):
    """Начало блокировки пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🚫 <b>Блокировка пользователя</b>\n\n"
        "Введите Telegram ID пользователя для блокировки:",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_ban)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_ban)
async def process_ban_user(message: Message, state: FSMContext, bot: Bot):
    """Обработка блокировки пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID! Введите число.")
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_telegram_id}</code> не найден.",
                reply_markup=get_admin_banned_keyboard()
            )
            await state.clear()
            return
        
        if user.is_banned:
            await message.answer(
                f"⚠️ Пользователь <code>{user_telegram_id}</code> уже заблокирован.",
                reply_markup=get_admin_banned_keyboard()
            )
            await state.clear()
            return
        
        # Блокируем пользователя
        user.is_banned = True
        await session.commit()
        
        # Уведомляем пользователя
        await notify_user(
            bot,
            user_telegram_id,
            "🚫 <b>Вы заблокированы в системе</b>\n\n"
            "Доступ к боту ограничен.\n"
            "Обратитесь к администратору для получения дополнительной информации."
        )
        
        await message.answer(
            f"✅ Пользователь <code>{user_telegram_id}</code> успешно заблокирован.",
            reply_markup=get_admin_banned_keyboard()
        )
    
    await state.clear()


@router.callback_query(F.data == "admin:unban_user")
async def start_unban_user(callback: CallbackQuery, state: FSMContext):
    """Начало разблокировки пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "✅ <b>Разблокировка пользователя</b>\n\n"
        "Введите Telegram ID пользователя для разблокировки:",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_unban)
    await callback.answer()


@router.message(AdminStates.waiting_user_id_unban)
async def process_unban_user(message: Message, state: FSMContext, bot: Bot):
    """Обработка разблокировки пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID! Введите число.")
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_telegram_id}</code> не найден.",
                reply_markup=get_admin_banned_keyboard()
            )
            await state.clear()
            return
        
        if not user.is_banned:
            await message.answer(
                f"⚠️ Пользователь <code>{user_telegram_id}</code> не заблокирован.",
                reply_markup=get_admin_banned_keyboard()
            )
            await state.clear()
            return
        
        # Разблокируем пользователя
        user.is_banned = False
        await session.commit()
        
        # Уведомляем пользователя
        await notify_user(
            bot,
            user_telegram_id,
            "✅ <b>Вы разблокированы!</b>\n\n"
            "Доступ к боту восстановлен.\n"
            "Приятной игры! 🎰"
        )
        
        await message.answer(
            f"✅ Пользователь <code>{user_telegram_id}</code> успешно разблокирован.",
            reply_markup=get_admin_banned_keyboard()
        )
    
    await state.clear()


@router.callback_query(F.data == "admin:amnesty")
async def process_amnesty(callback: CallbackQuery, bot: Bot):
    """Разблокировка всех пользователей (амнистия)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        # Получаем всех заблокированных
        result = await session.execute(
            select(User).where(User.is_banned == True)
        )
        banned_users = result.scalars().all()
        
        if not banned_users:
            await callback.answer("✅ Нет заблокированных пользователей", show_alert=True)
            return
        
        count = len(banned_users)
        
        # Разблокируем всех
        for user in banned_users:
            user.is_banned = False
            # Уведомляем каждого
            await notify_user(
                bot,
                user.telegram_id,
                "🕊️ <b>АМНИСТИЯ!</b>\n\n"
                "Вы были разблокированы в рамках общей амнистии.\n"
                "Доступ к боту восстановлен.\n"
                "Приятной игры! 🎰"
            )
        
        await session.commit()
        
        await callback.message.edit_text(
            f"🕊️ <b>Амнистия выполнена!</b>\n\n"
            f"Разблокировано пользователей: <b>{count}</b>",
            reply_markup=get_admin_banned_keyboard()
        )
    
    await callback.answer()


# --- АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ ---

@router.callback_query(F.data == "admin:active")
async def show_active_users(callback: CallbackQuery):
    """Показывает список активных пользователей за последние 15 минут"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    time_threshold = datetime.utcnow() - timedelta(minutes=15)
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        # Получаем пользователей, сделавших ставки за последние 15 минут
        result = await session.execute(
            select(User)
            .join(Bet)
            .where(Bet.created_at >= time_threshold)
            .distinct()
            .order_by(Bet.created_at.desc())
        )
        active_users = result.scalars().all()
        
        if not active_users:
            await callback.message.edit_text(
                "📊 <b>Активные пользователи</b>\n\n"
                "⏰ За последние 15 минут нет активности",
                reply_markup=get_admin_back_keyboard()
            )
        else:
            text = f"📊 <b>Активные пользователи</b>\n\n"
            text += f"⏰ За последние 15 минут\n"
            text += f"Активных пользователей: <b>{len(active_users)}</b>\n\n"
            
            for i, user in enumerate(active_users[:20], 1):  # Показываем первых 20
                text += f"{i}. ID: <code>{user.telegram_id}</code>"
                if user.username:
                    text += f" | @{user.username}"
                if user.first_name:
                    text += f" | {user.first_name}"
                text += "\n"
            
            if len(active_users) > 20:
                text += f"\n... и еще {len(active_users) - 20}"
            
            await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard())
    
    await callback.answer()


# --- СТАТИСТИКА ---

@router.callback_query(F.data == "admin:stats")
async def show_stats(callback: CallbackQuery):
    """Показывает общую статистику бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    from src.database import async_session_maker
    async with async_session_maker() as session:
        # Общее количество пользователей
        total_users_result = await session.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar()
        
        # Количество заблокированных
        banned_users_result = await session.execute(
            select(func.count(User.id)).where(User.is_banned == True)
        )
        banned_users = banned_users_result.scalar()
        
        # Общее количество ставок
        total_bets_result = await session.execute(select(func.count(Bet.id)))
        total_bets = total_bets_result.scalar()
        
        # Общая сумма ставок
        total_wagered_result = await session.execute(select(func.sum(Bet.stake_cents)))
        total_wagered = total_wagered_result.scalar() or 0
        
        # Общая сумма выплат
        total_payout_result = await session.execute(select(func.sum(Bet.payout_cents)))
        total_payout = total_payout_result.scalar() or 0
        
        # Активные за последние 24 часа
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        active_24h_result = await session.execute(
            select(func.count(func.distinct(Bet.user_id)))
            .where(Bet.created_at >= time_threshold)
        )
        active_24h = active_24h_result.scalar()
        
        text = f"📈 <b>Статистика бота</b>\n\n"
        text += f"👥 Всего пользователей: <b>{total_users}</b>\n"
        text += f"🚫 Заблокировано: <b>{banned_users}</b>\n"
        text += f"📊 Активных за 24ч: <b>{active_24h}</b>\n\n"
        text += f"🎰 Всего ставок: <b>{total_bets}</b>\n"
        text += f"💰 Всего поставлено: <b>${total_wagered / 100:,.2f}</b>\n"
        text += f"💸 Всего выплачено: <b>${total_payout / 100:,.2f}</b>\n"
        
        profit = total_wagered - total_payout
        text += f"📊 Прибыль: <b>${profit / 100:,.2f}</b>"
        
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard())
    
    await callback.answer()


# --- РАССЫЛКА ---

@router.callback_query(F.data == "admin:broadcast")
async def show_broadcast_menu(callback: CallbackQuery):
    """Меню рассылки (заглушка)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "⚠️ Функция в разработке",
        reply_markup=get_admin_back_keyboard()
    )
    await callback.answer()

