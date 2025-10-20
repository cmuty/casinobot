from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database import Base


class Transaction(Base):
    __tablename__ = 'transactions'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False, index=True)
    
    # Тип транзакции
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Сумма
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default='completed')
    
    # Метаданные
    meta: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )