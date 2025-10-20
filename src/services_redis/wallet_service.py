from typing import Optional
from src.redis_db import db
from src.models_redis import Wallet, Transaction
import logging

logger = logging.getLogger(__name__)


class WalletService:
    """Сервис для работы с кошельками в Redis"""
    
    @staticmethod
    async def get_or_create_wallet(user_id: int) -> Wallet:
        """Получить или создать кошелёк"""
        wallet_data = await db.get_wallet(user_id)
        
        if not wallet_data:
            wallet = Wallet(user_id=user_id, balance_cents=0)
            await db.set_wallet(user_id, wallet.to_dict())
            return wallet
        
        return Wallet.from_dict(wallet_data)
    
    @staticmethod
    async def get_balance(user_id: int) -> int:
        """Получить баланс пользователя"""
        return await db.get_balance(user_id)
    
    @staticmethod
    async def credit(user_id: int, amount_cents: int, reason: str) -> Transaction:
        """Начислить средства"""
        # Увеличиваем баланс
        new_balance = await db.increment_balance(user_id, amount_cents)
        
        # Создаём транзакцию
        transaction = Transaction(
            user_id=user_id,
            type='credit',
            amount_cents=amount_cents,
            status='completed',
            meta=reason
        )
        
        await db.add_transaction(transaction.to_dict())
        
        logger.info(f"💰 Credit: user={user_id}, amount={amount_cents}, reason={reason}, new_balance={new_balance}")
        
        return transaction
    
    @staticmethod
    async def debit(user_id: int, amount_cents: int, reason: str) -> Transaction:
        """Списать средства"""
        current_balance = await db.get_balance(user_id)
        
        if current_balance < amount_cents:
            raise ValueError("Insufficient funds")
        
        # Уменьшаем баланс
        new_balance = await db.decrement_balance(user_id, amount_cents)
        
        # Создаём транзакцию
        transaction = Transaction(
            user_id=user_id,
            type='debit',
            amount_cents=amount_cents,
            status='completed',
            meta=reason
        )
        
        await db.add_transaction(transaction.to_dict())
        
        logger.info(f"💸 Debit: user={user_id}, amount={amount_cents}, reason={reason}, new_balance={new_balance}")
        
        return transaction
    
    @staticmethod
    async def add_funds(user_id: int, amount_cents: int, reason: str) -> Transaction:
        """Добавить средства (алиас для credit)"""
        return await WalletService.credit(user_id, amount_cents, reason)
    
    @staticmethod
    async def set_balance(user_id: int, new_balance_cents: int):
        """Установить новый баланс пользователя (для админа)"""
        wallet = await WalletService.get_or_create_wallet(user_id)
        wallet.balance_cents = new_balance_cents
        wallet.updated_at = wallet.updated_at
        
        await db.set_wallet(user_id, wallet.to_dict())
        
        logger.info(f"✏️ Set balance: user={user_id}, new_balance={new_balance_cents}")


wallet_service = WalletService()
