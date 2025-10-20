from aiogram import Router, F
from aiogram.filters import CommandStart, Command # Добавлен Command
from aiogram.types import Message
from sqlalchemy import select
from src.models import User
from src.services.wallet_service import wallet_service
from src.config import settings
from src.utils.keyboards import get_main_menu_keyboard, get_games_keyboard
from src.i18n.translator import translator

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    from src.database import async_session_maker
    
    telegram_id = message.from_user.id
    
    # Проверяем тип чата
    if message.chat.type in ['group', 'supergroup']:
        # В группе отправляем только текст, без клавиатуры
        await message.answer(
           "🎰 <b>Добро пожаловать в HightRoll Casino!</b>\n\n"
           "Погнали крутить барабаны!\n\n"
           "💡 Используй <code>/help</code> чтобы узнать все команды."
        )
        return # Завершаем обработку, не выполняя остальной код функции

    async with async_session_maker() as session:
        # Проверяем существование пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        # Новый пользователь
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language_code=message.from_user.language_code or 'en',
                personality='playful' # НОВОЕ: Устанавливаем персональность по умолчанию
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            # Создаём кошелёк и начисляем стартовый бонус
            await wallet_service.credit(
                user.id,
                settings.STARTER_BONUS,
                'starter_bonus'
            )
            
            user.received_starter_bonus = True
            await session.commit()
            
            # Приветствие
            text = translator.get(
                'welcome.first_time',
                user.language_code,
                balance=f"${settings.STARTER_BONUS / 100:.0f}"
            )
        else:
            # Существующий пользователь
            balance = await wallet_service.get_balance(user.id)
            text = translator.get(
                'welcome.returning',
                user.language_code,
                name=user.first_name,
                balance=f"${balance / 100:.2f}"
            )
    
    # Отправляем приветствие и клавиатуру ТОЛЬКО в личных сообщениях
    await message.answer(
        text,
        reply_markup=get_main_menu_keyboard()
    )

@router.message(Command('help'))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    # Проверяем тип чата
    if message.chat.type in ['group', 'supergroup']:
        help_text = (
            "🎰 <b>Добро пожаловать в HightRoll!</b>\n\n"
            "Этот бот позволяет играть в азартные игры, зарабатывать и тратить виртуальную валюту 💰, "
            "прокачивать профиль и получать бонусы каждый день!\n\n"
            
                   "<b>📌 Основные команды:</b>\n"
                   "• /start - Начать работу с ботом 🎁\n"
                   "• /help - Показать вспомогательное сообщение\n"
                   "• /balance - Проверить баланс монет 💎\n"
                   "• /profile - Посмотреть профиль, статистику и достижения 🏆\n"
                   "• /bonus - Получить ежедневный бонус 🎉\n"
                   "• /buy - Купить монеты через Telegram Stars 💳\n"
                   "• /settings - Персональные настройки ⚙️\n\n"

                   "<b>🎮 Доступные игры:</b>\n"
                   "• /slots - Игровые слоты с шансом выиграть монеты 🎰\n"
                   "• /dice - Кости: угадай число и выиграй 🎲\n"
                   "• /roulette - Рулетка: ставь на цвет, число или диапазон 🎡\n"
                   "• /mines - Мины: открой клетки и избегай бомб 💣\n\n"
            
                   "<b>💡 Использование в группах:</b>\n"
                   "• <code>/dice 50</code> - игра в кости со ставкой $50\n"
                   "• <code>/slots 25</code> - игра в слоты со ставкой $25\n"
                   "• <code>/roulette 100</code> - игра в рулетку со ставкой $100\n"
                   "• <code>/mines 200</code> - игра в мины со ставкой $200\n\n"
            
            "<b>⭐ Особенности бота:</b>\n"
            "• Виртуальная валюта — монеты, которые можно зарабатывать и тратить 💰\n"
            "• Ежедневные бонусы для активных игроков 🎁\n"
            "• Прокачка профиля и отслеживание статистики побед и проигрышей 📊\n\n"
            
            "Используй команды с параметрами в группах или полное меню в личных сообщениях! 💎"
        )
        await message.answer(help_text)
        return

    help_text = (
    "🎰 <b>Добро пожаловать в HightRoll!</b>\n\n"
    "Этот бот позволяет играть в азартные игры, зарабатывать и тратить виртуальную валюту 💰, "
    "прокачивать профиль и получать бонусы каждый день!\n\n"
    "<b></b>\n"
    
    "<b>📌 Основные команды:</b>\n"
    "• /start - Начать работу с ботом 🎁\n"
    "• /help - Показать вспомогательное сообщение\n"
    "• /balance - Проверить баланс монет 💎\n"
    "• /profile - Посмотреть профиль, статистику и достижения 🏆\n"
    "• /bonus - Получить ежедневный бонус 🎉\n"
    "• /buy - Купить монеты через Telegram Stars 💳\n"
    "• /settings - Персональные настройки ⚙️\n" # НОВОЕ

    "<b></b>\n"

    "<b>🎮 Доступные игры:</b>\n"
    "• /slots - Игровые слоты с шансом выиграть монеты 🎰\n"
    "• /dice - Кости: угадай число и выиграй 🎲\n"
    "• /roulette - Рулетка: ставь на цвет, число или диапазон 🎡\n"
    "• /mines - Мины: открой клетки и избегай бомб 💣\n"
    
    "<b></b>\n"

    "<b>⭐ Особенности бота:</b>\n"
    "• Виртуальная валюта — монеты, которые можно зарабатывать и тратить 💰\n"
    "• Ежедневные бонусы для активных игроков 🎁\n"
    "• Прокачка профиля и отслеживание статистики побед и проигрышей 📊\n"
    
    "<b></b>\n"

    "Используй кнопки в меню в личных сообщениях или вводи команды вручную, чтобы начать играть прямо сейчас! 💎"
    )
    await message.answer(help_text)


# --- ОБРАБОТЧИКИ КНОПОК МЕНЮ ---

@router.message(F.text == "🎮 Игры")
async def show_games_menu(message: Message):
    """Показывает меню игр"""
    # Проверяем тип чата - только для личных сообщений
    if message.chat.type in ['group', 'supergroup']:
        return
    
    await message.answer(
        "🎮 <b>Выберите игру:</b>\n\n"
        "🎰 <b>Слоты</b> - классические игровые автоматы\n"
        "🎲 <b>Кости</b> - дуэль с ботом на удачу\n"
        "♠️ <b>Рулетка</b> - ставки на цвет и числа\n"
        "💣 <b>Мины</b> - открой клетки и избегай бомб\n"
        "🚀 <b>Ракетка</b> - растущий коэффициент до взрыва",
        reply_markup=get_games_keyboard()
    )


@router.message(F.text == "🔙 Назад")
async def back_to_main_menu(message: Message):
    """Возврат в главное меню"""
    # Проверяем тип чата - только для личных сообщений
    if message.chat.type in ['group', 'supergroup']:
        return
    
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )
