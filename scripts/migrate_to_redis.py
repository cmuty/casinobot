#!/usr/bin/env python3
"""
Скрипт для миграции данных из MySQL в Redis
Запускать только один раз при переходе на Redis
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Импорты для старой MySQL базы
from src.database import async_session_maker, init_db as init_mysql_db, close_db as close_mysql_db
from src.models import User as MySQLUser, Wallet as MySQLWallet, Bet as MySQLBet, Transaction as MySQLTransaction

# Импорты для новой Redis базы
from src.redis_db import init_redis, close_redis, db
from src.models_redis import User, Wallet, Bet, Transaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_users():
    """Миграция пользователей"""
    logger.info("🔄 Начинаем миграцию пользователей...")
    
    async with async_session_maker() as session:
        result = await session.execute(select(MySQLUser))
        mysql_users = result.scalars().all()
        
        migrated_count = 0
        for mysql_user in mysql_users:
            try:
                # Создаем пользователя для Redis
                redis_user = User(
                    telegram_id=mysql_user.telegram_id,
                    username=mysql_user.username,
                    first_name=mysql_user.first_name,
                    last_name=mysql_user.last_name,
                    language_code=mysql_user.language_code,
                    personality=mysql_user.personality,
                    is_vip=mysql_user.is_vip,
                    is_banned=mysql_user.is_banned,
                    received_starter_bonus=mysql_user.received_starter_bonus,
                    vip_cashback_enabled=mysql_user.vip_cashback_enabled,
                    vip_cashback_percentage=mysql_user.vip_cashback_percentage,
                    vip_multiplier_enabled=mysql_user.vip_multiplier_enabled,
                    vip_multiplier_value=mysql_user.vip_multiplier_value,
                    last_bonus_claimed_at=mysql_user.last_bonus_claimed_at,
                    bonus_streak=mysql_user.bonus_streak,
                    last_rob_time=mysql_user.last_rob_time,
                    rig_until=mysql_user.rig_until,
                    unrig_until=mysql_user.unrig_until,
                    slots_nonce=mysql_user.slots_nonce,
                    dice_nonce=mysql_user.dice_nonce,
                    roulette_nonce=mysql_user.roulette_nonce,
                    created_at=mysql_user.created_at,
                    updated_at=mysql_user.updated_at,
                    last_seen_at=mysql_user.last_seen_at
                )
                
                await db.set_user(mysql_user.telegram_id, redis_user.to_dict())
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка миграции пользователя {mysql_user.telegram_id}: {e}")
        
        logger.info(f"✅ Мигрировано пользователей: {migrated_count}")


async def migrate_wallets():
    """Миграция кошельков"""
    logger.info("🔄 Начинаем миграцию кошельков...")
    
    async with async_session_maker() as session:
        result = await session.execute(select(MySQLWallet))
        mysql_wallets = result.scalars().all()
        
        migrated_count = 0
        for mysql_wallet in mysql_wallets:
            try:
                # Создаем кошелек для Redis
                redis_wallet = Wallet(
                    user_id=mysql_wallet.user_id,
                    balance_cents=mysql_wallet.balance_cents,
                    currency=mysql_wallet.currency,
                    created_at=mysql_wallet.created_at,
                    updated_at=mysql_wallet.updated_at
                )
                
                await db.set_wallet(mysql_wallet.user_id, redis_wallet.to_dict())
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка миграции кошелька {mysql_wallet.user_id}: {e}")
        
        logger.info(f"✅ Мигрировано кошельков: {migrated_count}")


async def migrate_bets():
    """Миграция ставок"""
    logger.info("🔄 Начинаем миграцию ставок...")
    
    async with async_session_maker() as session:
        result = await session.execute(select(MySQLBet))
        mysql_bets = result.scalars().all()
        
        migrated_count = 0
        for mysql_bet in mysql_bets:
            try:
                # Создаем ставку для Redis
                redis_bet = Bet(
                    user_id=mysql_bet.user_id,
                    chat_id=mysql_bet.chat_id,
                    game_type=mysql_bet.game_type,
                    stake_cents=mysql_bet.stake_cents,
                    payout_cents=mysql_bet.payout_cents,
                    result=mysql_bet.result,
                    server_seed=mysql_bet.server_seed,
                    nonce=mysql_bet.nonce,
                    status=mysql_bet.status,
                    created_at=mysql_bet.created_at
                )
                
                await db.add_bet(redis_bet.to_dict())
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка миграции ставки {mysql_bet.id}: {e}")
        
        logger.info(f"✅ Мигрировано ставок: {migrated_count}")


async def migrate_transactions():
    """Миграция транзакций"""
    logger.info("🔄 Начинаем миграцию транзакций...")
    
    async with async_session_maker() as session:
        result = await session.execute(select(MySQLTransaction))
        mysql_transactions = result.scalars().all()
        
        migrated_count = 0
        for mysql_transaction in mysql_transactions:
            try:
                # Создаем транзакцию для Redis
                redis_transaction = Transaction(
                    user_id=mysql_transaction.user_id,
                    type=mysql_transaction.type,
                    amount_cents=mysql_transaction.amount_cents,
                    status=mysql_transaction.status,
                    meta=mysql_transaction.meta,
                    created_at=mysql_transaction.created_at
                )
                
                await db.add_transaction(redis_transaction.to_dict())
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка миграции транзакции {mysql_transaction.id}: {e}")
        
        logger.info(f"✅ Мигрировано транзакций: {migrated_count}")


async def main():
    """Главная функция миграции"""
    logger.info("🚀 Начинаем миграцию данных из MySQL в Redis...")
    
    try:
        # Инициализация MySQL
        await init_mysql_db()
        logger.info("✅ MySQL подключение установлено")
        
        # Инициализация Redis
        await init_redis()
        logger.info("✅ Redis подключение установлено")
        
        # Выполняем миграцию
        await migrate_users()
        await migrate_wallets()
        await migrate_bets()
        await migrate_transactions()
        
        logger.info("🎉 Миграция завершена успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
    finally:
        # Закрываем соединения
        await close_mysql_db()
        await close_redis()
        logger.info("✅ Соединения закрыты")


if __name__ == "__main__":
    asyncio.run(main())
