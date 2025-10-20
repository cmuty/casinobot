from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
import asyncio
import secrets
import random

from src.models import User
from src.services.wallet_service import wallet_service
from src.services.bet_service import bet_service
from src.services.rating_service import VIPService, CreditService, RatingService
from src.games.slots import SlotMachine
from src.games.dice import DiceGame
from src.games.roulette import RouletteGame
from src.games.mines import MinesGame
from src.games.rocket import RocketGame
from src.config import settings
from src.i18n.translator import translator
from src.states import RouletteStates, SlotsStates, DiceStates, MinesStates, RocketStates
# НОВОЕ:
from src.services.personality_engine import PersonalityEngine
from src.services.rating_service import RatingService, VIPService
from src.utils.keyboards import get_games_keyboard
from src.utils.ban_check import check_if_banned

router = Router()

# Вспомогательная функция для форматирования денежных сумм
def format_money(cents: int) -> str:
    """Форматирует сумму в центах в строку вида '1,234.56' (в долларах)"""
    dollars = cents / 100
    return f"{dollars:,.2f}" # Использует запятую как разделитель тысяч и 2 знака после запятой

# Вспомогательная функция для форматирования целых чисел (например, для ставки в центах, если нужно)
def format_number(num: int) -> str:
    """Форматирует целое число с разделителями тысяч"""
    return f"{num:,}"


async def process_game_result(user_id: int, stake_cents: int, win_amount: int, game_type: str):
    """Обрабатывает результат игры: обновляет рейтинги и применяет VIP бонусы"""
    vip_message = ""
    credit_message = ""
    
    if win_amount > 0:
        # Выигрыш - применяем VIP множитель
        total_win, vip_message = await VIPService.apply_vip_multiplier(user_id, win_amount)
        
        # Автоматический возврат кредитов
        remaining_win, credit_message = await CreditService.auto_repay_from_winnings(user_id, total_win)
        
        # Начисляем остаток выигрыша
        if remaining_win > 0:
            await wallet_service.credit(user_id, remaining_win, f"{game_type}_win")
        
        final_win_amount = total_win
        
        # Обновляем рейтинги
        await RatingService.update_user_rating(user_id, stake_cents, final_win_amount, 'daily')
        await RatingService.update_user_rating(user_id, stake_cents, final_win_amount, 'weekly')
        await RatingService.update_user_rating(user_id, stake_cents, final_win_amount, 'monthly')
        
    else:
        # Проигрыш - применяем VIP возврат
        cashback_amount, vip_message = await VIPService.apply_vip_cashback(user_id, stake_cents)
        final_win_amount = 0
    
    return final_win_amount, vip_message, credit_message


# --- ОБРАБОТЧИКИ КОМАНД С ПАРАМЕТРАМИ ---

@router.message(lambda message: message.text and message.text.startswith('/dice '))
async def cmd_dice_with_stake(message: Message, state: FSMContext):
    """Обрабатывает команду /dice с параметром ставки"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Извлекаем сумму из команды
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>/dice 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='dice',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Бот бросает
        bot_dice = await message.answer_dice(emoji='🎲')
        await asyncio.sleep(1)

        # Игрок бросает
        await message.answer("Твоя очередь бросать! 🎲")
        player_dice = await message.answer_dice(emoji='🎲')

        # Ждём анимацию
        await asyncio.sleep(4)

        bot_value = bot_dice.dice.value
        player_value = player_dice.dice.value
        
        # Проверяем подкрутку и открутку для игрока
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - игрок всегда выигрывает
            # Если игрок проигрывает, меняем его значение на выигрышное
            if player_value <= bot_value:
                player_value = bot_value + 1
                if player_value > 6:  # Максимум 6 на кости
                    player_value = 6
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - игрок всегда проигрывает
            # Если игрок выигрывает, меняем его значение на проигрышное
            if player_value > bot_value:
                player_value = bot_value - 1
                if player_value < 1:  # Минимум 1 на кости
                    player_value = 1

        payout = DiceGame.calculate_payout(player_value, bot_value, stake_cents)


        


        result_str = f"bot:{bot_value},player:{player_value}"


        await bet_service.complete_bet(bet.id, result_str, payout)


        


        # Применяем VIP бонусы и обрабатываем результат


        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'dice')


        


        new_balance = await wallet_service.get_balance(user.id)

        if player_value > bot_value:
            text = await PersonalityEngine.get_message('dice_win', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"💰 Выигрыш: <b>${format_money(final_payout)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        elif player_value == bot_value:
            text = f"🤝 <b>НИЧЬЯ!</b>\n\n"
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"↩️ Ставка возвращена: <b>${format_money(final_payout)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            text = await PersonalityEngine.get_message('dice_loss', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"


        await message.answer(text)


@router.message(lambda message: message.text and message.text.startswith('/slots '))
async def cmd_slots_with_stake(message: Message):
    """Обрабатывает команду /slots с параметром ставки"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Извлекаем сумму из команды
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>/slots 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='slots',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Анимация
        animation_msg = await message.answer("🎰 Крутим барабаны... 🤞")
        await asyncio.sleep(2)

        # Генерация результата
        server_seed = secrets.token_hex(32)
        client_seed = str(user.telegram_id)
        nonce = user.slots_nonce

        symbols = SlotMachine.spin(server_seed, client_seed, nonce)
        
        # Проверяем подкрутку и открутку
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - всегда выигрыш
            # Генерируем выигрышную комбинацию
            symbols = ['🍎', '🍎', '🍎']  # Три одинаковых символа = выигрыш
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - всегда проигрыш
            # Генерируем проигрышную комбинацию
            symbols = ['🍎', '🍊', '🍇']  # Разные символы = проигрыш
        
        payout = SlotMachine.calculate_payout(symbols, stake_cents)

        user.slots_nonce += 1
        await session.commit()

        await bet_service.complete_bet(bet.id, ''.join(symbols), payout)

        # Применяем VIP бонусы и обрабатываем результат
        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'slots')

        await animation_msg.delete()

        symbols_str = ' '.join(symbols)
        new_balance = await wallet_service.get_balance(user.id)

        if payout >= stake_cents * 100:
            text = await PersonalityEngine.get_message('jackpot', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"🤑 ТЫ СОРВАЛ КУШ: <b>${format_money(payout)}</b>!\n\n"
            text += f"Это в {format_number(payout // stake_cents)} раз больше ставки! 👑\n\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Новый баланс: <b>${format_money(new_balance)}</b>"
            
        elif payout > stake_cents:
            multiplier = payout / stake_cents
            text = await PersonalityEngine.get_message('big_win', user, {'multiplier': multiplier})
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"💰 Ты выиграл <b>${format_money(payout)}</b> (x{multiplier:.1f})!\n\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Новый баланс: <b>${format_money(new_balance)}</b>"
            
        elif payout > 0:
            text = await PersonalityEngine.get_message('slots_partial_win', user, {'payout': format_money(payout)})
            if 'slots_partial_win' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                text = f"😊 <b>Почти!</b>\n\n"
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"🎰 {symbols_str}\n\n"
                text += f"💰 Возврат: <b>${format_money(payout)}</b>\n\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            else:
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"\n\n🎰 {symbols_str}\n\n"
                text += f"💰 Возврат: <b>${format_money(payout)}</b>\n\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            text = await PersonalityEngine.get_message('slots_loss', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>\n\n"
            text += f"🍀 Попробуй ещё раз!"

        await message.answer(text)


@router.message(lambda message: message.text and message.text.startswith('/roulette '))
async def cmd_roulette_with_stake(message: Message):
    """Обрабатывает команду /roulette с параметрами ставки и цвета/числа"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Извлекаем параметры из команды
        parts = message.text.split(' ')
        if len(parts) < 3:
            await message.answer("❌ Неверный формат! Используйте: <code>/roulette 20 red</code> или <code>/roulette 20 к</code> или <code>/roulette 20 5</code>")
            return
        
        stake_text = parts[1].strip()
        bet_on = parts[2].strip().lower()
        
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>/roulette 20 red</code> или <code>/roulette 20 к</code> или <code>/roulette 20 5</code>")
        return

    # Валидация выбора (цвет или число)
    if bet_on.isdigit():
        bet_type = 'number'
        bet_value = int(bet_on)
        if not 1 <= bet_value <= 10:
            await message.answer("❌ Неверное число! Укажи от 1 до 10.")
            return
    elif bet_on in ['red', 'красное', 'r', 'к', 'крас']:
        bet_type = 'red'
        bet_value = RouletteGame.RED_NUMBERS
    elif bet_on in ['black', 'чёрное', 'b', 'ч', 'черное']:
        bet_type = 'black'
        bet_value = RouletteGame.BLACK_NUMBERS
    else:
        await message.answer("❌ Неверная ставка! Используй: число (1-10), red, black, к (красное), ч (черное)")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='roulette',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Анимация
        try:
            animation_msg = await message.answer("🎰 Рулетка крутится... 🌀")
        except Exception:
            # Если не удалось отправить анимацию из-за flood control, продолжаем без неё
            animation_msg = None
        await asyncio.sleep(2.5)

        # Результат (случайное число от 1 до 10)
        # Проверяем подкрутку и открутку
        is_rigged = await is_user_rigged(message.from_user.id)
        is_unrigged = await is_user_unrigged(message.from_user.id)
        
        print(f"DEBUG: User {message.from_user.id}, bet_type: {bet_type}, is_rigged: {is_rigged}, is_unrigged: {is_unrigged}")
        
        if is_rigged:
            # Подкрутка активна - всегда выигрыш
            if bet_type == "red":
                result_number = random.choice([1, 3, 5, 7, 9])  # Красные числа
            elif bet_type == "black":
                result_number = random.choice([2, 4, 6, 8, 10])  # Черные числа
            elif bet_type == "number":
                result_number = bet_value  # Точно выбранное число
            elif bet_type == "even":
                result_number = random.choice([2, 4, 6, 8, 10])  # Четные числа
            elif bet_type == "odd":
                result_number = random.choice([1, 3, 5, 7, 9])  # Нечетные числа
            elif bet_type == "high":
                result_number = random.choice([6, 7, 8, 9, 10])  # Высокие числа
            elif bet_type == "low":
                result_number = random.choice([1, 2, 3, 4, 5])  # Низкие числа
            else:
                # Для любых других ставок - выбираем выигрышное число
                result_number = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        elif is_unrigged:
            # Открутка активна - всегда проигрыш
            if bet_type == "red":
                result_number = random.choice([2, 4, 6, 8, 10])  # Черные числа
            elif bet_type == "black":
                result_number = random.choice([1, 3, 5, 7, 9])  # Красные числа
            elif bet_type == "number":
                result_number = random.choice([x for x in range(1, 11) if x != bet_value])  # Любое другое число
            elif bet_type == "even":
                result_number = random.choice([1, 3, 5, 7, 9])  # Нечетные числа
            elif bet_type == "odd":
                result_number = random.choice([2, 4, 6, 8, 10])  # Четные числа
            elif bet_type == "high":
                result_number = random.choice([1, 2, 3, 4, 5])  # Низкие числа
            elif bet_type == "low":
                result_number = random.choice([6, 7, 8, 9, 10])  # Высокие числа
            else:
                # Для любых других ставок - выбираем проигрышное число
                result_number = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        else:
            result_number = RouletteGame.spin()
        
        print(f"DEBUG: Final result_number: {result_number}")
        
        result_color = RouletteGame.get_color(result_number)

        # Рассчитываем выплату на основе выбора игрока
        payout = RouletteGame.calculate_payout(bet_type, bet_value, result_number, stake_cents)

        result_str = f"number:{result_number},color:{result_color}"
        await bet_service.complete_bet(bet.id, result_str, payout)

        # Применяем VIP бонусы и обрабатываем результат
        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'roulette')

        await animation_msg.delete()

        color_emoji = '🔴' if result_color == 'red' else '⚫'
        new_balance = await wallet_service.get_balance(user.id)

        if final_payout > 0:
            multiplier = final_payout / stake_cents
            text = await PersonalityEngine.get_message('big_win', user, {'multiplier': multiplier})
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
            text += f"💰 Выигрыш: <b>${format_money(final_payout)}</b> (x{multiplier:.1f})\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            text = await PersonalityEngine.get_message('roulette_loss', user)
            if 'roulette_loss' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                text = f"💔 <b>Не угадал...</b>\n\n"
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
                text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            
            else:
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"\n\n🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
                text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"

        await message.answer(text)


# --- РУССКИЕ КОМАНДЫ С ПАРАМЕТРАМИ ---

# /рулетка - вызываем текстовый обработчик без слэша
@router.message(lambda message: message.text and message.text.startswith('/рулетка '))
async def cmd_roulette_ru_with_stake(message: Message):
    """Обрабатывает русскую команду /рулетка с параметрами"""
    # Убираем слэш и вызываем текстовый обработчик
    text_without_slash = message.text[1:]  # Убираем первый символ (/)
    # Создаем временный объект для передачи в обработчик
    import types
    temp_msg = types.SimpleNamespace()
    temp_msg.text = text_without_slash
    temp_msg.from_user = message.from_user
    temp_msg.chat = message.chat
    temp_msg.answer = message.answer
    temp_msg.answer_dice = message.answer_dice
    await text_roulette_with_params(temp_msg)

# /слоты - вызываем текстовый обработчик без слэша
@router.message(lambda message: message.text and message.text.startswith('/слоты '))
async def cmd_slots_ru_with_stake(message: Message):
    """Обрабатывает русскую команду /слоты с параметром ставки"""
    text_without_slash = message.text[1:]
    import types
    temp_msg = types.SimpleNamespace()
    temp_msg.text = text_without_slash
    temp_msg.from_user = message.from_user
    temp_msg.chat = message.chat
    temp_msg.answer = message.answer
    await text_slots_with_params(temp_msg)

# /кости - вызываем текстовый обработчик без слэша
@router.message(lambda message: message.text and message.text.startswith('/кости '))
async def cmd_dice_ru_with_stake(message: Message, state: FSMContext):
    """Обрабатывает русскую команду /кости с параметром ставки"""
    text_without_slash = message.text[1:]
    import types
    temp_msg = types.SimpleNamespace()
    temp_msg.text = text_without_slash
    temp_msg.from_user = message.from_user
    temp_msg.chat = message.chat
    temp_msg.answer = message.answer
    temp_msg.answer_dice = message.answer_dice
    await text_dice_with_params(temp_msg, state)

# /мины - вызываем текстовый обработчик без слэша
@router.message(lambda message: message.text and message.text.startswith('/мины '))
async def cmd_mines_ru_with_stake(message: Message, state: FSMContext):
    """Обрабатывает русскую команду /мины с параметром ставки"""
    text_without_slash = message.text[1:]
    import types
    temp_msg = types.SimpleNamespace()
    temp_msg.text = text_without_slash
    temp_msg.from_user = message.from_user
    temp_msg.chat = message.chat
    temp_msg.answer = message.answer
    await text_mines_with_params(temp_msg, state)


# --- ТЕКСТОВЫЕ КОМАНДЫ БЕЗ СЛЭША (для групп и ЛС) ---

# рулетка [ставка] [цвет/число]
@router.message(lambda message: message.text and message.text.lower().startswith('рулетка '))
async def text_roulette_with_params(message: Message):
    """Обрабатывает текстовую команду 'рулетка [ставка] [цвет/число]' без слэша"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Парсим параметры напрямую
        parts = message.text.split(' ')
        if len(parts) < 3:
            await message.answer("❌ Неверный формат! Используйте: <code>рулетка 20 red</code> или <code>рулетка 20 к</code> или <code>рулетка 20 5</code>")
            return
        
        stake_text = parts[1].strip()
        bet_on = parts[2].strip().lower()
        
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>рулетка 20 red</code> или <code>рулетка 20 к</code> или <code>рулетка 20 5</code>")
        return

    # Валидация выбора (цвет или число)
    if bet_on.isdigit():
        bet_type = 'number'
        bet_value = int(bet_on)
        if not 1 <= bet_value <= 10:
            await message.answer("❌ Неверное число! Укажи от 1 до 10.")
            return
    elif bet_on in ['red', 'красное', 'r', 'к', 'крас']:
        bet_type = 'red'
        bet_value = RouletteGame.RED_NUMBERS
    elif bet_on in ['black', 'чёрное', 'b', 'ч', 'черное']:
        bet_type = 'black'
        bet_value = RouletteGame.BLACK_NUMBERS
    else:
        await message.answer("❌ Неверная ставка! Используй: число (1-10), red, black, к (красное), ч (черное)")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='roulette',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Анимация
        try:
            animation_msg = await message.answer("🎰 Рулетка крутится... 🌀")
        except Exception:
            # Если не удалось отправить анимацию из-за flood control, продолжаем без неё
            animation_msg = None
        await asyncio.sleep(2.5)

        # Результат (случайное число от 1 до 10)
        # Проверяем подкрутку и открутку
        is_rigged = await is_user_rigged(message.from_user.id)
        is_unrigged = await is_user_unrigged(message.from_user.id)
        
        print(f"DEBUG: User {message.from_user.id}, bet_type: {bet_type}, is_rigged: {is_rigged}, is_unrigged: {is_unrigged}")
        
        if is_rigged:
            # Подкрутка активна - всегда выигрыш
            if bet_type == "red":
                result_number = random.choice([1, 3, 5, 7, 9])  # Красные числа
            elif bet_type == "black":
                result_number = random.choice([2, 4, 6, 8, 10])  # Черные числа
            elif bet_type == "number":
                result_number = bet_value  # Точно выбранное число
            elif bet_type == "even":
                result_number = random.choice([2, 4, 6, 8, 10])  # Четные числа
            elif bet_type == "odd":
                result_number = random.choice([1, 3, 5, 7, 9])  # Нечетные числа
            elif bet_type == "high":
                result_number = random.choice([6, 7, 8, 9, 10])  # Высокие числа
            elif bet_type == "low":
                result_number = random.choice([1, 2, 3, 4, 5])  # Низкие числа
            else:
                # Для любых других ставок - выбираем выигрышное число
                result_number = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        elif is_unrigged:
            # Открутка активна - всегда проигрыш
            if bet_type == "red":
                result_number = random.choice([2, 4, 6, 8, 10])  # Черные числа
            elif bet_type == "black":
                result_number = random.choice([1, 3, 5, 7, 9])  # Красные числа
            elif bet_type == "number":
                result_number = random.choice([x for x in range(1, 11) if x != bet_value])  # Любое другое число
            elif bet_type == "even":
                result_number = random.choice([1, 3, 5, 7, 9])  # Нечетные числа
            elif bet_type == "odd":
                result_number = random.choice([2, 4, 6, 8, 10])  # Четные числа
            elif bet_type == "high":
                result_number = random.choice([1, 2, 3, 4, 5])  # Низкие числа
            elif bet_type == "low":
                result_number = random.choice([6, 7, 8, 9, 10])  # Высокие числа
            else:
                # Для любых других ставок - выбираем проигрышное число
                result_number = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        else:
            result_number = RouletteGame.spin()
        
        print(f"DEBUG: Final result_number: {result_number}")
        
        result_color = RouletteGame.get_color(result_number)

        # Рассчитываем выплату на основе выбора игрока
        payout = RouletteGame.calculate_payout(bet_type, bet_value, result_number, stake_cents)

        result_str = f"number:{result_number},color:{result_color}"
        await bet_service.complete_bet(bet.id, result_str, payout)

        # Применяем VIP бонусы и обрабатываем результат
        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'roulette')

        await animation_msg.delete()

        color_emoji = '🔴' if result_color == 'red' else '⚫'
        new_balance = await wallet_service.get_balance(user.id)

        if final_payout > 0:
            multiplier = final_payout / stake_cents
            text = await PersonalityEngine.get_message('big_win', user, {'multiplier': multiplier})
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
            text += f"💰 Выигрыш: <b>${format_money(final_payout)}</b> (x{multiplier:.1f})\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            text = await PersonalityEngine.get_message('roulette_loss', user)
            if 'roulette_loss' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                text = f"💔 <b>Не угадал...</b>\n\n"
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
                text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            
            else:
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"\n\n🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
                text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"

        await message.answer(text)

# слоты [ставка]
@router.message(lambda message: message.text and message.text.lower().startswith('слоты '))
async def text_slots_with_params(message: Message):
    """Обрабатывает текстовую команду 'слоты [ставка]' без слэша"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Парсим параметры напрямую
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>слоты 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='slots',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Анимация
        animation_msg = await message.answer("🎰 Крутим барабаны... 🤞")
        await asyncio.sleep(2)

        # Генерация результата
        server_seed = secrets.token_hex(32)
        client_seed = str(user.telegram_id)
        nonce = user.slots_nonce

        symbols = SlotMachine.spin(server_seed, client_seed, nonce)
        
        # Проверяем подкрутку и открутку
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - всегда выигрыш
            # Генерируем выигрышную комбинацию
            symbols = ['🍎', '🍎', '🍎']  # Три одинаковых символа = выигрыш
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - всегда проигрыш
            # Генерируем проигрышную комбинацию
            symbols = ['🍎', '🍊', '🍇']  # Разные символы = проигрыш
        
        payout = SlotMachine.calculate_payout(symbols, stake_cents)

        user.slots_nonce += 1
        await session.commit()

        await bet_service.complete_bet(bet.id, ''.join(symbols), payout)

        # Применяем VIP бонусы и обрабатываем результат
        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'slots')

        await animation_msg.delete()

        symbols_str = ' '.join(symbols)
        new_balance = await wallet_service.get_balance(user.id)

        if payout >= stake_cents * 100:
            text = await PersonalityEngine.get_message('jackpot', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"🤑 ТЫ СОРВАЛ КУШ: <b>${format_money(payout)}</b>!\n\n"
            text += f"Это в {format_number(payout // stake_cents)} раз больше ставки! 👑\n\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Новый баланс: <b>${format_money(new_balance)}</b>"
            
        elif payout > stake_cents:
            multiplier = payout / stake_cents
            text = await PersonalityEngine.get_message('big_win', user, {'multiplier': multiplier})
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"💰 Ты выиграл <b>${format_money(payout)}</b> (x{multiplier:.1f})!\n\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Новый баланс: <b>${format_money(new_balance)}</b>"
            
        elif payout > 0:
            text = await PersonalityEngine.get_message('slots_partial_win', user, {'payout': format_money(payout)})
            if 'slots_partial_win' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                text = f"😊 <b>Почти!</b>\n\n"
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"🎰 {symbols_str}\n\n"
                text += f"💰 Возврат: <b>${format_money(payout)}</b>\n\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            else:
                # Добавляем упоминание пользователя в группах
                if message.chat.type in ['group', 'supergroup']:
                    text = f"@{message.from_user.username or message.from_user.first_name}, " + text
                text += f"\n\n🎰 {symbols_str}\n\n"
                text += f"💰 Возврат: <b>${format_money(payout)}</b>\n\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            text = await PersonalityEngine.get_message('slots_loss', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>\n\n"
            text += f"🍀 Попробуй ещё раз!"

        await message.answer(text)

# кости [ставка]
@router.message(lambda message: message.text and message.text.lower().startswith('кости '))
async def text_dice_with_params(message: Message, state: FSMContext):
    """Обрабатывает текстовую команду 'кости [ставка]' без слэша"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Парсим параметры напрямую
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>кости 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='dice',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Бот бросает
        bot_dice = await message.answer_dice(emoji='🎲')
        await asyncio.sleep(1)

        # Игрок бросает
        await message.answer("Твоя очередь бросать! 🎲")
        player_dice = await message.answer_dice(emoji='🎲')

        # Ждём анимацию
        await asyncio.sleep(4)

        bot_value = bot_dice.dice.value
        player_value = player_dice.dice.value
        
        # Проверяем подкрутку и открутку для игрока
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - игрок всегда выигрывает
            # Если игрок проигрывает, меняем его значение на выигрышное
            if player_value <= bot_value:
                player_value = bot_value + 1
                if player_value > 6:  # Максимум 6 на кости
                    player_value = 6
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - игрок всегда проигрывает
            # Если игрок выигрывает, меняем его значение на проигрышное
            if player_value > bot_value:
                player_value = bot_value - 1
                if player_value < 1:  # Минимум 1 на кости
                    player_value = 1

        payout = DiceGame.calculate_payout(player_value, bot_value, stake_cents)


        


        result_str = f"bot:{bot_value},player:{player_value}"


        await bet_service.complete_bet(bet.id, result_str, payout)


        


        # Применяем VIP бонусы и обрабатываем результат


        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'dice')


        


        new_balance = await wallet_service.get_balance(user.id)

        if player_value > bot_value:
            text = await PersonalityEngine.get_message('dice_win', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"💰 Выигрыш: <b>${format_money(final_payout)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        elif player_value == bot_value:
            text = f"🤝 <b>НИЧЬЯ!</b>\n\n"
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"↩️ Ставка возвращена: <b>${format_money(final_payout)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            if credit_message:
                text += f"{credit_message}\n"
        else:
            text = await PersonalityEngine.get_message('dice_loss', user)
            # Добавляем упоминание пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                text = f"@{message.from_user.username or message.from_user.first_name}, " + text
            text += f"\n\n🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"

        await message.answer(text)

# мины [ставка]
@router.message(lambda message: message.text and message.text.lower().startswith('мины '))
async def text_mines_with_params(message: Message, state: FSMContext):
    """Обрабатывает текстовую команду 'мины [ставка]' без слэша"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Парсим параметры напрямую
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>мины 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='mines',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Генерируем мины
        mines_nonce = getattr(user, 'mines_nonce', 0)
        mines = MinesGame.generate_mines(user.id, mines_nonce)
        
        # Проверяем подкрутку и открутку
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - убираем все мины (игрок всегда выигрывает)
            mines = []
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - добавляем мины во все клетки (игрок всегда проигрывает)
            mines = list(range(25))  # Все 25 клеток - мины
        
        if hasattr(user, 'mines_nonce'):
            user.mines_nonce += 1
        await session.commit()

        # Создаем клавиатуру 5x5
        keyboard = create_mines_keyboard()

        # Сохраняем данные игры в состоянии
        await state.update_data(
            bet_id=bet.id,
            stake_cents=stake_cents,
            mines=mines,
            opened_cells=[],
            moves_count=0,
            user_id=user.id
        )
        await state.set_state(MinesStates.playing)

        # Отправляем сообщение с игрой
        if message.chat.type in ['group', 'supergroup']:
            username = message.from_user.username or message.from_user.first_name
            text = f"@{username}, вы начали игру минное поле!\n\n"
        else:
            text = f"💣 <b>Мины</b>\n\n"
        text += f"💰 Ставка: ${format_money(stake_cents)}\n\n"
        text += "Выберите клетку для открытия:"

        await message.answer(text, reply_markup=keyboard)


# --- ОБРАБОТЧИК ЧИСЛОВЫХ СООБЩЕНИЙ ДЛЯ ГРУПП ---
@router.message(lambda message: message.text and message.text.replace('.', '').replace(',', '').isdigit())
async def handle_numeric_messages(message: Message, state: FSMContext):
    """Обрабатывает числовые сообщения в группах для игр"""
    # Отладочная информация
    current_state = await state.get_state()
    print(f"DEBUG: Numeric message '{message.text}' from user {message.from_user.id} in chat {message.chat.id}")
    print(f"DEBUG: Current FSM state: {current_state}")
    
    # Если пользователь в состоянии админ-панели - пропускаем, чтобы обработчики админки сработали
    if current_state and current_state.startswith('AdminStates:'):
        print(f"DEBUG: User in admin state, skipping numeric handler")
        return
    
    # Проверяем, есть ли у пользователя активное состояние FSM
    if current_state == DiceStates.choosing_stake:
        print(f"DEBUG: Processing dice stake for user {message.from_user.id}")
        # Если пользователь в состоянии выбора ставки для костей
        await process_dice_stake(message, state)
    elif current_state == SlotsStates.choosing_stake:
        print(f"DEBUG: Processing slots stake for user {message.from_user.id}")
        # Если пользователь в состоянии выбора ставки для слотов
        await process_slots_stake(message, state)
    elif current_state == RouletteStates.choosing_stake:
        print(f"DEBUG: Processing roulette stake for user {message.from_user.id}")
        # Если пользователь в состоянии выбора ставки для рулетки
        await process_roulette_stake(message, state)
    elif current_state == RouletteStates.choosing_bet:
        print(f"DEBUG: Processing roulette bet for user {message.from_user.id}")
        # Если пользователь в состоянии выбора ставки в рулетке
        await process_roulette_choice(message, state)
    elif current_state == MinesStates.choosing_stake:
        print(f"DEBUG: Processing mines stake for user {message.from_user.id}")
        # Если пользователь в состоянии выбора ставки для мины
        await process_mines_stake(message, state)
    elif current_state == RocketStates.choosing_stake:
        # Если пользователь в состоянии выбора ставки для ракетки
        await process_rocket_stake(message, state)
    else:
        print(f"DEBUG: No active FSM state for user {message.from_user.id}, ignoring message")


# --- /slots (и 🎰 Слоты как текстовый триггер) ---

@router.message(Command('slots'))
async def cmd_slots(message: Message, state: FSMContext):
    """Запрашивает ставку для слотов через команду /slots"""
    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = message.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    # Проверяем тип чата
    if message.chat.type in ['group', 'supergroup']:
        # В группах - показываем инструкцию по использованию команды с параметрами
        await message.answer(
            "🎰 <b>Слоты</b>\n\n"
            "Используйте команду с суммой ставки:\n"
            "<code>/slots 10</code> или <code>/слоты 10</code> - ставка $10\n"
            "<code>/slots 25</code> или <code>/слоты 25</code> - ставка $25\n"
            "<code>/slots 50</code> или <code>/слоты 50</code> - ставка $50\n\n"
            "Минимальная ставка: $1\n"
            "Максимальная ставка: $1000"
        )
    else:
        # В ЛС - интерактивный режим (как было)
        await state.clear()
        await message.answer("🎰 <b>Слоты</b>\nВведите сумму ставки (например, 10):")
        await state.set_state(SlotsStates.choosing_stake)

# ТЕКСТОВЫЙ ТРИГГЕР для слотов - игнорируется в группах
@router.message(lambda message: message.text == '🎰 Слоты')
async def trigger_slots(message: Message, state: FSMContext):
    """Обрабатывает текстовый триггер '🎰 Слоты'"""
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
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    await state.clear()
    await message.answer("🎰 <b>Слоты</b>\nВведите сумму ставки (например, 10):")
    await state.set_state(SlotsStates.choosing_stake)


# --- /dice (и 🎲 Кости как текстовый триггер) ---

@router.message(Command('dice'))
async def cmd_dice(message: Message, state: FSMContext):
    """Запрашивает ставку для костей через команду /dice"""
    print(f"DEBUG: cmd_dice called for user {message.from_user.id} in chat {message.chat.id}")
    
    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = message.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    # Проверяем тип чата
    if message.chat.type in ['group', 'supergroup']:
        # В группах - показываем инструкцию по использованию команды с параметрами
        await message.answer(
            "🎲 <b>Дуэль на костях</b>\n\n"
            "Используйте команду с суммой ставки:\n"
            "<code>/dice 20</code> или <code>/кости 20</code> - ставка $20\n"
            "<code>/dice 50</code> или <code>/кости 50</code> - ставка $50\n"
            "<code>/dice 100</code> или <code>/кости 100</code> - ставка $100\n\n"
            "Минимальная ставка: $1\n"
            "Максимальная ставка: $1000"
        )
    else:
        # В ЛС - интерактивный режим (как было)
        await state.clear()
        print(f"DEBUG: Setting DiceStates.choosing_stake for user {message.from_user.id} in chat {message.chat.id}")
        await message.answer("🎲 <b>Дуэль на костях</b>\nВведите сумму ставки (например, 20):")
        await state.set_state(DiceStates.choosing_stake)

# ТЕКСТОВЫЙ ТРИГГЕР для костей - игнорируется в группах
@router.message(lambda message: message.text == '🎲 Кости')
async def trigger_dice(message: Message, state: FSMContext):
    """Обрабатывает текстовый триггер '🎲 Кости'"""
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
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    await state.clear()
    await message.answer("🎲 <b>Дуэль на костях</b>\nВведите сумму ставки (например, 20):")
    await state.set_state(DiceStates.choosing_stake)


# --- /roulette (и ♠️ Рулетка как текстовый триггер) ---

@router.message(Command('roulette'))
async def cmd_roulette(message: Message, state: FSMContext):
    """Запрашивает ставку для рулетки через команду /roulette"""
    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = message.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    # Проверяем тип чата
    if message.chat.type in ['group', 'supergroup']:
        # В группах - показываем инструкцию по использованию команды с параметрами
        await message.answer(
            "♠️ <b>Мини-рулетка</b>\n\n"
            "Используйте команду:\n"
            "<code>/roulette [ставка] [цвет/число]</code>\n\n"
            "Примеры:\n"
            "├ <code>/roulette 20 red</code> или <code>/рулетка 20 к</code>\n"
            "├ <code>/roulette 50 black</code> или <code>/рулетка 50 ч</code>\n"
            "└ <code>/roulette 100 5</code> - ставка на число\n\n"
            "🔴 Красное (red, к): x1.8\n"
            "⚫ Черное (black, ч): x1.8\n"
            "🎯 Число (1-10): x3\n\n"
            "Минимальная ставка: $1\n"
            "Максимальная ставка: $1000"
        )
    else:
        # В ЛС - интерактивный режим (как было)
        await state.clear()
        await message.answer("♠️ <b>Мини-рулетка</b>\nВведите сумму ставки (например, 20):")
        await state.set_state(RouletteStates.choosing_stake)

# ТЕКСТОВЫЙ ТРИГГЕР для рулетки - игнорируется в группах
@router.message(lambda message: message.text == '♠️ Рулетка')
async def trigger_roulette(message: Message, state: FSMContext):
    """Обрабатывает текстовый триггер '♠️ Рулетка'"""
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
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            return

    await state.clear()
    await message.answer("♠️ <b>Мини-рулетка</b>\nВведите сумму ставки (например, 20):")
    await state.set_state(RouletteStates.choosing_stake)


# --- РУССКИЕ КОМАНДЫ ДЛЯ ЛИЧНЫХ СООБЩЕНИЙ ---

@router.message(Command('слоты'))
async def cmd_slots_ru(message: Message, state: FSMContext):
    """Русская команда /слоты для ЛС"""
    await cmd_slots(message, state)

@router.message(Command('кости'))
async def cmd_dice_ru(message: Message, state: FSMContext):
    """Русская команда /кости для ЛС"""
    await cmd_dice(message, state)

@router.message(Command('рулетка'))
async def cmd_roulette_ru(message: Message, state: FSMContext):
    """Русская команда /рулетка для ЛС"""
    await cmd_roulette(message, state)


# --- FSM обработчики ---
# Эти обработчики НЕ должны срабатывать в группах, так как они зависят от состояния пользователя.
# Добавим проверку в начало каждого FSM-обработчика для надёжности, даже если основной запуск FSM заблокирован.
# Проверка в FSM-обработчиках - дополнительная мера.

@router.message(SlotsStates.choosing_stake)
async def process_slots_stake(message: Message, state: FSMContext):
    """Обрабатывает ввод ставки для слотов и запускает игру"""
    # Отладочная информация
    print(f"DEBUG: process_slots_stake called for user {message.from_user.id} in chat {message.chat.id}")
    print(f"DEBUG: Current state: {await state.get_state()}")
    
    # Продолжаем основную логику FSM
    try:
        stake_dollars = float(message.text)
        stake_cents = int(stake_dollars * 100)
    except ValueError:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('invalid_stake', user)
                # Если персональность не определена, используем стандартное сообщение
                if 'invalid_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = "❌ Неверная сумма! Введите число."
            else:
                text = "❌ Неверная сумма! Введите число."
        await message.answer(text)
        return

    if stake_cents < settings.MIN_BET:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('low_stake', user, {'min_bet': format_money(settings.MIN_BET)})
                # Если персональность не определена, используем стандартное сообщение
                if 'low_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}"
            else:
                text = f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}"
        await message.answer(text)
        return

    if stake_cents > settings.MAX_BET:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('high_stake', user, {'max_bet': format_money(settings.MAX_BET)})
                # Если персональность не определена, используем стандартное сообщение
                if 'high_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}"
            else:
                text = f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}"
        await message.answer(text)
        return

    telegram_id = message.from_user.id
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            await state.clear()
            return

        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            await state.clear()
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='slots',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            await state.clear()
            return

        # Анимация
        animation_msg = await message.answer("🎰 Крутим барабаны... 🤞")
        await asyncio.sleep(2)

        # Генерация результата
        server_seed = secrets.token_hex(32)
        client_seed = str(user.telegram_id)
        nonce = user.slots_nonce

        symbols = SlotMachine.spin(server_seed, client_seed, nonce)
        
        # Проверяем подкрутку и открутку
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - всегда выигрыш
            # Генерируем выигрышную комбинацию
            symbols = ['🍎', '🍎', '🍎']  # Три одинаковых символа = выигрыш
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - всегда проигрыш
            # Генерируем проигрышную комбинацию
            symbols = ['🍎', '🍊', '🍇']  # Разные символы = проигрыш
        
        payout = SlotMachine.calculate_payout(symbols, stake_cents)

        user.slots_nonce += 1
        await session.commit()

        await bet_service.complete_bet(bet.id, ''.join(symbols), payout)

        # Применяем VIP бонусы и обрабатываем результат
        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'slots')

        await animation_msg.delete()

        symbols_str = ' '.join(symbols)
        new_balance = await wallet_service.get_balance(user.id)

        if payout >= stake_cents * 100:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('jackpot', user)
            # Добавляем детали к сообщению персональности
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"🤑 ТЫ СОРВАЛ КУШ: <b>${format_money(payout)}</b>!\n\n"
            text += f"Это в {format_number(payout // stake_cents)} раз больше ставки! 👑\n\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Новый баланс: <b>${format_money(new_balance)}</b>"
            
        elif payout > stake_cents:
            multiplier = payout / stake_cents
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('big_win', user, {'multiplier': multiplier})
            # Добавляем детали
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"💰 Ты выиграл <b>${format_money(payout)}</b> (x{multiplier:.1f})!\n\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Новый баланс: <b>${format_money(new_balance)}</b>"
            
        elif payout > 0:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('slots_partial_win', user, {'payout': format_money(payout)})
            # Если не определено, используем стандартное
            if 'slots_partial_win' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                text = f"😊 <b>Почти!</b>\n\n"
                text += f"🎰 {symbols_str}\n\n"
                text += f"💰 Возврат: <b>${format_money(payout)}</b>\n\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            else:
                # Добавляем детали к сообщению персональности
                text += f"\n\n🎰 {symbols_str}\n\n"
                text += f"💰 Возврат: <b>${format_money(payout)}</b>\n\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('slots_loss', user)
            # Добавляем детали
            text += f"\n\n🎰 {symbols_str}\n\n"
            text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>\n\n"
            text += f"🍀 Попробуй ещё раз!"

        await message.answer(text)
        await state.clear()


# --- FSM для Dice ---
@router.message(DiceStates.choosing_stake)
async def process_dice_stake(message: Message, state: FSMContext):
    """Обрабатывает ввод ставки для костей и запускает игру"""
    # Отладочная информация
    print(f"DEBUG: process_dice_stake called for user {message.from_user.id} in chat {message.chat.id}")
    print(f"DEBUG: Current state: {await state.get_state()}")
    
    # Продолжаем основную логику FSM
    try:
        stake_dollars = float(message.text)
        stake_cents = int(stake_dollars * 100)
    except ValueError:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('invalid_stake', user)
                if 'invalid_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = "❌ Неверная сумма! Введите число."
            else:
                text = "❌ Неверная сумма! Введите число."
        await message.answer(text)
        return

    if stake_cents < settings.MIN_BET:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('low_stake', user, {'min_bet': format_money(settings.MIN_BET)})
                if 'low_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}"
            else:
                text = f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}"
        await message.answer(text)
        return

    if stake_cents > settings.MAX_BET:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('high_stake', user, {'max_bet': format_money(settings.MAX_BET)})
                if 'high_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}"
            else:
                text = f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}"
        await message.answer(text)
        return

    telegram_id = message.from_user.id
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            await state.clear()
            return

        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            await state.clear()
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='dice',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            await state.clear()
            return

        # Бот бросает
        bot_dice = await message.answer_dice(emoji='🎲')
        await asyncio.sleep(1)

        # Игрок бросает
        await message.answer("Твоя очередь бросать! 🎲")
        player_dice = await message.answer_dice(emoji='🎲')

        # Ждём анимацию
        await asyncio.sleep(4)

        bot_value = bot_dice.dice.value
        player_value = player_dice.dice.value
        
        # Проверяем подкрутку и открутку для игрока
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - игрок всегда выигрывает
            # Если игрок проигрывает, меняем его значение на выигрышное
            if player_value <= bot_value:
                player_value = bot_value + 1
                if player_value > 6:  # Максимум 6 на кости
                    player_value = 6
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - игрок всегда проигрывает
            # Если игрок выигрывает, меняем его значение на проигрышное
            if player_value > bot_value:
                player_value = bot_value - 1
                if player_value < 1:  # Минимум 1 на кости
                    player_value = 1

        payout = DiceGame.calculate_payout(player_value, bot_value, stake_cents)


        


        result_str = f"bot:{bot_value},player:{player_value}"


        await bet_service.complete_bet(bet.id, result_str, payout)


        


        # Применяем VIP бонусы и обрабатываем результат


        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'dice')


        


        new_balance = await wallet_service.get_balance(user.id)

        if player_value > bot_value:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('dice_win', user)
            # Добавляем детали
            text += f"\n\n🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"💰 Выигрыш: <b>${format_money(final_payout)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        elif player_value == bot_value:
            # НОВОЕ: Используем персональность (нейтральное сообщение, добавим его в NeutralPersonality)
            # Пока используем стандартное
            text = f"🤝 <b>НИЧЬЯ!</b>\n\n"
            text += f"🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"↩️ Ставка возвращена: <b>${format_money(final_payout)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            if credit_message:
                text += f"{credit_message}\n"
        else:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('dice_loss', user)
            # Добавляем детали
            text += f"\n\n🤖 Бот: {bot_value}\n"
            text += f"👤 Ты: {player_value}\n\n"
            text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"

        await message.answer(text)
        await state.clear()


# --- FSM для Roulette ---
@router.message(RouletteStates.choosing_stake)
async def process_roulette_stake(message: Message, state: FSMContext):
    """Обрабатывает ввод ставки для рулетки и запрашивает выбор (число/цвет)"""
    # Продолжаем основную логику FSM
    try:
        stake_dollars = float(message.text)
        stake_cents = int(stake_dollars * 100)
    except ValueError:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('invalid_stake', user)
                if 'invalid_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = "❌ Неверная сумма! Введите число."
            else:
                text = "❌ Неверная сумма! Введите число."
        await message.answer(text)
        return

    if stake_cents < settings.MIN_BET:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('low_stake', user, {'min_bet': format_money(settings.MIN_BET)})
                if 'low_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}"
            else:
                text = f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}"
        await message.answer(text)
        return

    if stake_cents > settings.MAX_BET:
        # НОВОЕ: Используем персональность
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if user:
                text = await PersonalityEngine.get_message('high_stake', user, {'max_bet': format_money(settings.MAX_BET)})
                if 'high_stake' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                    text = f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}"
            else:
                text = f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}"
        await message.answer(text)
        return

    telegram_id = message.from_user.id
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            await state.clear()
            return

        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            await state.clear()
            return

        # Сохраняем ставку в состоянии
        await state.update_data(stake_cents=stake_cents)
        await message.answer(
            "🎰 <b>Мини-рулетка</b>\n\n"
            "Теперь выберите:\n"
            "📍 Число (1-10): x3\n"
            "🔴 Красное (red, к, крас): x1.8\n"
            "⚫ Чёрное (black, ч, черное): x1.8\n\n"
            "Пример: <code>5</code> или <code>red</code> или <code>к</code>"
        )
        await state.set_state(RouletteStates.choosing_bet)

@router.message(RouletteStates.choosing_bet)
async def process_roulette_choice(message: Message, state: FSMContext):
    """Обрабатывает выбор (число/цвет) и запускает игру в рулетку"""
    # Продолжаем основную логику FSM
    bet_on = message.text.lower().strip()

    # Валидация выбора
    if bet_on.isdigit():
        bet_type = 'number'
        bet_value = int(bet_on)
        if not 1 <= bet_value <= 10:
            await message.answer("❌ Неверное число! Укажи от 1 до 10.")
            return
    elif bet_on in ['red', 'красное', 'r', 'к', 'крас']:
        bet_type = 'red'
        bet_value = RouletteGame.RED_NUMBERS
    elif bet_on in ['black', 'чёрное', 'b', 'ч', 'черное']:
        bet_type = 'black'
        bet_value = RouletteGame.BLACK_NUMBERS
    else:
        await message.answer("❌ Неверная ставка! Используй: число (1-10), red, black, к (красное), ч (черное)")
        return

    # Получаем сохранённую ставку из состояния
    data = await state.get_data()
    stake_cents = data.get('stake_cents')

    if stake_cents is None:
        await message.answer("❌ Ошибка получения ставки. Попробуйте снова.")
        await state.clear()
        return

    telegram_id = message.from_user.id
    from src.database import async_session_maker
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            await state.clear()
            return

        # Проверка баланса (повторно, на всякий случай)
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            # НОВОЕ: Используем персональность
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            await state.clear()
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='roulette',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            await state.clear()
            return

        # Анимация
        try:
            animation_msg = await message.answer("🎰 Рулетка крутится... 🌀")
        except Exception:
            # Если не удалось отправить анимацию из-за flood control, продолжаем без неё
            animation_msg = None
        await asyncio.sleep(2.5)

        # Результат
        result_number = RouletteGame.spin()
        result_color = RouletteGame.get_color(result_number)

        payout = RouletteGame.calculate_payout(bet_type, bet_value, result_number, stake_cents)

        result_str = f"number:{result_number},color:{result_color}"
        await bet_service.complete_bet(bet.id, result_str, payout)

        # Применяем VIP бонусы и обрабатываем результат
        final_payout, vip_message, credit_message = await process_game_result(user.id, stake_cents, payout, 'roulette')

        await animation_msg.delete()

        color_emoji = '🔴' if result_color == 'red' else '⚫'
        new_balance = await wallet_service.get_balance(user.id)

        if final_payout > 0:
            multiplier = final_payout / stake_cents
            # НОВОЕ: Используем персональность (например, win в рулетке)
            # Пока используем стандартное сообщение с персональностью big_win
            text = await PersonalityEngine.get_message('big_win', user, {'multiplier': multiplier})
            # Добавляем детали
            text += f"\n\n🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
            text += f"💰 Выигрыш: <b>${format_money(final_payout)}</b> (x{multiplier:.1f})\n"
            if vip_message:
                text += f"{vip_message}\n"
            if credit_message:
                text += f"{credit_message}\n"
            text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
        else:
            # НОВОЕ: Используем персональность (например, loss в рулетке)
            # Пока используем стандартное сообщение с персональностью slots_loss
            text = await PersonalityEngine.get_message('roulette_loss', user) # Добавим в персональности
            if 'roulette_loss' not in ['big_win', 'slots_loss', 'dice_win', 'dice_loss', 'jackpot', 'low_balance', 'daily_bonus', 'welcome_back', 'error_too_fast']:
                text = f"💔 <b>Не угадал...</b>\n\n"
                text += f"🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
                text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            
            else:
                # Добавляем детали к сообщению персональности
                text += f"\n\n🎯 Выпало: {color_emoji} <b>{result_number}</b>\n\n"
                text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                if vip_message:
                    text += f"{vip_message}\n"
                if credit_message:
                    text += f"{credit_message}\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
            

        await message.answer(text)
        await state.clear()


# --- ИГРА В МИНЫ ---

@router.message(lambda message: message.text and message.text.startswith('/mines '))
async def cmd_mines_with_stake(message: Message, state: FSMContext):
    """Обрабатывает команду /mines с параметром ставки"""
    try:
        # Извлекаем сумму из команды
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>/mines 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='mines',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Генерируем мины
        mines_nonce = getattr(user, 'mines_nonce', 0)
        mines = MinesGame.generate_mines(user.id, mines_nonce)
        
        # Проверяем подкрутку и открутку
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - убираем все мины (игрок всегда выигрывает)
            mines = []
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - добавляем мины во все клетки (игрок всегда проигрывает)
            mines = list(range(25))  # Все 25 клеток - мины
        
        if hasattr(user, 'mines_nonce'):
            user.mines_nonce += 1
        await session.commit()

        # Создаем клавиатуру 5x5
        keyboard = create_mines_keyboard()

        # Сохраняем данные игры в состоянии
        await state.update_data(
            bet_id=bet.id,
            stake_cents=stake_cents,
            mines=mines,
            opened_cells=[],
            moves_count=0,
            user_id=user.id
        )
        await state.set_state(MinesStates.playing)

        # Отправляем сообщение с игрой
        username = message.from_user.username or message.from_user.first_name
        text = f"@{username}, вы начали игру минное поле!\n\n"
        text += f"💰 Ставка: ${format_money(stake_cents)}\n\n"
        text += "Выберите клетку для открытия:"

        await message.answer(text, reply_markup=keyboard)


def create_mines_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру 5x5 для игры в мины"""
    keyboard = []
    
    # Создаем кнопки 5x5
    for row in range(5):
        keyboard_row = []
        for col in range(5):
            button = InlineKeyboardButton(
                text="❓",
                callback_data=f"mines_open_{row}_{col}"
            )
            keyboard_row.append(button)
        keyboard.append(keyboard_row)
    
    # Добавляем кнопку отмены
    cancel_button = InlineKeyboardButton(
        text="❌ Отменить",
        callback_data="mines_cancel"
    )
    keyboard.append([cancel_button])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(lambda c: c.data.startswith('mines_'))
async def handle_mines_callback(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок в игре мины"""
    await callback.answer()
    
    data = await state.get_data()
    bet_id = data.get('bet_id')
    stake_cents = data.get('stake_cents')
    mines = data.get('mines')
    opened_cells = data.get('opened_cells', [])
    moves_count = data.get('moves_count', 0)
    user_id = data.get('user_id')
    
    if not all([bet_id, stake_cents, mines, user_id]):
        await callback.message.edit_text("❌ Ошибка данных игры. Попробуйте снова.")
        await state.clear()
        return
    
    if callback.data == "mines_cancel":
        # Пользователь решил забрать выигрыш
        if moves_count == 0:
            # Если не сделал ни одного хода, возвращаем ставку
            payout = stake_cents
        else:
            # Рассчитываем выигрыш
            payout = MinesGame.calculate_payout(stake_cents, moves_count)
        
        # Завершаем ставку
        await bet_service.complete_bet(bet_id, f"cancelled_after_{moves_count}_moves", payout)
        
        # Получаем пользователя
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                new_balance = await wallet_service.get_balance(user.id)
                username = callback.from_user.username or callback.from_user.first_name
                
                if moves_count == 0:
                    text = f"@{username}, игра отменена.\n\n"
                    text += f"↩️ Ставка возвращена: <b>${format_money(payout)}</b>\n"
                    text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
                else:
                    text = f"@{username}, игра завершена!\n\n"
                    text += f"💰 Выигрыш: <b>${format_money(payout)}</b>\n"
                    text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
                
                await callback.message.edit_text(text)
        
        await state.clear()
        return
    
    # Обрабатываем открытие клетки
    if callback.data.startswith("mines_open_"):
        # Извлекаем координаты
        coords = callback.data.replace("mines_open_", "").split("_")
        row, col = int(coords[0]), int(coords[1])
        position = MinesGame.coords_to_position(row, col)
        
        # Проверяем, не открыта ли уже эта клетка
        if position in opened_cells:
            return
        
        # Проверяем, есть ли мина в этой клетке
        if position in mines:
            # Пользователь попал на мину - проиграл
            await bet_service.complete_bet(bet_id, f"lost_on_move_{moves_count + 1}", 0)
            
            # Получаем пользователя
            from src.database import async_session_maker
            async with async_session_maker() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                
                if user:
                    new_balance = await wallet_service.get_balance(user.id)
                    username = callback.from_user.username or callback.from_user.first_name
                    
                    text = f"@{username}, игра завершена!\n\n"
                    text += f"💸 Вы проиграли\n"
                    text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
                    
                    # Создаем финальную клавиатуру с открытыми минами
                    final_keyboard = create_final_mines_keyboard(mines, opened_cells + [position])
                    await callback.message.edit_text(text, reply_markup=final_keyboard)
            
            await state.clear()
            return
        
        # Клетка безопасна - продолжаем игру
        opened_cells.append(position)
        moves_count += 1
        
        # Проверяем максимальное количество ходов (защита от абуза)
        if moves_count >= MinesGame.MAX_SAFE_MOVES:
            # Принудительно завершаем игру с максимальным выигрышем
            payout = MinesGame.calculate_payout(stake_cents, moves_count)
            await bet_service.complete_bet(bet_id, f"max_moves_reached_{moves_count}", payout)
            
            # Получаем пользователя
            from src.database import async_session_maker
            async with async_session_maker() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                
                if user:
                    new_balance = await wallet_service.get_balance(user.id)
                    username = callback.from_user.username or callback.from_user.first_name
                    
                    text = f"@{username}, игра завершена!\n\n"
                    text += f"🎯 Достигнут максимум ходов ({MinesGame.MAX_SAFE_MOVES})\n"
                    text += f"💰 Выигрыш: <b>${format_money(payout)}</b>\n"
                    text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
                    
                    # Создаем финальную клавиатуру с открытыми минами
                    final_keyboard = create_final_mines_keyboard(mines, opened_cells)
                    await callback.message.edit_text(text, reply_markup=final_keyboard)
            
            await state.clear()
            return
        
        # Обновляем состояние
        await state.update_data(
            opened_cells=opened_cells,
            moves_count=moves_count
        )
        
        # Создаем обновленную клавиатуру
        updated_keyboard = create_updated_mines_keyboard(opened_cells)
        
        # Обновляем сообщение
        username = callback.from_user.username or callback.from_user.first_name
        multiplier = MinesGame.get_multiplier(moves_count)
        text = f"@{username}, вы начали игру минное поле!\n\n"
        text += f"💰 Ставка: ${format_money(stake_cents)}\n"
        text += f"🎯 Ход: {moves_count} | Коэффициент: x{multiplier:.1f}\n\n"
        text += "Выберите клетку для открытия:"
        
        await callback.message.edit_text(text, reply_markup=updated_keyboard)


def create_updated_mines_keyboard(opened_cells: list) -> InlineKeyboardMarkup:
    """Создает обновленную клавиатуру с открытыми клетками"""
    keyboard = []
    
    # Создаем кнопки 5x5
    for row in range(5):
        keyboard_row = []
        for col in range(5):
            position = MinesGame.coords_to_position(row, col)
            
            if position in opened_cells:
                # Открытая клетка - пустая
                button = InlineKeyboardButton(
                    text="⬜",
                    callback_data="mines_opened"
                )
            else:
                # Закрытая клетка
                button = InlineKeyboardButton(
                    text="❓",
                    callback_data=f"mines_open_{row}_{col}"
                )
            keyboard_row.append(button)
        keyboard.append(keyboard_row)
    
    # Добавляем кнопку отмены
    cancel_button = InlineKeyboardButton(
        text="❌ Отменить",
        callback_data="mines_cancel"
    )
    keyboard.append([cancel_button])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_final_mines_keyboard(mines: list, opened_cells: list) -> InlineKeyboardMarkup:
    """Создает финальную клавиатуру с открытыми минами"""
    keyboard = []
    
    # Создаем кнопки 5x5
    for row in range(5):
        keyboard_row = []
        for col in range(5):
            position = MinesGame.coords_to_position(row, col)
            
            if position in mines:
                # Мина
                button = InlineKeyboardButton(
                    text="💣",
                    callback_data="mines_final"
                )
            elif position in opened_cells:
                # Открытая безопасная клетка
                button = InlineKeyboardButton(
                    text="⬜",
                    callback_data="mines_final"
                )
            else:
                # Закрытая клетка - пустая
                button = InlineKeyboardButton(
                    text="⬜",
                    callback_data="mines_final"
                )
            keyboard_row.append(button)
        keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- ОБРАБОТЧИКИ КНОПОК ИГР ---

@router.message(lambda message: message.text == '🎰 Слоты' and message.chat.type == 'private')
async def button_slots(message: Message, state: FSMContext):
    """Обработчик кнопки Слоты"""
    if await check_if_banned(message):
        return
    await cmd_slots(message, state)


@router.message(lambda message: message.text == '🎲 Кости' and message.chat.type == 'private')
async def button_dice(message: Message, state: FSMContext):
    """Обработчик кнопки Кости"""
    if await check_if_banned(message):
        return
    await cmd_dice(message, state)


@router.message(lambda message: message.text == '♠️ Рулетка' and message.chat.type == 'private')
async def button_roulette(message: Message, state: FSMContext):
    """Обработчик кнопки Рулетка"""
    if await check_if_banned(message):
        return
    await cmd_roulette(message, state)


@router.message(lambda message: message.text == '💣 Мины' and message.chat.type == 'private')
async def button_mines(message: Message, state: FSMContext):
    """Обработчик кнопки Мины"""
    if await check_if_banned(message):
        return
    # Для личных сообщений используем интерактивный режим
    await message.answer(
        "💣 <b>Мины</b>\n\n"
        "Введите сумму ставки (например, 20):"
    )
    await state.set_state(MinesStates.choosing_stake)


@router.message(lambda message: message.text == '🚀 Ракетка' and message.chat.type == 'private')
async def button_rocket(message: Message, state: FSMContext):
    """Обработчик кнопки Ракетка"""
    if await check_if_banned(message):
        return
    # Для личных сообщений используем интерактивный режим
    await message.answer(
        "🚀 <b>Ракетка</b>\n\n"
        "Введите сумму ставки (например, 20):"
    )
    await state.set_state(RocketStates.choosing_stake)


async def process_mines_stake(message: Message, state: FSMContext):
    """Обрабатывает ввод ставки для игры в мины"""
    try:
        stake_dollars = float(message.text)
        stake_cents = int(stake_dollars * 100)
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число (например, 20)")
        return

    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = message.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            await state.clear()
            return

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='mines',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Генерируем мины
        mines_nonce = getattr(user, 'mines_nonce', 0)
        mines = MinesGame.generate_mines(user.id, mines_nonce)
        
        # Проверяем подкрутку и открутку
        if await is_user_rigged(message.from_user.id):
            # Подкрутка активна - убираем все мины (игрок всегда выигрывает)
            mines = []
        elif await is_user_unrigged(message.from_user.id):
            # Открутка активна - добавляем мины во все клетки (игрок всегда проигрывает)
            mines = list(range(25))  # Все 25 клеток - мины
        
        if hasattr(user, 'mines_nonce'):
            user.mines_nonce += 1
        await session.commit()

        # Создаем клавиатуру 5x5
        keyboard = create_mines_keyboard()

        # Сохраняем данные игры в состоянии
        await state.update_data(
            bet_id=bet.id,
            stake_cents=stake_cents,
            mines=mines,
            opened_cells=[],
            moves_count=0,
            user_id=user.id
        )
        await state.set_state(MinesStates.playing)

        # Отправляем сообщение с игрой
        text = f"💣 <b>Мины</b>\n\n"
        text += f"💰 Ставка: ${format_money(stake_cents)}\n\n"
        text += "Выберите клетку для открытия:"

        await message.answer(text, reply_markup=keyboard)


async def process_rocket_stake(message: Message, state: FSMContext):
    """Обрабатывает ввод ставки для игры в ракетку"""
    try:
        stake_dollars = float(message.text)
        stake_cents = int(stake_dollars * 100)
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число (например, 20)")
        return

    # Проверяем пользователя
    from src.database import async_session_maker
    telegram_id = message.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Сначала запустите бота командой /start")
            await state.clear()
            return

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='rocket',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Запускаем игру
        await start_rocket_game(message, state, bet.id, stake_cents, user)


# --- ИГРА В РАКЕТКУ (CRASH GAME) ---

# Команда: ракетка [ставка]
@router.message(lambda message: message.text and message.text.lower().startswith('ракетка '))
async def text_rocket_with_params(message: Message, state: FSMContext):
    """Обрабатывает текстовую команду 'ракетка [ставка]' без слэша"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Парсим параметры напрямую
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>ракетка 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='rocket',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Запускаем игру
        await start_rocket_game(message, state, bet.id, stake_cents, user)


# Команда: /ракетка [ставка]
@router.message(lambda message: message.text and message.text.startswith('/ракетка '))
async def cmd_rocket_ru_with_stake(message: Message, state: FSMContext):
    """Обрабатывает русскую команду /ракетка с параметром ставки"""
    # Убираем слэш и вызываем текстовый обработчик
    text_without_slash = message.text[1:]  # Убираем первый символ (/)
    import types
    temp_msg = types.SimpleNamespace()
    temp_msg.text = text_without_slash
    temp_msg.from_user = message.from_user
    temp_msg.chat = message.chat
    temp_msg.answer = message.answer
    temp_msg.edit_text = message.edit_text if hasattr(message, 'edit_text') else None
    await text_rocket_with_params(temp_msg, state)


# Команда: /rocket [ставка]
@router.message(lambda message: message.text and message.text.startswith('/rocket '))
async def cmd_rocket_with_stake(message: Message, state: FSMContext):
    """Обрабатывает команду /rocket с параметром ставки"""
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    try:
        # Извлекаем сумму из команды
        stake_text = message.text.split(' ', 1)[1].strip()
        stake_dollars = float(stake_text)
        stake_cents = int(stake_dollars * 100)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат! Используйте: <code>/rocket 20</code>")
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

        # Валидация ставки
        if stake_cents < settings.MIN_BET:
            await message.answer(f"📉 Минимальная ставка — ${format_money(settings.MIN_BET)}")
            return

        if stake_cents > settings.MAX_BET:
            await message.answer(f"📈 Максимальная ставка — ${format_money(settings.MAX_BET)}")
            return

        # Проверяем баланс
        balance = await wallet_service.get_balance(user.id)
        if balance < stake_cents:
            text = await PersonalityEngine.get_message('low_balance', user)
            await message.answer(text)
            return

        try:
            bet = await bet_service.create_bet(
                user_id=user.id,
                chat_id=message.chat.id,
                game_type='rocket',
                stake_cents=stake_cents
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
            return

        # Запускаем игру
        await start_rocket_game(message, state, bet.id, stake_cents, user)


async def start_rocket_game(message: Message, state: FSMContext, bet_id: int, stake_cents: int, user):
    """Запускает игру в ракетку"""
    # Генерируем точку краша
    crash_point = RocketGame.calculate_crash_point()
    
    # Проверяем подкрутку и открутку
    if await is_user_rigged(message.from_user.id):
        # Подкрутка активна - устанавливаем очень высокую точку краша (игрок всегда выигрывает)
        crash_point = 999.99  # Практически невозможно достичь
    elif await is_user_unrigged(message.from_user.id):
        # Открутка активна - устанавливаем очень низкую точку краша (игрок всегда проигрывает)
        crash_point = 1.01  # Практически сразу краш
    
    # Определяем имя пользователя для упоминания в группах
    if message.chat.type in ['group', 'supergroup']:
        username = message.from_user.username or message.from_user.first_name
        user_mention = f"@{username}, "
    else:
        user_mention = ""
    
    # Отправляем предстартовое сообщение
    countdown_msg = await message.answer(f"{user_mention}🚀 Игра начнется через 3 секунды...")
    await asyncio.sleep(1)
    await countdown_msg.edit_text(f"{user_mention}🚀 Игра начнется через 2 секунды...")
    await asyncio.sleep(1)
    await countdown_msg.edit_text(f"{user_mention}🚀 Игра начнется через 1 секунду...")
    await asyncio.sleep(1)
    
    # Создаем кнопку "Забрать"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Забрать", callback_data=f"rocket_cashout_{bet_id}")]
    ])
    
    # Стартовое сообщение
    text = f"{user_mention}🚀 <b>Ракетка</b>\n\n"
    text += f"💰 Ваша ставка: <b>${format_money(stake_cents)}</b>\n"
    text += f"📊 Коэффициент: <b>{RocketGame.format_multiplier(1.0)}</b>"
    
    game_msg = await countdown_msg.edit_text(text, reply_markup=keyboard)
    
    # Сохраняем данные игры в состоянии
    await state.update_data(
        bet_id=bet_id,
        stake_cents=stake_cents,
        crash_point=crash_point,
        user_id=user.id,
        game_message_id=game_msg.message_id,
        chat_id=message.chat.id,
        cashed_out=False,
        user_mention=user_mention
    )
    await state.set_state(RocketStates.playing)
    
    # Создаем флаг для остановки игры и блокировку
    game_stopped = False
    game_locked = False
    
    # Запускаем симуляцию ракеты
    async def update_rocket(multiplier: float, is_crashed: bool):
        """Callback для обновления сообщения"""
        nonlocal game_stopped, game_locked
        
        try:
            # Проверяем блокировку
            if game_locked:
                return False
            
            data = await state.get_data()
            
            # Проверяем, не забрал ли игрок выигрыш или игра остановлена
            if data.get('cashed_out', False) or game_stopped:
                game_stopped = True
                game_locked = True
                return False  # Останавливаем игру
            
            if not is_crashed:
                # Обновляем текст с текущим коэффициентом
                rocket_emoji = RocketGame.get_rocket_emoji(multiplier)
                text = f"{data.get('user_mention', '')}🚀 <b>Ракетка</b>\n\n"
                text += f"💰 Ваша ставка: <b>${format_money(stake_cents)}</b>\n"
                text += f"📊 Коэффициент: <b>{RocketGame.format_multiplier(multiplier)}</b> {rocket_emoji}"
                
                try:
                    await game_msg.edit_text(text, reply_markup=keyboard)
                except Exception:
                    # Игнорируем ошибки редактирования (если сообщение не изменилось)
                    pass
                return True  # Продолжаем игру
            else:
                # Ракета взорвалась!
                if not data.get('cashed_out', False) and not game_stopped and not game_locked:
                    # Блокируем игру перед обработкой взрыва
                    game_locked = True
                    
                    # Игрок не успел забрать - проигрыш
                    try:
                        await bet_service.complete_bet(bet_id, f"crashed_at_{crash_point}", 0)
                    except Exception:
                        # Если ставка уже завершена, игнорируем
                        pass
                    
                    new_balance = await wallet_service.get_balance(user.id)
                    
                    text = f"{data.get('user_mention', '')}💥 <b>Ракетка взорвалась!</b>\n\n"
                    text += f"📊 Коэффициент краша: <b>{RocketGame.format_multiplier(crash_point)}</b>\n\n"
                    text += f"💸 Потеряно: <b>${format_money(stake_cents)}</b>\n"
                    text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
                    
                    await game_msg.edit_text(text)
                    await state.clear()
                    game_stopped = True
                return False  # Останавливаем игру
        
        except Exception as e:
            game_stopped = True
            game_locked = True
            return False  # Останавливаем игру
    
    # Запускаем симуляцию
    await RocketGame.simulate_rocket(crash_point, update_rocket)


# Callback для кнопки "Забрать"
@router.callback_query(lambda c: c.data.startswith('rocket_cashout_'))
async def handle_rocket_cashout(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Забрать' в игре ракетка"""
    try:
        await callback.answer()
        
        # Получаем данные из состояния
        data = await state.get_data()
        
        # Проверяем, что игра активна
        current_state = await state.get_state()
        
        if current_state != RocketStates.playing:
            await callback.answer("❌ Игра уже завершена", show_alert=True)
            return
        
        bet_id = data.get('bet_id')
        stake_cents = data.get('stake_cents')
        crash_point = data.get('crash_point')
        user_id = data.get('user_id')
        user_mention = data.get('user_mention', '')
        
        if not all([bet_id, stake_cents, crash_point, user_id]):
            await callback.answer("❌ Ошибка данных игры", show_alert=True)
            await state.clear()
            return
        
        # Проверяем, не забрал ли уже игрок
        if data.get('cashed_out', False):
            await callback.answer("❌ Вы уже забрали выигрыш", show_alert=True)
            return
        
        # Получаем текущий коэффициент из текста сообщения
        try:
            # Парсим текущий коэффициент из сообщения
            message_text = callback.message.text
            
            if "Коэффициент:" in message_text:
                coef_line = [line for line in message_text.split('\n') if 'Коэффициент:' in line][0]
                
                # Извлекаем число из строки типа "📊 Коэффициент: 2.5x 🚀"
                import re
                match = re.search(r'(\d+\.\d+)x', coef_line)
                if match:
                    current_multiplier = float(match.group(1))
                else:
                    current_multiplier = 1.0
            else:
                current_multiplier = 1.0
        except Exception:
            current_multiplier = 1.0
        
        # Проверяем, не превысил ли коэффициент точку краша
        if current_multiplier >= crash_point:
            await callback.answer("❌ Слишком поздно! Ракетка взорвалась", show_alert=True)
            return
        
        # АТОМАРНО помечаем, что игрок забрал выигрыш
        await state.update_data(cashed_out=True)
        
        # Дополнительная проверка - если уже забрали, выходим
        updated_data = await state.get_data()
        if updated_data.get('cashed_out', False) != True:
            await callback.answer("❌ Ошибка обработки", show_alert=True)
            return
        
        # Рассчитываем выплату
        payout = RocketGame.calculate_payout(stake_cents, current_multiplier)
        
        # Завершаем ставку (с проверкой на дублирование)
        try:
            await bet_service.complete_bet(bet_id, f"cashed_out_at_{current_multiplier}", payout)
        except Exception as e:
            # Если ставка уже завершена, игнорируем ошибку
            if "already completed" in str(e).lower() or "duplicate" in str(e).lower():
                await callback.answer("❌ Ставка уже обработана", show_alert=True)
                await state.clear()
                return
            else:
                raise e
        
        # Получаем пользователя
        from src.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                new_balance = await wallet_service.get_balance(user.id)
                
                text = f"{user_mention}✅ <b>Выигрыш забран!</b>\n\n"
                text += f"📊 Коэффициент: <b>{RocketGame.format_multiplier(current_multiplier)}</b>\n\n"
                text += f"💰 Выигрыш: <b>${format_money(payout)}</b>\n"
                text += f"💵 Баланс: <b>${format_money(new_balance)}</b>"
                
                try:
                    await callback.message.edit_text(text)
                except Exception:
                    # Попробуем отправить новое сообщение
                    try:
                        await callback.message.answer(text)
                    except Exception:
                        pass
        
        # Очищаем состояние игры
        await state.clear()
        
    except Exception as e:
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# --- КОМАНДА ПЕРЕВОДА ДЕНЕГ ---

@router.message(lambda message: message.text and message.text.lower().startswith('перевести '))
async def transfer_money_command(message: Message):
    """Обрабатывает команду 'перевести [количество] [айди пользователя]' для перевода денег"""
    try:
        # Проверка блокировки
        if await check_if_banned(message):
            return
        
        # Парсим команду
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "Используйте: <b>перевести [сумма] [ID пользователя]</b>\n\n"
                              "Пример: <code>перевести 1000 123456789</code>")
            return
        
        # Получаем сумму и ID получателя
        try:
            amount_str = parts[1]
            # Поддерживаем разные форматы: 1000, 1k, 1.5k, 1000000, 1m
            amount_str = amount_str.lower().replace(',', '').replace(' ', '')
            
            if amount_str.endswith('k'):
                amount_cents = int(float(amount_str[:-1]) * 100000)  # k = 1000
            elif amount_str.endswith('m'):
                amount_cents = int(float(amount_str[:-1]) * 100000000)  # m = 1000000
            else:
                amount_cents = int(float(amount_str) * 100)  # обычное число в долларах
            
            if amount_cents <= 0:
                await message.answer("❌ Сумма должна быть больше 0!")
                return
                
        except ValueError:
            await message.answer("❌ Неверный формат суммы!\n\n"
                              "Поддерживаемые форматы:\n"
                              "• <code>1000</code> - 1000 долларов\n"
                              "• <code>1k</code> - 1000 долларов\n"
                              "• <code>1.5k</code> - 1500 долларов\n"
                              "• <code>1m</code> - 1,000,000 долларов")
            return
        
        try:
            recipient_id = int(parts[2])
            if recipient_id <= 0:
                await message.answer("❌ Неверный ID пользователя!")
                return
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя!")
            return
        
        # Проверяем что пользователь не пытается перевести самому себе
        if recipient_id == message.from_user.id:
            await message.answer("❌ Нельзя переводить деньги самому себе!")
            return
        
        # Получаем внутренние user_id для отправителя и получателя
        from src.database import async_session_maker
        async with async_session_maker() as session:
            # Получаем отправителя
            sender_query = select(User).where(User.telegram_id == message.from_user.id)
            sender_result = await session.execute(sender_query)
            sender = sender_result.scalar_one_or_none()
            
            if not sender:
                await message.answer("❌ Ошибка: ваш аккаунт не найден в системе!")
                return
            
            # Получаем получателя, создаем если нет
            recipient_query = select(User).where(User.telegram_id == recipient_id)
            recipient_result = await session.execute(recipient_query)
            recipient = recipient_result.scalar_one_or_none()
            
            if not recipient:
                # Создаем нового пользователя если его нет
                recipient = User(
                    telegram_id=recipient_id,
                    username=f"user_{recipient_id}",  # Временное имя
                    first_name="Unknown",
                    last_name=None,
                    language_code="ru",
                    is_bot=False,
                    is_premium=False,
                    vip_status=False,
                    vip_multiplier=1.0,
                    vip_cashback_percentage=0.0
                )
                session.add(recipient)
                await session.commit()
                await session.refresh(recipient)
        
        # Получаем баланс отправителя
        sender_balance = await wallet_service.get_balance(sender.id)
        
        # Проверяем достаточность средств
        if sender_balance < amount_cents:
            await message.answer(f"❌ Недостаточно средств!\n\n"
                              f"💰 Ваш баланс: <b>${format_money(sender_balance)}</b>\n"
                              f"💸 Требуется: <b>${format_money(amount_cents)}</b>")
            return
        
        # Выполняем перевод
        # Списываем с отправителя
        await wallet_service.debit(sender.id, amount_cents, f"transfer_to_{recipient_id}")
        
        # Зачисляем получателю
        await wallet_service.credit(recipient.id, amount_cents, f"transfer_from_{message.from_user.id}")
        
        # Получаем новые балансы
        new_sender_balance = await wallet_service.get_balance(sender.id)
        new_recipient_balance = await wallet_service.get_balance(recipient.id)
        
        # Формируем сообщение об успешном переводе
        sender_name = message.from_user.username or message.from_user.first_name
        text = f"✅ <b>Перевод выполнен успешно!</b>\n\n"
        text += f"👤 Отправитель: @{sender_name}\n"
        text += f"💰 Сумма: <b>${format_money(amount_cents)}</b>\n"
        text += f"🎯 Получатель ID: <code>{recipient_id}</code>\n\n"
        text += f"💵 Ваш баланс: <b>${format_money(new_sender_balance)}</b>"
        
        await message.answer(text)
        
        # Отправляем уведомление получателю (если возможно)
        try:
            recipient_text = f"💰 <b>Получен перевод!</b>\n\n"
            recipient_text += f"👤 От: @{sender_name}\n"
            recipient_text += f"💰 Сумма: <b>${format_money(amount_cents)}</b>\n"
            recipient_text += f"💵 Ваш баланс: <b>${format_money(new_recipient_balance)}</b>"
            
            await message.bot.send_message(recipient_id, recipient_text)
        except Exception:
            # Если не удалось отправить уведомление получателю, это не критично
            pass
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при выполнении перевода. Попробуйте позже.")
        print(f"Transfer error: {e}")


@router.message(lambda message: message.text and message.text.startswith('/transfer '))
async def cmd_transfer_with_params(message: Message):
    """Обрабатывает команду /transfer с параметрами (английская версия)"""
    # Заменяем команду на русскую версию и вызываем основной обработчик
    message.text = message.text.replace('/transfer ', 'перевести ', 1)
    await transfer_money_command(message)


# --- КОМАНДА ПЕРЕВОДА ЧЕРЕЗ РЕПЛАЙ ---

@router.message(lambda message: message.reply_to_message and message.text and message.text.lower().startswith('п '))
async def transfer_money_reply_command(message: Message):
    """Обрабатывает команду 'п [сумма]' в ответ на сообщение пользователя"""
    try:
        # Проверка блокировки
        if await check_if_banned(message):
            return
        
        # Проверяем что реплай не на бота
        if message.reply_to_message.from_user.is_bot:
            await message.answer("❌ Нельзя переводить деньги боту!")
            return
        
        # Проверяем что пользователь не пытается перевести самому себе
        if message.reply_to_message.from_user.id == message.from_user.id:
            await message.answer("❌ Нельзя переводить деньги самому себе!")
            return
        
        # Парсим команду
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "Используйте: <b>п [сумма]</b>\n\n"
                              "Пример: <code>п 1000</code>")
            return
        
        # Получаем сумму
        try:
            amount_str = parts[1]
            # Поддерживаем разные форматы: 1000, 1k, 1.5k, 1000000, 1m
            amount_str = amount_str.lower().replace(',', '').replace(' ', '')
            
            if amount_str.endswith('k'):
                amount_cents = int(float(amount_str[:-1]) * 100000)  # k = 1000
            elif amount_str.endswith('m'):
                amount_cents = int(float(amount_str[:-1]) * 100000000)  # m = 1000000
            else:
                amount_cents = int(float(amount_str) * 100)  # обычное число в долларах
            
            if amount_cents <= 0:
                await message.answer("❌ Сумма должна быть больше 0!")
                return
                
        except ValueError:
            await message.answer("❌ Неверный формат суммы!\n\n"
                              "Поддерживаемые форматы:\n"
                              "• <code>1000</code> - 1000 долларов\n"
                              "• <code>1k</code> - 1000 долларов\n"
                              "• <code>1.5k</code> - 1500 долларов\n"
                              "• <code>1m</code> - 1,000,000 долларов")
            return
        
        # Получаем ID получателя из реплая
        recipient_id = message.reply_to_message.from_user.id
        
        # Получаем внутренние user_id для отправителя и получателя
        from src.database import async_session_maker
        async with async_session_maker() as session:
            # Получаем отправителя
            sender_query = select(User).where(User.telegram_id == message.from_user.id)
            sender_result = await session.execute(sender_query)
            sender = sender_result.scalar_one_or_none()
            
            if not sender:
                await message.answer("❌ Ошибка: ваш аккаунт не найден в системе!")
                return
            
            # Получаем получателя, создаем если нет
            recipient_query = select(User).where(User.telegram_id == recipient_id)
            recipient_result = await session.execute(recipient_query)
            recipient = recipient_result.scalar_one_or_none()
            
            if not recipient:
                # Создаем нового пользователя если его нет
                recipient = User(
                    telegram_id=recipient_id,
                    username=f"user_{recipient_id}",  # Временное имя
                    first_name="Unknown",
                    last_name=None,
                    language_code="ru",
                    is_bot=False,
                    is_premium=False,
                    vip_status=False,
                    vip_multiplier=1.0,
                    vip_cashback_percentage=0.0
                )
                session.add(recipient)
                await session.commit()
                await session.refresh(recipient)
        
        # Получаем баланс отправителя
        sender_balance = await wallet_service.get_balance(sender.id)
        
        # Проверяем достаточность средств
        if sender_balance < amount_cents:
            await message.answer(f"❌ Недостаточно средств!\n\n"
                              f"💰 Ваш баланс: <b>${format_money(sender_balance)}</b>\n"
                              f"💸 Требуется: <b>${format_money(amount_cents)}</b>")
            return
        
        # Выполняем перевод
        # Списываем с отправителя
        await wallet_service.debit(sender.id, amount_cents, f"transfer_to_{recipient_id}")
        
        # Зачисляем получателю
        await wallet_service.credit(recipient.id, amount_cents, f"transfer_from_{message.from_user.id}")
        
        # Получаем новые балансы
        new_sender_balance = await wallet_service.get_balance(sender.id)
        new_recipient_balance = await wallet_service.get_balance(recipient.id)
        
        # Формируем сообщение об успешном переводе
        sender_name = message.from_user.username or message.from_user.first_name
        recipient_name = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
        text = f"✅ <b>Перевод выполнен успешно!</b>\n\n"
        text += f"👤 Отправитель: @{sender_name}\n"
        text += f"💰 Сумма: <b>${format_money(amount_cents)}</b>\n"
        text += f"🎯 Получатель: @{recipient_name}\n\n"
        text += f"💵 Ваш баланс: <b>${format_money(new_sender_balance)}</b>"
        
        await message.answer(text)
        
        # Отправляем уведомление получателю (если возможно)
        try:
            recipient_text = f"💰 <b>Получен перевод!</b>\n\n"
            recipient_text += f"👤 От: @{sender_name}\n"
            recipient_text += f"💰 Сумма: <b>${format_money(amount_cents)}</b>\n"
            recipient_text += f"💵 Ваш баланс: <b>${format_money(new_recipient_balance)}</b>"
            
            await message.bot.send_message(recipient_id, recipient_text)
        except Exception:
            # Если не удалось отправить уведомление получателю, это не критично
            pass
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при выполнении перевода. Попробуйте позже.")
        print(f"Transfer reply error: {e}")


# --- КОРОТКИЙ АЛИАС КОМАНДЫ ПЕРЕВОДА ---

@router.message(lambda message: message.text and message.text.lower().startswith('п '))
async def transfer_money_short_command(message: Message):
    """Обрабатывает короткую команду 'п [сумма] [айди пользователя]'"""
    try:
        # Проверка блокировки
        if await check_if_banned(message):
            return
        
        # Парсим команду
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "Используйте: <b>п [сумма] [ID пользователя]</b>\n\n"
                              "Пример: <code>п 1000 123456789</code>")
            return
        
        # Получаем сумму и ID получателя
        try:
            amount_str = parts[1]
            # Поддерживаем разные форматы: 1000, 1k, 1.5k, 1000000, 1m
            amount_str = amount_str.lower().replace(',', '').replace(' ', '')
            
            if amount_str.endswith('k'):
                amount_cents = int(float(amount_str[:-1]) * 100000)  # k = 1000
            elif amount_str.endswith('m'):
                amount_cents = int(float(amount_str[:-1]) * 100000000)  # m = 1000000
            else:
                amount_cents = int(float(amount_str) * 100)  # обычное число в долларах
            
            if amount_cents <= 0:
                await message.answer("❌ Сумма должна быть больше 0!")
                return
                
        except ValueError:
            await message.answer("❌ Неверный формат суммы!\n\n"
                              "Поддерживаемые форматы:\n"
                              "• <code>1000</code> - 1000 долларов\n"
                              "• <code>1k</code> - 1000 долларов\n"
                              "• <code>1.5k</code> - 1500 долларов\n"
                              "• <code>1m</code> - 1,000,000 долларов")
            return
        
        try:
            recipient_id = int(parts[2])
            if recipient_id <= 0:
                await message.answer("❌ Неверный ID пользователя!")
                return
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя!")
            return
        
        # Проверяем что пользователь не пытается перевести самому себе
        if recipient_id == message.from_user.id:
            await message.answer("❌ Нельзя переводить деньги самому себе!")
            return
        
        # Получаем внутренние user_id для отправителя и получателя
        from src.database import async_session_maker
        async with async_session_maker() as session:
            # Получаем отправителя
            sender_query = select(User).where(User.telegram_id == message.from_user.id)
            sender_result = await session.execute(sender_query)
            sender = sender_result.scalar_one_or_none()
            
            if not sender:
                await message.answer("❌ Ошибка: ваш аккаунт не найден в системе!")
                return
            
            # Получаем получателя, создаем если нет
            recipient_query = select(User).where(User.telegram_id == recipient_id)
            recipient_result = await session.execute(recipient_query)
            recipient = recipient_result.scalar_one_or_none()
            
            if not recipient:
                # Создаем нового пользователя если его нет
                recipient = User(
                    telegram_id=recipient_id,
                    username=f"user_{recipient_id}",  # Временное имя
                    first_name="Unknown",
                    last_name=None,
                    language_code="ru",
                    is_bot=False,
                    is_premium=False,
                    vip_status=False,
                    vip_multiplier=1.0,
                    vip_cashback_percentage=0.0
                )
                session.add(recipient)
                await session.commit()
                await session.refresh(recipient)
        
        # Получаем баланс отправителя
        sender_balance = await wallet_service.get_balance(sender.id)
        
        # Проверяем достаточность средств
        if sender_balance < amount_cents:
            await message.answer(f"❌ Недостаточно средств!\n\n"
                              f"💰 Ваш баланс: <b>${format_money(sender_balance)}</b>\n"
                              f"💸 Требуется: <b>${format_money(amount_cents)}</b>")
            return
        
        # Выполняем перевод
        # Списываем с отправителя
        await wallet_service.debit(sender.id, amount_cents, f"transfer_to_{recipient_id}")
        
        # Зачисляем получателю
        await wallet_service.credit(recipient.id, amount_cents, f"transfer_from_{message.from_user.id}")
        
        # Получаем новые балансы
        new_sender_balance = await wallet_service.get_balance(sender.id)
        new_recipient_balance = await wallet_service.get_balance(recipient.id)
        
        # Формируем сообщение об успешном переводе
        sender_name = message.from_user.username or message.from_user.first_name
        text = f"✅ <b>Перевод выполнен успешно!</b>\n\n"
        text += f"👤 Отправитель: @{sender_name}\n"
        text += f"💰 Сумма: <b>${format_money(amount_cents)}</b>\n"
        text += f"🎯 Получатель ID: <code>{recipient_id}</code>\n\n"
        text += f"💵 Ваш баланс: <b>${format_money(new_sender_balance)}</b>"
        
        await message.answer(text)
        
        # Отправляем уведомление получателю (если возможно)
        try:
            recipient_text = f"💰 <b>Получен перевод!</b>\n\n"
            recipient_text += f"👤 От: @{sender_name}\n"
            recipient_text += f"💰 Сумма: <b>${format_money(amount_cents)}</b>\n"
            recipient_text += f"💵 Ваш баланс: <b>${format_money(new_recipient_balance)}</b>"
            
            await message.bot.send_message(recipient_id, recipient_text)
        except Exception:
            # Если не удалось отправить уведомление получателю, это не критично
            pass
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при выполнении перевода. Попробуйте позже.")
        print(f"Transfer short error: {e}")


# --- АЛИАСЫ ДЛЯ ПОКАЗА БАЛАНСА ---

@router.message(lambda message: message.text and message.text.lower() in ['б', 'баланс', 'м', 'мешок'])
async def show_balance_aliases(message: Message):
    """Показывает баланс по алиасам: б, баланс, м, мешок"""
    try:
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
            
            # Формируем сообщение с упоминанием пользователя в группах
            if message.chat.type in ['group', 'supergroup']:
                username = message.from_user.username or message.from_user.first_name
                text = f"@{username}, 💰 Твой баланс: <b>${balance / 100:.2f}</b>"
            else:
                text = f"💰 Твой баланс: <b>${balance / 100:.2f}</b>"

            await message.answer(text)
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при получении баланса. Попробуйте позже.")
        print(f"Balance alias error: {e}")


# --- ФУНКЦИИ ПОДКРУТКИ ---

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    try:
        from src.config import settings
        admin_ids = settings.ADMIN_ID
        if isinstance(admin_ids, str):
            admin_ids = [int(x.strip()) for x in admin_ids.split(',')]
        elif isinstance(admin_ids, int):
            admin_ids = [admin_ids]
        return user_id in admin_ids
    except Exception:
        return False

async def get_user_rig_info(user_id: int):
    """Возвращает статус подкрутки и время окончания"""
    try:
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        from datetime import datetime
        
        async with async_session_maker() as session:
            
            user_query = select(User).where(User.telegram_id == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            print(f"DEBUG RIG INFO: User {user_id}, user found: {user is not None}, rig_until: {getattr(user, 'rig_until', None) if user else None}")
            
            if not user or not user.rig_until:
                return False, None
            
            # Проверяем не истекла ли подкрутка
            if datetime.utcnow() > user.rig_until:
                # Очищаем истекшую подкрутку
                user.rig_until = None
                await session.commit()
                print(f"DEBUG RIG INFO: Rig expired for user {user_id}")
                return False, None
            
            print(f"DEBUG RIG INFO: Rig active for user {user_id} until {user.rig_until}")
            return True, user.rig_until
    except Exception as e:
        print(f"Rig info error: {e}")
        return False, None

async def get_user_unrig_info(user_id: int):
    """Возвращает статус открутки и время окончания"""
    try:
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        from datetime import datetime
        
        async with async_session_maker() as session:
            
            user_query = select(User).where(User.telegram_id == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            print(f"DEBUG UNRIG INFO: User {user_id}, user found: {user is not None}, unrig_until: {getattr(user, 'unrig_until', None) if user else None}")
            
            if not user or not user.unrig_until:
                return False, None
            
            # Проверяем не истекла ли открутка
            if datetime.utcnow() > user.unrig_until:
                # Очищаем истекшую открутку
                user.unrig_until = None
                await session.commit()
                print(f"DEBUG UNRIG INFO: Unrig expired for user {user_id}")
                return False, None
            
            print(f"DEBUG UNRIG INFO: Unrig active for user {user_id} until {user.unrig_until}")
            return True, user.unrig_until
    except Exception as e:
        print(f"Unrig info error: {e}")
        return False, None

async def is_user_rigged(user_id: int) -> bool:
    """Проверяет, активна ли подкрутка у пользователя"""
    try:
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        from datetime import datetime
        
        async with async_session_maker() as session:
            
            user_query = select(User).where(User.telegram_id == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            print(f"DEBUG RIG: User {user_id}, user found: {user is not None}, rig_until: {getattr(user, 'rig_until', None) if user else None}")
            
            if not user or not user.rig_until:
                return False
            
            # Проверяем не истекла ли подкрутка
            if datetime.utcnow() > user.rig_until:
                # Очищаем истекшую подкрутку
                user.rig_until = None
                await session.commit()
                print(f"DEBUG RIG: Rig expired for user {user_id}")
                return False
            
            print(f"DEBUG RIG: Rig active for user {user_id} until {user.rig_until}")
            return True
    except Exception as e:
        print(f"Rig check error: {e}")
        return False

async def is_user_unrigged(user_id: int) -> bool:
    """Проверяет, активна ли открутка у пользователя"""
    try:
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        from datetime import datetime
        
        async with async_session_maker() as session:
            
            user_query = select(User).where(User.telegram_id == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            print(f"DEBUG UNRIG: User {user_id}, user found: {user is not None}, unrig_until: {getattr(user, 'unrig_until', None) if user else None}")
            
            if not user or not user.unrig_until:
                return False
            
            # Проверяем не истекла ли открутка
            if datetime.utcnow() > user.unrig_until:
                # Очищаем истекшую открутку
                user.unrig_until = None
                await session.commit()
                print(f"DEBUG UNRIG: Unrig expired for user {user_id}")
                return False
            
            print(f"DEBUG UNRIG: Unrig active for user {user_id} until {user.unrig_until}")
            return True
    except Exception as e:
        print(f"Unrig check error: {e}")
        return False

# --- КОМАНДА ПОДКРУТКИ ---

@router.message(lambda message: message.text and message.text.lower().startswith('подкрутка '))
async def rig_user_command(message: Message):
    """Обрабатывает команду 'подкрутка [айди пользователя] [время]' для подкрутки"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды!")
        return
    
    try:
        # Парсим команду: подкрутка 123456789 30s
        parts = message.text.lower().split()
        if len(parts) != 3:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "📝 Использование: <code>подкрутка [айди пользователя] [время]</code>\n\n"
                              "⏰ Форматы времени:\n"
                              "• <code>30s</code> - 30 секунд\n"
                              "• <code>2h</code> - 2 часа\n"
                              "• <code>1y</code> - 1 год")
            return
        
        # Парсим ID пользователя
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный ID пользователя!")
            return
        
        # Парсим время
        time_str = parts[2]
        if not time_str[-1] in ['s', 'h', 'y']:
            await message.answer("❌ Неверный формат времени!\n\n"
                              "⏰ Доступные форматы:\n"
                              "• <code>s</code> - секунды\n"
                              "• <code>h</code> - часы\n"
                              "• <code>y</code> - годы")
            return
        
        try:
            time_value = int(time_str[:-1])
            if time_value <= 0:
                raise ValueError("Время должно быть больше 0")
        except ValueError:
            await message.answer("❌ Неверное значение времени!")
            return
        
        # Конвертируем время в секунды
        time_unit = time_str[-1]
        if time_unit == 's':
            duration_seconds = time_value
        elif time_unit == 'h':
            duration_seconds = time_value * 3600
        elif time_unit == 'y':
            duration_seconds = time_value * 365 * 24 * 3600
        else:
            await message.answer("❌ Неподдерживаемый формат времени!")
            return
        
        # Проверяем максимальное время (1 год)
        if duration_seconds > 365 * 24 * 3600:
            await message.answer("❌ Максимальное время подкрутки: 1 год!")
            return
        
        # Получаем пользователей
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        async with async_session_maker() as session:
            
            # Получаем грабителя
            robber_query = select(User).where(User.telegram_id == message.from_user.id)
            robber_result = await session.execute(robber_query)
            robber = robber_result.scalar_one_or_none()
            
            if not robber:
                await message.answer("❌ Ваш аккаунт не найден в системе!")
                return
            
            # Получаем цель
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
        
        # Устанавливаем подкрутку
        rig_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        
        print(f"DEBUG RIG SET: Setting rig_until for user {target_id} to {rig_until}")
        
        async with async_session_maker() as session:
            # Получаем пользователя заново в новой сессии
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
            
            target.rig_until = rig_until
            await session.commit()
            print(f"DEBUG RIG SET: Successfully set rig_until for user {target_id}")
        
        # Форматируем время для отображения
        if time_unit == 's':
            time_display = f"{time_value} сек"
        elif time_unit == 'h':
            time_display = f"{time_value} час"
        else:
            time_display = f"{time_value} год"
        
        # Красивое сообщение об успехе
        success_text = f"🎯 <b>ПОДКРУТКА АКТИВИРОВАНА!</b> 🎯\n\n"
        success_text += f"👤 Пользователь: <code>{target_id}</code>\n"
        success_text += f"⏰ Длительность: <b>{time_display}</b>\n"
        success_text += f"🎰 Статус: <b>100% выигрыши</b>\n\n"
        success_text += f"🕐 Действует до: <b>{rig_until.strftime('%d.%m.%Y %H:%M:%S')}</b>"
        
        await message.answer(success_text)
        
    except Exception as e:
        print(f"Rig command error: {e}")
        await message.answer("❌ Произошла ошибка при активации подкрутки. Попробуйте позже.")


# --- КОМАНДА ОТКРУТКИ ---

@router.message(lambda message: message.text and message.text.lower().startswith('открутка '))
async def unrig_user_command(message: Message):
    """Обрабатывает команду 'открутка [айди пользователя] [время]' для открутки"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды!")
        return
    
    try:
        # Парсим команду: открутка 123456789 30s
        parts = message.text.lower().split()
        if len(parts) != 3:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "📝 Использование: <code>открутка [айди пользователя] [время]</code>\n\n"
                              "⏰ Форматы времени:\n"
                              "• <code>30s</code> - 30 секунд\n"
                              "• <code>2h</code> - 2 часа\n"
                              "• <code>1y</code> - 1 год")
            return
        
        # Парсим ID пользователя
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный ID пользователя!")
            return
        
        # Парсим время
        time_str = parts[2]
        if not time_str[-1] in ['s', 'h', 'y']:
            await message.answer("❌ Неверный формат времени!\n\n"
                              "⏰ Доступные форматы:\n"
                              "• <code>s</code> - секунды\n"
                              "• <code>h</code> - часы\n"
                              "• <code>y</code> - годы")
            return
        
        try:
            time_value = int(time_str[:-1])
            if time_value <= 0:
                raise ValueError("Время должно быть больше 0")
        except ValueError:
            await message.answer("❌ Неверное значение времени!")
            return
        
        # Конвертируем время в секунды
        time_unit = time_str[-1]
        if time_unit == 's':
            duration_seconds = time_value
        elif time_unit == 'h':
            duration_seconds = time_value * 3600
        elif time_unit == 'y':
            duration_seconds = time_value * 365 * 24 * 3600
        else:
            await message.answer("❌ Неподдерживаемый формат времени!")
            return
        
        # Проверяем максимальное время (1 год)
        if duration_seconds > 365 * 24 * 3600:
            await message.answer("❌ Максимальное время открутки: 1 год!")
            return
        
        # Получаем пользователей
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        async with async_session_maker() as session:
            
            # Получаем администратора
            admin_query = select(User).where(User.telegram_id == message.from_user.id)
            admin_result = await session.execute(admin_query)
            admin = admin_result.scalar_one_or_none()
            
            if not admin:
                await message.answer("❌ Ваш аккаунт не найден в системе!")
                return
            
            # Получаем цель
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
        
        # Устанавливаем открутку
        unrig_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        
        print(f"DEBUG UNRIG SET: Setting unrig_until for user {target_id} to {unrig_until}")
        
        async with async_session_maker() as session:
            # Получаем пользователя заново в новой сессии
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
            
            target.unrig_until = unrig_until
            await session.commit()
            print(f"DEBUG UNRIG SET: Successfully set unrig_until for user {target_id}")
        
        # Форматируем время для отображения
        if time_unit == 's':
            time_display = f"{time_value} сек"
        elif time_unit == 'h':
            time_display = f"{time_value} час"
        else:
            time_display = f"{time_value} год"
        
        # Красивое сообщение об успехе
        success_text = f"💀 <b>ОТКРУТКА АКТИВИРОВАНА!</b> 💀\n\n"
        success_text += f"👤 Пользователь: <code>{target_id}</code>\n"
        success_text += f"⏰ Длительность: <b>{time_display}</b>\n"
        success_text += f"🎰 Статус: <b>100% проигрыши</b>\n\n"
        success_text += f"🕐 Действует до: <b>{unrig_until.strftime('%d.%m.%Y %H:%M:%S')}</b>"
        
        await message.answer(success_text)
        
    except Exception as e:
        print(f"Unrig command error: {e}")
        await message.answer("❌ Произошла ошибка при активации открутки. Попробуйте позже.")


# --- КОМАНДА ПРОВЕРКИ ЛИЧНОСТИ ---

@router.message(lambda message: message.text and message.text.lower().startswith('личность '))
async def check_personality_command(message: Message):
    """Обрабатывает команду 'личность [айди пользователя]' для проверки личности"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды!")
        return
    
    try:
        # Парсим команду: личность 123456789
        parts = message.text.lower().split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "📝 Использование: <code>личность [айди пользователя]</code>")
            return
        
        # Парсим ID пользователя
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный ID пользователя!")
            return
        
        # Получаем пользователя
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
        
        # Показываем информацию о личности
        personality = getattr(target, 'personality', 'playful')
        success_text = f"👤 <b>ЛИЧНОСТЬ ПОЛЬЗОВАТЕЛЯ</b> 👤\n\n"
        success_text += f"🆔 ID: <code>{target_id}</code>\n"
        success_text += f"👤 Имя: <b>{target.first_name or 'Не указано'}</b>\n"
        success_text += f"🎭 Личность: <b>{personality}</b>\n\n"
        success_text += f"📝 Доступные личности: <code>playful, neutral, formal, freak</code>"
        
        await message.answer(success_text)
        
    except Exception as e:
        print(f"Check personality command error: {e}")
        await message.answer("❌ Произошла ошибка при проверке личности. Попробуйте позже.")


# --- КОМАНДА ПРОВЕРКИ ПОДКРУТКИ ---

@router.message(lambda message: message.text and message.text.lower().startswith('статус '))
async def check_rig_status_command(message: Message):
    """Обрабатывает команду 'статус [айди пользователя]' для проверки подкрутки/открутки"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды!")
        return
    
    try:
        # Парсим команду: статус 123456789
        parts = message.text.lower().split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "📝 Использование: <code>статус [айди пользователя]</code>")
            return
        
        # Парсим ID пользователя
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный ID пользователя!")
            return
        
        # Получаем пользователя
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
        
        # Проверяем статус подкрутки/открутки
        print(f"DEBUG STATUS START: Checking user {target_id}")
        is_rigged, rig_until = await get_user_rig_info(target_id)
        is_unrigged, unrig_until = await get_user_unrig_info(target_id)
        
        print(f"DEBUG STATUS: User {target_id}, is_rigged: {is_rigged}, rig_until: {rig_until}, is_unrigged: {is_unrigged}, unrig_until: {unrig_until}")
        
        success_text = f"🎯 <b>СТАТУС МОДИФИКАЦИЙ</b> 🎯\n\n"
        success_text += f"🆔 ID: <code>{target_id}</code>\n"
        success_text += f"👤 Имя: <b>{target.first_name or 'Не указано'}</b>\n\n"
        
        if is_rigged:
            success_text += f"🎯 <b>ПОДКРУТКА АКТИВНА</b>\n"
            success_text += f"⏰ До: <b>{rig_until.strftime('%d.%m.%Y %H:%M:%S')}</b>\n\n"
        elif is_unrigged:
            success_text += f"💀 <b>ОТКРУТКА АКТИВНА</b>\n"
            success_text += f"⏰ До: <b>{unrig_until.strftime('%d.%m.%Y %H:%M:%S')}</b>\n\n"
        else:
            success_text += f"🎰 <b>ОБЫЧНАЯ ИГРА</b>\n"
            success_text += f"📝 Модификации не активны\n\n"
        
        success_text += f"🔧 Используйте команды:\n"
        success_text += f"• <code>подкрутка {target_id} 30s</code>\n"
        success_text += f"• <code>открутка {target_id} 30s</code>\n"
        success_text += f"• <code>выключить {target_id}</code>"
        
        await message.answer(success_text)
        
    except Exception as e:
        print(f"Check rig status command error: {e}")
        await message.answer("❌ Произошла ошибка при проверке статуса. Попробуйте позже.")


# --- КОМАНДА ВЫКЛЮЧЕНИЯ ПОДКРУТКИ/ОТКРУТКИ ---

@router.message(lambda message: message.text and message.text.lower().startswith('выключить '))
async def disable_rig_command(message: Message):
    """Обрабатывает команду 'выключить [айди пользователя]' для отключения подкрутки/открутки"""
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды!")
        return
    
    try:
        # Парсим команду: выключить 123456789
        parts = message.text.lower().split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "📝 Использование: <code>выключить [айди пользователя]</code>\n\n"
                              "🔧 Эта команда отключает подкрутку и открутку для указанного пользователя")
            return
        
        # Парсим ID пользователя
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный ID пользователя!")
            return
        
        # Получаем пользователей
        from src.database import async_session_maker
        from src.models import User
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            
            # Получаем администратора
            admin_query = select(User).where(User.telegram_id == message.from_user.id)
            admin_result = await session.execute(admin_query)
            admin = admin_result.scalar_one_or_none()
            
            if not admin:
                await message.answer("❌ Ваш аккаунт не найден в системе!")
                return
            
            # Получаем цель
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
        
        # Сбрасываем подкрутку и открутку
        async with async_session_maker() as session:
            target.rig_until = None
            target.unrig_until = None
            await session.commit()
        
        # Красивое сообщение об успехе
        success_text = f"🔧 <b>ПОДКРУТКА И ОТКРУТКА ОТКЛЮЧЕНЫ!</b> 🔧\n\n"
        success_text += f"👤 Пользователь: <code>{target_id}</code>\n"
        success_text += f"🎰 Статус: <b>Обычная игра</b>\n\n"
        success_text += f"✅ Все модификации отключены"
        
        await message.answer(success_text)
        
    except Exception as e:
        print(f"Disable rig command error: {e}")
        await message.answer("❌ Произошла ошибка при отключении подкрутки/открутки. Попробуйте позже.")


# --- КОМАНДА ОГРАБЛЕНИЯ ---

@router.message(lambda message: message.text and message.text.lower().startswith('ограбить '))
async def rob_user_command(message: Message):
    """Обрабатывает команду 'ограбить [айди пользователя]'"""
    try:
        # Проверка блокировки
        if await check_if_banned(message):
            return
        
        # Парсим команду
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат команды!\n\n"
                              "Используйте: <b>ограбить [ID пользователя]</b>\n\n"
                              "Пример: <code>ограбить 123456789</code>")
            return
        
        try:
            target_id = int(parts[1])
            if target_id <= 0:
                await message.answer("❌ Неверный ID пользователя!")
                return
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя!")
            return
        
        # Проверяем что пользователь не пытается ограбить сам себя
        if target_id == message.from_user.id:
            await message.answer("❌ Нельзя ограбить самого себя!")
            return
        
        # Проверяем что цель не бот
        if target_id == message.bot.id:
            await message.answer("❌ Нельзя ограбить бота!")
            return
        
        await start_rob_process(message, target_id)
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при попытке ограбления. Попробуйте позже.")
        print(f"Rob command error: {e}")


@router.message(lambda message: message.reply_to_message and message.text and message.text.lower() == 'ограбить')
async def rob_user_reply_command(message: Message):
    """Обрабатывает команду 'ограбить' в ответ на сообщение пользователя"""
    try:
        # Проверка блокировки
        if await check_if_banned(message):
            return
        
        # Проверяем что реплай не на бота
        if message.reply_to_message.from_user.is_bot:
            await message.answer("❌ Нельзя ограбить бота!")
            return
        
        # Проверяем что пользователь не пытается ограбить сам себя
        if message.reply_to_message.from_user.id == message.from_user.id:
            await message.answer("❌ Нельзя ограбить самого себя!")
            return
        
        target_id = message.reply_to_message.from_user.id
        await start_rob_process(message, target_id)
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при попытке ограбления. Попробуйте позже.")
        print(f"Rob reply error: {e}")


async def start_rob_process(message: Message, target_id: int):
    """Запускает процесс ограбления"""
    try:
        from src.database import async_session_maker
        from src.models import User
        from datetime import datetime, timedelta
        
        # Получаем данные пользователей
        async with async_session_maker() as session:
            # Получаем грабителя
            robber_query = select(User).where(User.telegram_id == message.from_user.id)
            robber_result = await session.execute(robber_query)
            robber = robber_result.scalar_one_or_none()
            
            if not robber:
                await message.answer("❌ Ошибка: ваш аккаунт не найден в системе!")
                return
            
            # Получаем цель
            target_query = select(User).where(User.telegram_id == target_id)
            target_result = await session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if not target:
                await message.answer("❌ Пользователь с таким ID не найден в системе!")
                return
        
        # Проверяем лимит ограблений (раз в сутки)
        last_rob_time = getattr(robber, 'last_rob_time', None)
        if last_rob_time:
            time_since_last_rob = datetime.utcnow() - last_rob_time
            if time_since_last_rob.total_seconds() < 86400:  # 24 часа
                hours_left = int((86400 - time_since_last_rob.total_seconds()) / 3600)
                await message.answer(f"⏰ Ограбление доступно раз в сутки!\n\n"
                                  f"⏳ Следующее ограбление через: <b>{hours_left} часов</b>")
                return
        
        # Получаем балансы
        robber_balance = await wallet_service.get_balance(robber.id)
        target_balance = await wallet_service.get_balance(target.id)
        
        # Проверяем минимальный баланс грабителя (нужно хотя бы $10 для штрафа)
        if robber_balance < 1000:  # $10 в центах
            await message.answer("❌ Недостаточно средств для ограбления!\n\n"
                              f"💰 Минимальный баланс: <b>$10.00</b>\n"
                              f"💵 Ваш баланс: <b>${format_money(robber_balance)}</b>")
            return
        
        # Проверяем что у цели есть деньги для ограбления
        if target_balance < 100:  # $1 в центах
            await message.answer("❌ У этого пользователя нет денег для ограбления!")
            return
        
        # Начинаем процесс ограбления
        await message.answer(f"🔫 <b>Начат процесс ограбления пользователя {target_id}...</b>\n\n"
                          f"⏳ Подготовка к ограблению... 0%")
        
        # Анимация прогресса
        progress_msg = await message.answer("⏳ Подготовка к ограблению... 0%")
        
        for progress in range(0, 101, 5):
            await asyncio.sleep(0.1)  # Быстрая анимация
            
            if progress < 30:
                status = "🔍 Разведка..."
            elif progress < 60:
                status = "🚗 Подход к цели..."
            elif progress < 90:
                status = "🔓 Взлом защиты..."
            else:
                status = "💰 Захват денег..."
            
            try:
                await progress_msg.edit_text(f"🔫 <b>Начат процесс ограбления пользователя {target_id}...</b>\n\n"
                                          f"{status} {progress}%")
            except Exception:
                # Если не удалось отредактировать, продолжаем
                pass
        
        # Красивая анимация завершения
        await asyncio.sleep(0.5)
        
        # Определяем результат ограбления
        rob_success = random.random() < 0.25  # 25% шанс успеха
        
        try:
            if rob_success:
                # Успешное ограбление
                stolen_amount = int(target_balance * 0.3)  # 30% от баланса цели
                
                # Проверяем что у цели достаточно средств
                if stolen_amount > target_balance:
                    stolen_amount = target_balance
                
                # Списываем с цели
                await wallet_service.debit(target.id, stolen_amount, f"robbed_by_{message.from_user.id}")
                
                # Зачисляем грабителю
                await wallet_service.credit(robber.id, stolen_amount, f"robbed_from_{target_id}")
                
                # Обновляем время последнего ограбления
                async with async_session_maker() as session:
                    robber.last_rob_time = datetime.utcnow()
                    await session.commit()
                
                # Получаем новые балансы
                new_robber_balance = await wallet_service.get_balance(robber.id)
                
                # Красивое сообщение об успехе
                success_text = f"🎉 <b>ОГРАБЛЕНИЕ УСПЕШНО!</b> 🎉\n\n"
                success_text += f"💰 Украдено: <b>${format_money(stolen_amount)}</b>\n"
                success_text += f"🎯 Жертва: <code>{target_id}</code>\n"
                success_text += f"💵 Ваш баланс: <b>${format_money(new_robber_balance)}</b>\n\n"
                success_text += f"⏰ Следующее ограбление через 24 часа"
                
                try:
                    await progress_msg.edit_text(success_text)
                except Exception:
                    await message.answer(success_text)
                
                # Отправляем уведомление жертве
                try:
                    victim_text = f"🚨 <b>Вас ограбили!</b> 🚨\n\n"
                    victim_text += f"💰 Потеряно: <b>${format_money(stolen_amount)}</b>\n"
                    victim_text += f"🔫 Грабитель: @{message.from_user.username or message.from_user.first_name}\n"
                    victim_text += f"💵 Ваш баланс: <b>${format_money(await wallet_service.get_balance(target.id))}</b>"
                    
                    await message.bot.send_message(target_id, victim_text)
                except Exception:
                    # Если не удалось отправить уведомление жертве
                    pass
                    
            else:
                # Неудачное ограбление
                penalty_amount = int(robber_balance * 0.1)  # 10% штраф
                
                # Проверяем что у грабителя достаточно средств для штрафа
                if penalty_amount > robber_balance:
                    penalty_amount = robber_balance
                
                # Списываем штраф с грабителя
                await wallet_service.debit(robber.id, penalty_amount, f"rob_failed_penalty")
                
                # Обновляем время последнего ограбления
                async with async_session_maker() as session:
                    robber.last_rob_time = datetime.utcnow()
                    await session.commit()
                
                # Получаем новый баланс
                new_robber_balance = await wallet_service.get_balance(robber.id)
                
                # Красивое сообщение о неудаче
                fail_text = f"💥 <b>ОГРАБЛЕНИЕ ПРОВАЛИЛОСЬ!</b> 💥\n\n"
                fail_text += f"🚔 Вас поймали полицейские!\n"
                fail_text += f"💸 Штраф: <b>${format_money(penalty_amount)}</b>\n"
                fail_text += f"💵 Ваш баланс: <b>${format_money(new_robber_balance)}</b>\n\n"
                fail_text += f"⏰ Следующее ограбление через 24 часа"
                
                try:
                    await progress_msg.edit_text(fail_text)
                except Exception:
                    await message.answer(fail_text)
                    
        except ValueError as e:
            if "Insufficient funds" in str(e):
                await message.answer("❌ Недостаточно средств для завершения ограбления!")
            else:
                await message.answer("❌ Ошибка при обработке средств!")
        except Exception as e:
            print(f"Robbery transaction error: {e}")
            await message.answer("❌ Ошибка при обработке транзакции!")
            
    except Exception as e:
        await message.answer("❌ Произошла ошибка при ограблении. Попробуйте позже.")
        print(f"Rob process error: {e}")
