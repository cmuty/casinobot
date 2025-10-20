from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database import Base


class User(Base):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default='en')
    
    # НОВОЕ: Поле для персональности
    personality: Mapped[str] = mapped_column(String(20), default='playful')
    
    # Статусы
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    received_starter_bonus: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # VIP бонусы
    vip_cashback_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_cashback_percentage: Mapped[int] = mapped_column(Integer, default=10)  # 10% возврат
    vip_multiplier_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_multiplier_value: Mapped[float] = mapped_column(Integer, default=130)  # 1.3x множитель (130%)
    
    # Бонусы
    last_bonus_claimed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    bonus_streak: Mapped[int] = mapped_column(Integer, default=0)
    
    # Ограбления
    last_rob_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Подкрутка
    rig_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    unrig_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Nonce для Provably Fair
    slots_nonce: Mapped[int] = mapped_column(Integer, default=0)
    dice_nonce: Mapped[int] = mapped_column(Integer, default=0)
    roulette_nonce: Mapped[int] = mapped_column(Integer, default=0)
    
    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="user", uselist=False)
    bets: Mapped[list["Bet"]] = relationship("Bet", back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")