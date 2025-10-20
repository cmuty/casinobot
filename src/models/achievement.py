from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from src.database import Base


class UserAchievement(Base):
    __tablename__ = 'user_achievements'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Код достижения
    achievement_code: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Временная метка
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)