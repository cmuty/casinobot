from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import json


@dataclass
class User:
    """Модель пользователя для Redis"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = 'en'
    personality: str = 'playful'
    
    # Статусы
    is_vip: bool = False
    is_banned: bool = False
    received_starter_bonus: bool = False
    
    # VIP бонусы
    vip_cashback_enabled: bool = False
    vip_cashback_percentage: int = 10
    vip_multiplier_enabled: bool = False
    vip_multiplier_value: float = 1.3
    
    # Бонусы
    last_bonus_claimed_at: Optional[datetime] = None
    bonus_streak: int = 0
    
    # Ограбления
    last_rob_time: Optional[datetime] = None
    
    # Подкрутка
    rig_until: Optional[datetime] = None
    unrig_until: Optional[datetime] = None
    
    # Nonce для Provably Fair
    slots_nonce: int = 0
    dice_nonce: int = 0
    roulette_nonce: int = 0
    
    # Метаданные
    created_at: datetime = None
    updated_at: datetime = None
    last_seen_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.last_seen_at is None:
            self.last_seen_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Создать из словаря"""
        # Обработка datetime полей
        for field in ['last_bonus_claimed_at', 'last_rob_time', 'rig_until', 'unrig_until', 'created_at', 'updated_at', 'last_seen_at']:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    data[field] = None
        
        return cls(**data)


@dataclass
class Wallet:
    """Модель кошелька для Redis"""
    user_id: int
    balance_cents: int = 0
    currency: str = 'USD'
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Wallet':
        """Создать из словаря"""
        # Обработка datetime полей
        for field in ['created_at', 'updated_at']:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    data[field] = None
        
        return cls(**data)


@dataclass
class Bet:
    """Модель ставки для Redis"""
    user_id: int
    chat_id: int
    game_type: str
    stake_cents: int
    payout_cents: int = 0
    result: Optional[str] = None
    server_seed: Optional[str] = None
    nonce: Optional[int] = None
    status: str = 'completed'
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Bet':
        """Создать из словаря"""
        # Обработка datetime полей
        if data.get('created_at') and isinstance(data['created_at'], str):
            try:
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            except ValueError:
                data['created_at'] = None
        
        return cls(**data)


@dataclass
class Transaction:
    """Модель транзакции для Redis"""
    user_id: int
    type: str
    amount_cents: int
    status: str = 'completed'
    meta: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Transaction':
        """Создать из словаря"""
        # Обработка datetime полей
        if data.get('created_at') and isinstance(data['created_at'], str):
            try:
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            except ValueError:
                data['created_at'] = None
        
        return cls(**data)


@dataclass
class Rating:
    """Модель рейтинга для Redis"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    total_wagered: int = 0
    total_won: int = 0
    games_played: int = 0
    win_rate: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Rating':
        """Создать из словаря"""
        # Обработка datetime полей
        for field in ['created_at', 'updated_at']:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    data[field] = None
        
        return cls(**data)
