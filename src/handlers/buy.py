from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from src.models import User
from src.services.wallet_service import wallet_service
from src.utils.ban_check import check_if_banned
# Убираем импорт async_session_maker, будем использовать локальный импорт

router = Router()

# Курс обмена: 1 Telegram Star = 10 центов (0.10$) - выгодный курс!
STAR_TO_CENT_RATE = 10

# Доступные пакеты для покупки
PACKAGES = {
    "small": {
        "stars": 100,
        "cents": 100000,  # $1000
        "name": "💰 Пакет бомжа",
        "description": "100 Telegram Stars → $1000"
    },
    "medium": {
        "stars": 500,
        "cents": 500000,  # $5000
        "name": "💎 Пакет дэпера", 
        "description": "500 Telegram Stars → $5000"
    },
    "large": {
        "stars": 1000,
        "cents": 1200000,  # $12000
        "name": "👑 Пакет хайроллера",
        "description": "1000 Telegram Stars → $12000"
    },
    "mega": {
        "stars": 2000,
        "cents": 3500000,  # $35000
        "name": "🚀 ПАКЕТ КУПЬЕРА",
        "description": "2000 Telegram Stars → $35000"
    }
}


@router.message(Command('buy'))
async def cmd_buy(message: Message):
    """Показывает доступные пакеты для покупки"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = message.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    # Создаем клавиатуру с пакетами
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=PACKAGES["small"]["name"],
                callback_data=f"buy_package:small"
            )
        ],
        [
            InlineKeyboardButton(
                text=PACKAGES["medium"]["name"],
                callback_data=f"buy_package:medium"
            )
        ],
        [
            InlineKeyboardButton(
                text=PACKAGES["large"]["name"],
                callback_data=f"buy_package:large"
            )
        ],
        [
            InlineKeyboardButton(
                text=PACKAGES["mega"]["name"],
                callback_data=f"buy_package:mega"
            )
        ]
    ])

    text = "💳 <b>Покупка монет</b>\n\n"
    text += "Выберите пакет для покупки:\n\n"
    
    for package_id, package in PACKAGES.items():
        if package_id == "mega":
            # Выделяем пакет купьера
            text += f"🔥 <b>{package['name']}</b> 🔥\n"
            text += f"<b>{package['description']}</b>\n\n"
        else:
            text += f"{package['name']}\n"
            text += f"{package['description']}\n\n"

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith('buy_package:'))
async def handle_buy_package(callback_query, bot):
    """Обрабатывает выбор пакета для покупки"""
    await callback_query.answer()
    
    package_id = callback_query.data.split(':')[1]
    if package_id not in PACKAGES:
        await callback_query.message.edit_text("❌ Неверный пакет")
        return
    
    package = PACKAGES[package_id]
    
    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = callback_query.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await callback_query.message.edit_text("❌ Сначала запустите бота командой /start")
            return

    try:
        # Создаем инвойс для Telegram Stars
        await bot.send_invoice(
            chat_id=callback_query.message.chat.id,
            title=package["name"],
            description=package["description"],
            payload=f"buy_{package_id}_{user.id}",
            provider_token="",  # Для Telegram Stars не нужен provider_token
            currency="XTR",  # Telegram Stars
            prices=[LabeledPrice(label=package["name"], amount=package["stars"])],
            start_parameter=f"buy_{package_id}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False
        )
        
        await callback_query.message.delete()
        
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Ошибка при создании платежа: {e}")


@router.message(lambda message: message.successful_payment is not None)
async def handle_successful_payment(message: Message):
    """Обрабатывает успешный платеж"""
    payment = message.successful_payment
    
    # Извлекаем данные из payload
    payload_parts = payment.invoice_payload.split('_')
    if len(payload_parts) != 3 or payload_parts[0] != "buy":
        await message.answer("❌ Неверный формат платежа")
        return
    
    package_id = payload_parts[1]
    user_id = int(payload_parts[2])
    
    if package_id not in PACKAGES:
        await message.answer("❌ Неверный пакет")
        return
    
    package = PACKAGES[package_id]
    
    # Проверяем пользователя
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        # Проверяем сумму платежа
        if payment.total_amount != package["stars"]:
            await message.answer("❌ Неверная сумма платежа")
            return
        
        # Зачисляем деньги на баланс
        await wallet_service.add_funds(user.id, package["cents"], "purchase")
        
        # Получаем новый баланс
        new_balance = await wallet_service.get_balance(user.id)
        
        # Отправляем подтверждение
        text = f"✅ <b>Покупка успешна!</b>\n\n"
        text += f"📦 Пакет: {package['name']}\n"
        text += f"💰 Получено: ${package['cents'] / 100:.2f}\n"
        text += f"💵 Новый баланс: ${new_balance / 100:.2f}\n\n"
        text += "Спасибо за покупку! 🎉"
        
        await message.answer(text)
