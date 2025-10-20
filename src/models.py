from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database import Base
from src.config import settings

# --- Пользователь ---
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default='en')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    last_bonus_claimed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    bonus_streak: Mapped[int] = mapped_column(Integer, default=0)
    slots_nonce: Mapped[int] = mapped_column(Integer, default=0)
    mines_nonce: Mapped[int] = mapped_column(Integer, default=0)
    received_starter_bonus: Mapped[bool] = mapped_column(Boolean, default=False)

    # НОВОЕ: Поле для персональности
    personality: Mapped[str] = mapped_column(String(20), default='playful')

    # Связи
    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    bets: Mapped[list["Bet"]] = relationship("Bet", back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    achievements: Mapped[list["UserAchievement"]] = relationship("UserAchievement", back_populates="user")


# --- Кошелёк ---
class Wallet(Base):
    __tablename__ = 'wallets'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    balance_cents: Mapped[int] = mapped_column(Integer, default=0)  # Баланс в центах

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="wallet")


# --- Ставки ---
class Bet(Base):
    __tablename__ = 'bets'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Для /top
    game_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'slots', 'dice', 'roulette'
    stake_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # Ставка в центах
    payout_cents: Mapped[int] = mapped_column(Integer, default=0)  # Выплата в центах
    result: Mapped[str] = mapped_column(String(255), nullable=True)  # Результат игры
    status: Mapped[str] = mapped_column(String(20), default='pending')  # 'pending', 'completed'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="bets")


# --- Транзакции ---
class Transaction(Base):
    __tablename__ = 'transactions'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'credit', 'debit', 'bonus', etc.
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # Сумма в центах
    status: Mapped[str] = mapped_column(String(20), default='pending')  # 'pending', 'completed', 'failed'
    meta: Mapped[str] = mapped_column(String(255), nullable=True)  # Дополнительная информация
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="transactions")


# --- Достижения ---
# Уже есть в achievement.py, но я вставлю сюда для полноты
class UserAchievement(Base):
    __tablename__ = 'user_achievements'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Код достижения
    achievement_code: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Временная метка
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="achievements")