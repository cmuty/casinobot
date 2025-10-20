from aiogram.fsm.state import State, StatesGroup


class LanguageStates(StatesGroup):
    """Состояния выбора языка"""
    choosing = State()


class RouletteStates(StatesGroup):
    """Состояния игры в рулетку"""
    choosing_stake = State()
    choosing_bet = State()


class SlotsStates(StatesGroup):
    """Состояния игры в слоты"""
    choosing_stake = State()


class DiceStates(StatesGroup):
    """Состояния игры в кости"""
    choosing_stake = State()

class MinesStates(StatesGroup):
    """Состояния игры в мины"""
    choosing_stake = State()
    playing = State()

class RocketStates(StatesGroup):
    """Состояния игры в ракетку"""
    choosing_stake = State()
    playing = State()

# НОВОЕ: Состояния для удаления аккаунта
class DeletionStates(StatesGroup):
    """Состояния удаления аккаунта"""
    confirm = State()

# НОВОЕ: Состояния для настроек (если потребуется)
class SettingsStates(StatesGroup):
    """Состояния настроек"""
    choosing_option = State()

# НОВОЕ: Состояния для админ-панели
class AdminStates(StatesGroup):
    """Состояния админ-панели"""
    # Управление пользователями
    waiting_user_id_search = State()  # Ожидание ID для поиска
    waiting_user_id_delete = State()  # Ожидание ID для удаления
    waiting_user_id_add_balance = State()  # Ожидание ID для выдачи валюты
    waiting_amount_add_balance = State()  # Ожидание суммы для выдачи
    waiting_user_id_set_balance = State()  # Ожидание ID для изменения валюты
    waiting_amount_set_balance = State()  # Ожидание суммы для изменения
    
    # Блокировки
    waiting_user_id_ban = State()  # Ожидание ID для блокировки
    waiting_user_id_unban = State()  # Ожидание ID для разблокировки