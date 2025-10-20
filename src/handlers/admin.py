from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func
from src.models import User, Bet
from src.config import settings
from src.services.wallet_service import wallet_service
from src.utils.keyboards import get_main_menu_keyboard # Импортируем, если нужно показать меню после команды

router = Router()

def is_admin(telegram_id: int) -> bool:
    """Проверка прав администратора"""
    return telegram_id == settings.ADMIN_ID

@router.message(Command('admin_stats'))
async def cmd_admin_stats(message: Message):
    """Статистика казино (только для админа)"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Access denied")
        return

    # Проверяем тип чата: если группа — выполним логику, но не отправим клавиатуру (её и не планировали)
    # В данном случае, логика выполнится везде, но клавиатура не отправляется.
    # Это соответствует обновлённым требованиям: команды / работают, но меню не показывается.
    from src.database import async_session_maker
    async with async_session_maker() as session:
        # Всего пользователей
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        # Всего ставок
        total_bets = await session.execute(select(func.count(Bet.id)))
        total_bets = total_bets.scalar()
        # Объём ставок
        total_wagered = await session.execute(select(func.sum(Bet.stake_cents)))
        total_wagered = total_wagered.scalar() or 0
        # Выплачено
        total_payout = await session.execute(select(func.sum(Bet.payout_cents)))
        total_payout = total_payout.scalar() or 0
        # House edge
        house_edge = ((total_wagered - total_payout) / total_wagered * 100) if total_wagered > 0 else 0

        text = (
            f"🔧 <b>Статус казино</b>\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"🎰 Всего ставок: {total_bets}\n"
            f"💰 Объём ставок: ${total_wagered / 100:.2f}\n"
            f"🎁 Выплачено: ${total_payout / 100:.2f}\n"
            f"📊 House edge: {house_edge:.2f}%\n"
            f"⚙️ Система: 🟢 Online"
        )
        await message.answer(text)
        # Не отправляем клавиатуру в группе
        # if message.chat.type not in ['group', 'supergroup']:
        #     await message.answer("Меню:", reply_markup=get_main_menu_keyboard())
        # # Убрано: не отправляем меню


@router.message(Command('admin_credit'))
async def cmd_admin_credit(message: Message):
    """Начислить средства пользователю"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Access denied")
        return

    # Проверяем тип чата: если группа — выполним логику, но не отправим клавиатуру (её и не планировали)
    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer("Usage: /admin_credit [telegram_id] [amount]")
        return

    try:
        target_telegram_id = int(args[0])
        amount_dollars = float(args[1])
        amount_cents = int(amount_dollars * 100)
    except ValueError:
        await message.answer("❌ Неверные параметры")
        return

    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        await wallet_service.credit(
            user.id,
            amount_cents,
            f'admin_credit:by_{message.from_user.id}'
        )
        await message.answer(
            f"✅ Начислено <b>${amount_dollars:.2f}</b> пользователю {user.first_name or user.telegram_id}"
        )
        # Не отправляем клавиатуру в группе
        # if message.chat.type not in ['group', 'supergroup']:
        #     await message.answer("Меню:", reply_markup=get_main_menu_keyboard())
        # # Убрано: не отправляем меню
