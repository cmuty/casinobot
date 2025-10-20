from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from datetime import datetime

from src.models import User
from src.services.rating_service import RatingService, CreditService, VIPService
from src.services.wallet_service import wallet_service
from src.utils.keyboards import get_back_keyboard
from src.utils.ban_check import check_if_banned

router = Router()


@router.message(Command('rating'))
async def cmd_rating(message: Message):
    """Команда для просмотра рейтингов (алиас для leaderboard)"""
    await cmd_leaderboard(message)


@router.message(Command('leaderboard'))
async def cmd_leaderboard(message: Message):
    """Команда для просмотра лидерборда"""
    if await check_if_banned(message):
        return
    
    # Проверяем тип чата - только для личных сообщений
    if message.chat.type in ['group', 'supergroup']:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Дневной", callback_data="leaderboard:daily")],
        [InlineKeyboardButton(text="📊 Недельный", callback_data="leaderboard:weekly")],
        [InlineKeyboardButton(text="🏆 Месячный", callback_data="leaderboard:monthly")],
        [InlineKeyboardButton(text="🎁 Мои награды", callback_data="leaderboard:rewards")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ])
    
    text = (
        "🏆 <b>Лидерборды LuckyStar Casino</b>\n\n"
        "📅 <b>Дневной</b> - топ игроков за день\n"
        "📊 <b>Недельный</b> - топ игроков за неделю\n"
        "🏆 <b>Месячный</b> - топ игроков за месяц\n\n"
        "💡 <b>Награды за места:</b>\n"
        "🥇 1 место - $1500\n"
        "🥈 2 место - $700\n"
        "🥉 3 место - $400"
    )
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "leaderboard:menu")
async def show_leaderboard_menu(callback: CallbackQuery):
    """Показывает меню лидербордов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Дневной", callback_data="leaderboard:daily")],
        [InlineKeyboardButton(text="📊 Недельный", callback_data="leaderboard:weekly")],
        [InlineKeyboardButton(text="🏆 Месячный", callback_data="leaderboard:monthly")],
        [InlineKeyboardButton(text="🎁 Мои награды", callback_data="leaderboard:rewards")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ])
    
    text = (
        "🏆 <b>Лидерборды</b>\n\n"
        "Выберите период для просмотра рейтинга игроков:\n\n"
        "📅 <b>Дневной</b> - топ игроков за сегодня\n"
        "📊 <b>Недельный</b> - топ игроков за неделю\n"
        "🏆 <b>Месячный</b> - топ игроков за месяц\n\n"
        "💡 <b>Награды за места:</b>\n"
        "🥇 1 место - $1500\n"
        "🥈 2 место - $700\n"
        "🥉 3 место - $400"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except:
        await callback.message.answer(text, reply_markup=keyboard)
    
    await callback.answer()


@router.callback_query(F.data.startswith("leaderboard:"))
async def show_leaderboard(callback: CallbackQuery):
    """Показывает лидерборд за период"""
    if callback.data == "leaderboard:rewards":
        await show_user_rewards(callback)
        return
    
    period = callback.data.split(":")[1]
    period_names = {
        'daily': 'дневной',
        'weekly': 'недельный', 
        'monthly': 'месячный'
    }
    
    leaderboard = await RatingService.get_leaderboard(period, 10)
    
    if not leaderboard:
        text = f"📊 <b>{period_names[period].title()} лидерборд</b>\n\n❌ Пока нет данных за этот период"
    else:
        text = f"📊 <b>{period_names[period].title()} лидерборд</b>\n\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, player in enumerate(leaderboard):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            username = player['username'] or player['first_name'] or f"User{player['user_id']}"
            winnings = player['total_winnings'] / 100
            win_rate = player['win_rate']
            
            text += f"{medal} <b>{username}</b>\n"
            text += f"   💰 Выигрыш: ${winnings:.2f}\n"
            text += f"   📈 Винрейт: {win_rate}%\n"
            text += f"   🎮 Игр: {player['total_bets']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="leaderboard:menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "leaderboard:rewards")
async def show_user_rewards(callback: CallbackQuery):
    """Показывает награды пользователя"""
    user_id = callback.from_user.id
    
    # Получаем пользователя из БД
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
    
    rewards = await RatingService.get_user_rewards(user.id)
    
    if not rewards:
        text = "🎁 <b>Мои награды</b>\n\n❌ У вас пока нет наград"
    else:
        text = "🎁 <b>Мои награды</b>\n\n"
        
        for reward in rewards:
            position_medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            medal = position_medals.get(reward['position'], f"{reward['position']}.")
            amount = reward['amount'] / 100
            period_names = {'daily': 'дневной', 'weekly': 'недельный', 'monthly': 'месячный'}
            period = period_names.get(reward['period'], reward['period'])
            status = "✅ Получено" if reward['is_claimed'] else "⏳ Ожидает"
            
            text += f"{medal} <b>{period.title()} лидерборд</b>\n"
            text += f"   💰 Награда: ${amount:.0f}\n"
            text += f"   📅 Дата: {reward['rewarded_at'].strftime('%d.%m.%Y')}\n"
            text += f"   {status}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="leaderboard:menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()




@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery):
    """Возврат к профилю"""
    await callback.answer()
    # Имитируем команду профиля
    from src.handlers.profile import cmd_profile
    await cmd_profile(callback.message)


@router.callback_query(F.data == "credits:menu")
async def credits_menu(callback: CallbackQuery):
    """Меню кредитов"""
    if await check_if_banned(callback):
        return
    
    from src.database import get_session
    from src.models import User
    from src.services.rating_service import CreditService
    
    telegram_id = callback.from_user.id
    
    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        if not user.is_vip:
            await callback.answer("❌ Кредиты доступны только VIP пользователям")
            return
        
        # Получаем доступные кредиты
        available_credits = await CreditService.get_available_credits(user.id)
        
        text = "💳 <b>Система кредитов</b>\n\n"
        text += "💰 <b>Доступные кредиты:</b>\n"
        
        if available_credits:
            for credit in available_credits:
                amount = credit['amount'] / 100
                limit_type = credit['limit_type']
                
                if limit_type == 'daily_1k':
                    text += f"├ 💵 $1000 (каждые 3 дня)\n"
                elif limit_type == 'weekly_5k':
                    text += f"├ 💰 $5000 (каждую неделю)\n"
                elif limit_type == 'monthly_15k':
                    text += f"├ 💎 $15000 (каждый месяц)\n"
        else:
            text += "├ ❌ Нет доступных кредитов\n"
        
        text += "\n💡 <b>Условия:</b>\n"
        text += "├ 📅 Возврат через 7 дней\n"
        text += "├ 📈 Процент: 10%\n"
        text += "└ ⚠️ При просрочке: блокировка аккаунта"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 Взять $1000", callback_data="credit:take:1000")],
            [InlineKeyboardButton(text="💰 Взять $5000", callback_data="credit:take:5000")],
            [InlineKeyboardButton(text="💎 Взять $15000", callback_data="credit:take:15000")],
            [InlineKeyboardButton(text="📋 Мои кредиты", callback_data="credit:list")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
        ])
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        
        await callback.answer()


@router.callback_query(F.data.startswith("credit:take:"))
async def take_credit(callback: CallbackQuery):
    """Взятие кредита"""
    if await check_if_banned(callback):
        return
    
    from src.database import get_session
    from src.models import User
    from src.services.rating_service import CreditService
    from src.services.wallet_service import wallet_service
    
    telegram_id = callback.from_user.id
    amount_str = callback.data.split(":")[2]
    amount_cents = int(amount_str) * 100
    
    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        if not user.is_vip:
            await callback.answer("❌ Кредиты доступны только VIP пользователям")
            return
        
        # Определяем тип лимита
        if amount_cents == 100000:  # $1000
            limit_type = 'daily_1k'
        elif amount_cents == 500000:  # $5000
            limit_type = 'weekly_5k'
        elif amount_cents == 1500000:  # $15000
            limit_type = 'monthly_15k'
        else:
            await callback.answer("❌ Неверная сумма кредита")
            return
        
        # Проверяем доступность кредита
        success = await CreditService.take_credit(user.id, amount_cents, limit_type)
        
        if success:
            # Добавляем деньги на баланс
            await wallet_service.credit(user.id, amount_cents, "credit")
            
            await callback.answer(f"✅ Кредит ${amount_str} выдан успешно!")
            
            # Возвращаемся в меню кредитов
            await credits_menu(callback)
        else:
            await callback.answer("❌ Кредит недоступен. Проверьте лимиты.")


@router.callback_query(F.data == "credit:list")
async def list_credits(callback: CallbackQuery):
    """Список кредитов пользователя"""
    if await check_if_banned(callback):
        return
    
    from src.database import get_session
    from src.models import User
    from src.services.rating_service import CreditService
    
    telegram_id = callback.from_user.id
    
    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        # Получаем активные кредиты
        active_credits = await CreditService.get_user_credits(user.id)
        
        text = "📋 <b>Мои кредиты</b>\n\n"
        
        keyboard_buttons = []
        
        if active_credits:
            for credit in active_credits:
                amount = credit['amount'] / 100
                amount_to_repay = credit['amount_to_repay'] / 100
                status_icons = {
                    'active': '🟢',
                    'overdue': '🔴',
                    'paid': '✅'
                }
                status_text = {
                    'active': 'Активный',
                    'overdue': 'Просрочен',
                    'paid': 'Погашен'
                }
                
                text += f"💳 <b>Кредит ${amount:.0f}</b>\n"
                text += f"   💸 К возврату: ${amount_to_repay:.0f}\n"
                text += f"   📅 Выдан: {credit['issued_at'].strftime('%d.%m.%Y')}\n"
                text += f"   ⏰ Срок: {credit['due_date'].strftime('%d.%m.%Y')}\n"
                text += f"   {status_icons[credit['status']]} {status_text[credit['status']]}\n\n"
                
                # Добавляем кнопку возврата для активных кредитов
                if credit['status'] == 'active':
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=f"💰 Вернуть ${amount_to_repay:.0f}", 
                            callback_data=f"credit:repay:{credit['id']}"
                        )
                    ])
        else:
            text += "📝 У вас нет активных кредитов"
        
        # Добавляем кнопку "Назад"
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="credits:menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        
        await callback.answer()


@router.callback_query(F.data == "vip:bonuses")
async def vip_bonuses(callback: CallbackQuery):
    """VIP бонусы"""
    if await check_if_banned(callback):
        return
    
    from src.database import get_session
    from src.models import User
    
    telegram_id = callback.from_user.id
    
    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        if not user.is_vip:
            await callback.answer("❌ VIP бонусы доступны только VIP пользователям")
            return
        
        # Статус бонусов
        cashback_status = "✅ Включен" if user.vip_cashback_enabled else "❌ Выключен"
        multiplier_status = "✅ Включен" if user.vip_multiplier_enabled else "❌ Выключен"
        
        text = "⭐ <b>VIP бонусы</b>\n\n"
        text += "💰 <b>Возврат средств:</b>\n"
        text += f"├ Статус: {cashback_status}\n"
        text += f"├ Процент: {user.vip_cashback_percentage}%\n"
        text += f"└ Возврат части проигранной суммы\n\n"
        text += "🎯 <b>Множитель выигрышей:</b>\n"
        text += f"├ Статус: {multiplier_status}\n"
        text += f"├ Множитель: {user.vip_multiplier_value/100:.1f}x\n"
        text += f"└ Увеличение выигрышей на 30%\n\n"
        text += "💡 <b>Как работает:</b>\n"
        text += "├ При проигрыше: возврат части суммы\n"
        text += "└ При выигрыше: увеличение приза"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💰 Возврат: {'Выключить' if user.vip_cashback_enabled else 'Включить'}", 
                callback_data=f"vip:toggle:cashback"
            )],
            [InlineKeyboardButton(
                text=f"🎯 Множитель: {'Выключить' if user.vip_multiplier_enabled else 'Включить'}", 
                callback_data=f"vip:toggle:multiplier"
            )],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
        ])
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        
        await callback.answer()


@router.callback_query(F.data.startswith("credit:repay:"))
async def repay_credit(callback: CallbackQuery):
    """Возврат кредита"""
    if await check_if_banned(callback):
        return
    
    from src.database import get_session
    from src.models import User
    from src.services.rating_service import CreditService
    
    telegram_id = callback.from_user.id
    credit_id = int(callback.data.split(":")[2])
    
    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        # Возвращаем кредит
        success, message = await CreditService.repay_credit(user.id, credit_id)
        
        if success:
            await callback.answer(f"✅ {message}")
            # Возвращаемся к списку кредитов
            await list_credits(callback)
        else:
            await callback.answer(f"❌ {message}")


@router.callback_query(F.data.startswith("vip:toggle:"))
async def toggle_vip_bonus(callback: CallbackQuery):
    """Переключение VIP бонусов"""
    if await check_if_banned(callback):
        return
    
    from src.database import get_session
    from src.models import User
    
    telegram_id = callback.from_user.id
    bonus_type = callback.data.split(":")[2]
    
    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        if not user.is_vip:
            await callback.answer("❌ VIP бонусы доступны только VIP пользователям")
            return
        
        # Переключаем бонус
        if bonus_type == "cashback":
            user.vip_cashback_enabled = not user.vip_cashback_enabled
            status = "включен" if user.vip_cashback_enabled else "выключен"
            await callback.answer(f"💰 Возврат средств {status}")
        elif bonus_type == "multiplier":
            user.vip_multiplier_enabled = not user.vip_multiplier_enabled
            status = "включен" if user.vip_multiplier_enabled else "выключен"
            await callback.answer(f"🎯 Множитель выигрышей {status}")
        
        await session.commit()
        
        # Возвращаемся в меню VIP бонусов
        await vip_bonuses(callback)
