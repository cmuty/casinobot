from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    builder.button(text="🇬🇧 English", callback_data="lang:en")
    builder.adjust(2)
    return builder.as_markup()

def get_main_menu_keyboard(lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Главное меню (только для личных сообщений)"""
    # Эта функция просто *создаёт* клавиатуру.
    # Решение, *отправлять* её или нет, принимается *в обработчике команды*,
    # где проверяется message.chat.type.
    texts = {
        'ru': {
            'games': '🎮 Игры',
            'profile': '👤 Профиль',
            'bonus': '🎁 Бонус',
            'balance': '💰 Баланс',
            'settings': '⚙️ Настройки'
        },
        'en': {
            'games': '🎮 Games',
            'profile': '👤 Profile',
            'bonus': '🎁 Bonus',
            'balance': '💰 Balance',
            'settings': '⚙️ Settings'
        }
    }
    
    t = texts.get(lang, texts['ru'])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t['games']),
                KeyboardButton(text=t['profile'])
            ],
            [
                KeyboardButton(text=t['bonus']),
                KeyboardButton(text=t['balance'])
            ],
            [
                KeyboardButton(text=t['settings'])
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_games_keyboard(lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Клавиатура игр (только для личных сообщений)"""
    texts = {
        'ru': {
            'slots': '🎰 Слоты',
            'dice': '🎲 Кости',
            'roulette': '♠️ Рулетка',
            'mines': '💣 Мины',
            'rocket': '🚀 Ракетка',
            'back': '🔙 Назад'
        },
        'en': {
            'slots': '🎰 Slots',
            'dice': '🎲 Dice',
            'roulette': '♠️ Roulette',
            'mines': '💣 Mines',
            'rocket': '🚀 Rocket',
            'back': '🔙 Back'
        }
    }
    
    t = texts.get(lang, texts['ru'])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t['slots']),
                KeyboardButton(text=t['dice'])
            ],
            [
                KeyboardButton(text=t['roulette']),
                KeyboardButton(text=t['mines'])
            ],
            [
                KeyboardButton(text=t['rocket'])
            ],
            [
                KeyboardButton(text=t['back'])
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_settings_keyboard(lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Клавиатура настроек (только для личных сообщений)"""
    # Эта функция просто *создаёт* клавиатуру.
    # Решение, *отправлять* её или нет, принимается *в обработчике команды*,
    # где проверяется message.chat.type.
    texts = {
        'ru': {
            'export_data': '📦 Экспорт данных',
            'delete_account': '🗑️ Удалить аккаунт',
            'back': '🔙 Назад'
        },
        'en': {
            'export_data': '📦 Export Data',
            'delete_account': '🗑️ Delete Account',
            'back': '🔙 Back'
        }
    }
    
    t = texts.get(lang, texts['ru'])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t['export_data']),
            ],
            [
                KeyboardButton(text=t['delete_account']),
            ],
            [
                KeyboardButton(text=t['back']), # Пока ведёт назад в главное меню
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_stake_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура выбора ставки"""
    builder = InlineKeyboardBuilder()
    
    stakes = [
        ("$1", "stake:100"),
        ("$5", "stake:500"),
        ("$10", "stake:1000"),
        ("$20", "stake:2000"),
        ("$50", "stake:5000"),
        ("$100", "stake:10000"),
    ]
    
    for text, data in stakes:
        builder.button(text=text, callback_data=data)
    
    cancel_text = "❌ Отмена" if lang == 'ru' else "❌ Cancel"
    builder.button(text=cancel_text, callback_data="cancel")
    
    builder.adjust(3, 3, 1)
    return builder.as_markup()


def get_roulette_bet_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура выбора ставки в рулетке"""
    builder = InlineKeyboardBuilder()
    
    if lang == 'ru':
        builder.button(text="🔴 Красное", callback_data="roulette:red")
        builder.button(text="⚫ Чёрное", callback_data="roulette:black")
    else:
        builder.button(text="🔴 Red", callback_data="roulette:red")
        builder.button(text="⚫ Black", callback_data="roulette:black")
    
    # Числа 1-10
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"roulette:{i}")
    
    cancel_text = "❌ Отмена" if lang == 'ru' else "❌ Cancel"
    builder.button(text=cancel_text, callback_data="cancel")
    
    builder.adjust(2, 5, 5, 1)
    return builder.as_markup()


def get_cancel_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура отмены"""
    builder = InlineKeyboardBuilder()
    cancel_text = "❌ Отмена" if lang == 'ru' else "❌ Cancel"
    builder.button(text=cancel_text, callback_data="cancel")
    return builder.as_markup()


# --- АДМИН-ПАНЕЛЬ ---

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Управление юзерами", callback_data="admin:users")
    builder.button(text="🚫 Заблокированные юзеры", callback_data="admin:banned")
    builder.button(text="📊 Активные юзеры", callback_data="admin:active")
    builder.button(text="📈 Статистика", callback_data="admin:stats")
    builder.button(text="📢 Рассылка", callback_data="admin:broadcast")
    builder.button(text="🔙 Закрыть", callback_data="admin:close")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def get_admin_users_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления пользователями"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Найти юзера", callback_data="admin:user_search")
    builder.button(text="🗑️ Удалить юзера", callback_data="admin:user_delete")
    builder.button(text="💰 Выдать валюту", callback_data="admin:user_add_balance")
    builder.button(text="✏️ Изменить валюту", callback_data="admin:user_set_balance")
    builder.button(text="🔙 Назад", callback_data="admin:main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_admin_banned_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления блокировками"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список заблокированных", callback_data="admin:banned_list")
    builder.button(text="🚫 Заблокировать", callback_data="admin:ban_user")
    builder.button(text="✅ Разблокировать", callback_data="admin:unban_user")
    builder.button(text="🕊️ Амнистия", callback_data="admin:amnesty")
    builder.button(text="🔙 Назад", callback_data="admin:main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="admin:main")
    return builder.as_markup()


def get_back_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Универсальная клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    back_text = "🔙 Назад" if lang == 'ru' else "🔙 Back"
    builder.button(text=back_text, callback_data="back")
    return builder.as_markup()