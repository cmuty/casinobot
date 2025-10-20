from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database import Base


class UserRating(Base):
    """Рейтинг пользователей"""
    __tablename__ = 'user_ratings'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Статистика за период
    total_wins: Mapped[int] = mapped_column(Integer, default=0)
    total_losses: Mapped[int] = mapped_column(Integer, default=0)
    total_winnings: Mapped[int] = mapped_column(Integer, default=0)  # в центах
    total_bets: Mapped[int] = mapped_column(Integer, default=0)
    
    # Период рейтинга (daily, weekly, monthly)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Дата начала периода
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Дата последнего обновления
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User")


class LeaderboardReward(Base):
    """Награды за места в лидерборде"""
    __tablename__ = 'leaderboard_rewards'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Место в лидерборде
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Период (daily, weekly, monthly)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Размер награды в центах
    reward_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Дата получения награды
    rewarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Статус награды
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User")


class UserCredit(Base):
    """Кредиты пользователей"""
    __tablename__ = 'user_credits'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Размер кредита в центах
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Процент возврата (например, 1.1 = 110%)
    interest_rate: Mapped[float] = mapped_column(Float, default=1.1)
    
    # Дата выдачи кредита
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Дата погашения
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Статус кредита (active, paid, overdue)
    status: Mapped[str] = mapped_column(String(20), default='active')
    
    # Сумма к возврату в центах
    amount_to_repay: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Дата последнего обновления статуса
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User")


class CreditLimit(Base):
    """Лимиты кредитов для VIP"""
    __tablename__ = 'credit_limits'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Тип лимита (daily_1k, weekly_5k, monthly_15k)
    limit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Дата последнего использования
    last_used: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Количество использований
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
