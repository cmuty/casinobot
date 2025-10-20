from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
import json
from io import BytesIO
from datetime import datetime
from src.models import User, Bet, Transaction, UserAchievement, Wallet # Добавлен Wallet
from src.database import async_session_maker
from src.services.wallet_service import wallet_service
from src.services.bet_service import bet_service
# Импортируем клавиатуры
from src.utils.keyboards import get_settings_keyboard, get_main_menu_keyboard
from src.states import DeletionStates
from src.utils.ban_check import check_if_banned

# Нужно импортировать delete из sqlalchemy
from sqlalchemy import delete

router = Router()

# --- /settings (и ⚙️ Настройки как текстовый триггер) ---
# Работает везде, но в группах только информационное сообщение без клавиатуры
@router.message(Command('settings'))
async def cmd_settings(message: Message):
    """Команда /settings"""
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

    # Определяем язык пользователя (если в модели есть language_code, иначе по умолчанию 'ru')
    lang = getattr(user, 'language_code', 'ru')

    if message.chat.type in ['group', 'supergroup']:
        # В группе — только информационное сообщение без клавиатуры
        await message.answer("⚙️ <b>Настройки</b>\n\nЗдесь вы можете управлять своим аккаунтом.")
    else:
        # В ЛС — с клавиатурой
        await message.answer(
            "⚙️ <b>Настройки</b>\n\n"
            "Здесь вы можете управлять своим аккаунтом.",
            reply_markup=get_settings_keyboard(lang),
            parse_mode='HTML'
        )

# ТЕКСТОВЫЙ ТРИГГЕР для настроек - игнорируется в группах
@router.message(lambda message: message.text == '⚙️ Настройки')
async def trigger_settings(message: Message):
    """Обрабатывает текстовый триггер '⚙️ Настройки'"""
    # Проверяем тип чата: если группа — игнорируем (ничего не отвечаем)
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
        return
    
    # Проверка блокировки
    if await check_if_banned(message):
        return
    
    # Если ЛС - выполняем логику команды settings (без клавиатуры в группе, она и так не отправляется в ЛС)
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

    lang = getattr(user, 'language_code', 'ru')

    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Здесь вы можете управлять своим аккаунтом.",
        reply_markup=get_settings_keyboard(lang),
        parse_mode='HTML'
    )


# --- /export_data (и 📦 Экспорт данных как текстовый триггер) ---
# Работает только в ЛС. В группах — игнор.
@router.message(Command('export_data'))
async def cmd_export_data(message: Message):
    """Экспорт всех данных пользователя (GDPR)"""
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

        # Проверяем тип чата
        if message.chat.type in ['group', 'supergroup']:
            # В группе отправляем информационное сообщение
            await message.answer("📦 <b>Экспорт данных</b>\n\nЭкспорт данных доступен только в личных сообщениях с ботом.")
            return

        # Сборка данных
        data = {
            'user_info': {
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'language': user.language_code,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'is_vip': user.is_vip,
                'personality': getattr(user, 'personality', 'playful') # Теперь это поле есть
            },
            'wallet': {
                'balance': (await wallet_service.get_balance(user.id)) / 100,
                'currency': 'USD'
            },
            'statistics': {},
            'bets': [],
            'transactions': [],
            'achievements': []
        }

        # Статистика
        stats = await bet_service.get_user_stats(user.id)
        data['statistics'] = {
            'total_bets': stats['total_bets'],
            'total_wagered': stats['total_wagered_cents'] / 100,
            'total_won': stats['total_won_cents'] / 100,
            'win_rate': stats['winrate'],
        }

        # Ставки
        bets_result = await session.execute(
            select(Bet).where(Bet.user_id == user.id).order_by(Bet.created_at.desc()).limit(1000)
        )
        bets = bets_result.scalars().all()
        for bet in bets:
            data['bets'].append({
                'id': bet.id,
                'game_type': bet.game_type,
                'stake': bet.stake_cents / 100,
                'payout': bet.payout_cents / 100,
                'result': bet.result,
                'created_at': bet.created_at.isoformat()
            })

        # Транзакции
        transactions_result = await session.execute(
            select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(1000)
        )
        transactions = transactions_result.scalars().all()
        for tx in transactions:
            data['transactions'].append({
                'id': tx.id,
                'type': tx.type,
                'amount': tx.amount_cents / 100,
                'status': tx.status,
                'meta': tx.meta,
                'created_at': tx.created_at.isoformat()
            })

        # Достижения
        achievements_result = await session.execute(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        )
        achievements = achievements_result.scalars().all()
        for ach in achievements:
            data['achievements'].append({
                'code': ach.achievement_code,
                'unlocked_at': ach.unlocked_at.isoformat()
            })

        # Создание JSON файла
        json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str) # default=str для datetime

        buffer = BytesIO(json_data.encode('utf-8'))
        buffer.name = f"luckystar_data_{user.telegram_id}.json"

        from aiogram.types import BufferedInputFile
        file = BufferedInputFile(buffer.getvalue(), filename=buffer.name)

        await message.answer_document(
            document=file,
            caption="📦 Вот все твои данные в LuckyStar Casino.\n\nЭтот файл содержит полную информацию о твоей активности."
        )

# ТЕКСТОВЫЙ ТРИГГЕР для экспорта данных - игнорируется в группах
@router.message(lambda message: message.text == '📦 Экспорт данных')
async def trigger_export_data(message: Message):
    """Обрабатывает текстовый триггер '📦 Экспорт данных'"""
    # Проверяем тип чата: если группа — игнорируем (ничего не отвечаем)
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
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

        # Сборка данных (копия логики из cmd_export_data)
        data = {
            'user_info': {
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'language': user.language_code,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'is_vip': user.is_vip,
                'personality': getattr(user, 'personality', 'playful')
            },
            'wallet': {
                'balance': (await wallet_service.get_balance(user.id)) / 100,
                'currency': 'USD'
            },
            'statistics': {},
            'bets': [],
            'transactions': [],
            'achievements': []
        }

        stats = await bet_service.get_user_stats(user.id)
        data['statistics'] = {
            'total_bets': stats['total_bets'],
            'total_wagered': stats['total_wagered_cents'] / 100,
            'total_won': stats['total_won_cents'] / 100,
            'win_rate': stats['winrate'],
        }

        bets_result = await session.execute(
            select(Bet).where(Bet.user_id == user.id).order_by(Bet.created_at.desc()).limit(1000)
        )
        bets = bets_result.scalars().all()
        for bet in bets:
            data['bets'].append({
                'id': bet.id,
                'game_type': bet.game_type,
                'stake': bet.stake_cents / 100,
                'payout': bet.payout_cents / 100,
                'result': bet.result,
                'created_at': bet.created_at.isoformat()
            })

        transactions_result = await session.execute(
            select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(1000)
        )
        transactions = transactions_result.scalars().all()
        for tx in transactions:
            data['transactions'].append({
                'id': tx.id,
                'type': tx.type,
                'amount': tx.amount_cents / 100,
                'status': tx.status,
                'meta': tx.meta,
                'created_at': tx.created_at.isoformat()
            })

        achievements_result = await session.execute(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        )
        achievements = achievements_result.scalars().all()
        for ach in achievements:
            data['achievements'].append({
                'code': ach.achievement_code,
                'unlocked_at': ach.unlocked_at.isoformat()
            })

        json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)

        buffer = BytesIO(json_data.encode('utf-8'))
        buffer.name = f"luckystar_data_{user.telegram_id}.json"

        from aiogram.types import BufferedInputFile
        file = BufferedInputFile(buffer.getvalue(), filename=buffer.name)

        await message.answer_document(
            document=file,
            caption="📦 Вот все твои данные в LuckyStar Casino.\n\nЭтот файл содержит полную информацию о твоей активности."
        )


# --- /delete_account (и 🗑️ Удалить аккаунт как текстовый триггер) ---
# Работает только в ЛС. В группах — игнор.
@router.message(Command('delete_account'))
async def cmd_delete_account(message: Message, state: FSMContext):
    """Удаление аккаунта (GDPR)"""
    # Проверяем тип чата: если группа — игнорируем
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
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

    await state.set_state(DeletionStates.confirm)

    await message.answer(
        "⚠️ <b>Удаление аккаунта</b>\n\n"
        "Ты уверен, что хочешь удалить свой аккаунт?\n\n"
        "Будут удалены:\n"
        "• Профиль и баланс\n"
        "• История ставок\n"
        "• Достижения\n"
        "• Все персональные данные\n\n"
        "❗ Это действие необратимо!\n\n"
        "Для подтверждения введи: <code>DELETE MY ACCOUNT</code>",
        parse_mode='HTML'
    )

# ТЕКСТОВЫЙ ТРИГГЕР для удаления аккаунта - игнорируется в группах
@router.message(lambda message: message.text == '🗑️ Удалить аккаунт')
async def trigger_delete_account(message: Message, state: FSMContext):
    """Обрабатывает текстовый триггер '🗑️ Удалить аккаунт'"""
    # Проверяем тип чата: если группа — игнорируем (ничего не отвечаем)
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
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

    await state.set_state(DeletionStates.confirm)

    await message.answer(
        "⚠️ <b>Удаление аккаунта</b>\n\n"
        "Ты уверен, что хочешь удалить свой аккаунт?\n\n"
        "Будут удалены:\n"
        "• Профиль и баланс\n"
        "• История ставок\n"
        "• Достижения\n"
        "• Все персональные данные\n\n"
        "❗ Это действие необратимо!\n\n"
        "Для подтверждения введи: <code>DELETE MY ACCOUNT</code>",
        parse_mode='HTML'
    )


# --- FSM подтверждение удаления ---
# Работает только в ЛС. В группах — игнор.
@router.message(DeletionStates.confirm)
async def confirm_deletion(message: Message, state: FSMContext):
    """Подтверждение удаления"""
    # Проверяем тип чата: если группа — игнорируем
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
        await state.clear() # Сбросим состояние, чтобы не висело
        return

    from src.database import async_session_maker
    telegram_id = message.from_user.id

    if message.text != "DELETE MY ACCOUNT":
        await message.answer("❌ Неверное подтверждение. Удаление отменено.")
        await state.clear()
        return

    await message.answer("📦 Создаём финальный экспорт твоих данных...")

    # Экспорт данных (повторно) - ПОЛНОСТЬЮ КОПИРУЕМ КОД ИЗ cmd_export_data
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Пользователь не найден.")
            await state.clear()
            return

        # Сборка данных (повтор кода из cmd_export_data)
        data = {
            'user_info': {
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'language': user.language_code,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'is_vip': user.is_vip,
                'personality': getattr(user, 'personality', 'playful')
            },
            'wallet': {
                'balance': (await wallet_service.get_balance(user.id)) / 100,
                'currency': 'USD'
            },
            'statistics': {},
            'bets': [],
            'transactions': [],
            'achievements': []
        }

        stats = await bet_service.get_user_stats(user.id)
        data['statistics'] = {
            'total_bets': stats['total_bets'],
            'total_wagered': stats['total_wagered_cents'] / 100,
            'total_won': stats['total_won_cents'] / 100,
            'win_rate': stats['winrate'],
        }

        bets_result = await session.execute(
            select(Bet).where(Bet.user_id == user.id).order_by(Bet.created_at.desc()).limit(1000)
        )
        bets = bets_result.scalars().all()
        for bet in bets:
            data['bets'].append({
                'id': bet.id,
                'game_type': bet.game_type,
                'stake': bet.stake_cents / 100,
                'payout': bet.payout_cents / 100,
                'result': bet.result,
                'created_at': bet.created_at.isoformat()
            })

        transactions_result = await session.execute(
            select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(1000)
        )
        transactions = transactions_result.scalars().all()
        for tx in transactions:
            data['transactions'].append({
                'id': tx.id,
                'type': tx.type,
                'amount': tx.amount_cents / 100,
                'status': tx.status,
                'meta': tx.meta,
                'created_at': tx.created_at.isoformat()
            })

        achievements_result = await session.execute(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        )
        achievements = achievements_result.scalars().all()
        for ach in achievements:
            data['achievements'].append({
                'code': ach.achievement_code,
                'unlocked_at': ach.unlocked_at.isoformat()
            })

        json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        buffer = BytesIO(json_data.encode('utf-8'))
        buffer.name = f"luckystar_data_{user.telegram_id}_before_deletion.json"
        from aiogram.types import BufferedInputFile
        file = BufferedInputFile(buffer.getvalue(), filename=buffer.name)
        await message.answer_document(
            document=file,
            caption="📦 Финальный экспорт данных перед удалением."
        )

    # Удаление
    await message.answer("🗑️ Удаляем все данные...")

    # ПРАВИЛЬНОЕ УДАЛЕНИЕ:
    async with async_session_maker() as session:
        # 1. Удаляем транзакции
        await session.execute(
            delete(Transaction).where(Transaction.user_id == user.id)
        )
        # 2. Удаляем достижения (если есть)
        # await session.execute(
        #     delete(UserAchievement).where(UserAchievement.user_id == user.id)
        # )
        # 3. Удаляем ставки
        await session.execute(
            delete(Bet).where(Bet.user_id == user.id)
        )
        # 4. Удаляем кошелёк (важно удалить до пользователя, чтобы избежать проблем с ON DELETE CASCADE и обновлениями)
        await session.execute(
            delete(Wallet).where(Wallet.user_id == user.id)
        )
        # 5. Удаляем пользователя
        await session.execute(
            delete(User).where(User.telegram_id == telegram_id)
        )

        await session.commit() # Коммитим все удаления вместе

    await message.answer(
        "✅ Твой аккаунт успешно удалён.\n\n"
        "Спасибо, что был с нами! Если захочешь вернуться — мы всегда здесь. 👋"
    )

    await state.clear()

# --- "🔙 Назад" ---
# Работает только в ЛС. В группах — игнор.
@router.message(lambda message: message.text == '🔙 Назад')
async def cmd_back_to_main(message: Message):
    """Возврат в главное меню"""
    # Проверяем тип чата: если группа — игнорируем
    if message.chat.type in ['group', 'supergroup']:
        # Ничего не отправляем, просто игнорируем
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

    # Получаем баланс для сообщения (как в /balance)
    balance = await wallet_service.get_balance(user.id)
    lang = getattr(user, 'language_code', 'ru')

    text = f"🏠 Возвращено в <b>главное меню</b>"

    # Отправляем сообщение с главным меню (только в ЛС)
    await message.answer(
        text,
        reply_markup=get_main_menu_keyboard(lang), # Используем главное меню
        parse_mode='HTML'
    )
