from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import User, Wallet, Transaction
import logging

logger = logging.getLogger(__name__)


class WalletService:
    """Сервис для работы с кошельками"""
    
    @staticmethod
    async def get_or_create_wallet(user_id: int) -> Wallet:
        """Получить или создать кошелёк"""
        from src.database import async_session_maker
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(Wallet).where(Wallet.user_id == user_id)
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                wallet = Wallet(user_id=user_id, balance_cents=0)
                session.add(wallet)
                await session.commit()
                await session.refresh(wallet)
            
            return wallet
    
    @staticmethod
    async def get_balance(user_id: int) -> int:
        """Получить баланс пользователя"""
        wallet = await WalletService.get_or_create_wallet(user_id)
        return wallet.balance_cents
    
    @staticmethod
    async def credit(user_id: int, amount_cents: int, reason: str):
        """Начислить средства"""
        from src.database import async_session_maker
        
        async with async_session_maker() as session:
            # Получаем кошелёк
            result = await session.execute(
                select(Wallet).where(Wallet.user_id == user_id)
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                wallet = Wallet(user_id=user_id, balance_cents=0)
                session.add(wallet)
            
            # Обновляем баланс
            wallet.balance_cents += amount_cents
            
            # Создаём транзакцию
            transaction = Transaction(
                user_id=user_id,
                type='credit',
                amount_cents=amount_cents,
                status='completed',
                meta=reason
            )
            session.add(transaction)
            
            await session.commit()
            await session.refresh(transaction)
            
            logger.info(f"💰 Credit: user={user_id}, amount={amount_cents}, reason={reason}")
            
            return transaction
    
    @staticmethod
    async def debit(user_id: int, amount_cents: int, reason: str):
        """Списать средства"""
        from src.database import async_session_maker
        
        async with async_session_maker() as session:
            # Получаем кошелёк
            result = await session.execute(
                select(Wallet).where(Wallet.user_id == user_id)
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet or wallet.balance_cents < amount_cents:
                raise ValueError("Insufficient funds")
            
            # Обновляем баланс
            wallet.balance_cents -= amount_cents
            
            # Создаём транзакцию
            transaction = Transaction(
                user_id=user_id,
                type='debit',
                amount_cents=amount_cents,
                status='completed',
                meta=reason
            )
            session.add(transaction)
            
            await session.commit()
            await session.refresh(transaction)
            
            logger.info(f"💸 Debit: user={user_id}, amount={amount_cents}, reason={reason}")
            
            return transaction
    
    @staticmethod
    async def add_funds(user_id: int, amount_cents: int, reason: str):
        """Добавить средства (алиас для credit)"""
        return await WalletService.credit(user_id, amount_cents, reason)
    
    @staticmethod
    async def set_balance(user_id: int, new_balance_cents: int):
        """Установить новый баланс пользователя (для админа)"""
        from src.database import async_session_maker
        
        async with async_session_maker() as session:
            # Получаем кошелёк
            result = await session.execute(
                select(Wallet).where(Wallet.user_id == user_id)
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                wallet = Wallet(user_id=user_id, balance_cents=new_balance_cents)
                session.add(wallet)
            else:
                wallet.balance_cents = new_balance_cents
            
            await session.commit()
            
            logger.info(f"✏️ Set balance: user={user_id}, new_balance={new_balance_cents}")


wallet_service = WalletService()