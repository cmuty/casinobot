from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database import Base


class Bet(Base):
    __tablename__ = 'bets'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # Игра
    game_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Финансы
    stake_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payout_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # Результат
    result: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Provably Fair
    server_seed: Mapped[str] = mapped_column(String(128), nullable=True)
    nonce: Mapped[int] = mapped_column(BigInteger, nullable=True)
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default='completed')
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bets")
    
    __table_args__ = (
        Index('idx_user_game', 'user_id', 'game_type'),
    )