import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from src.config import settings

logger = logging.getLogger(__name__)

# Глобальная переменная для Redis соединения
redis_client: Optional[redis.Redis] = None


class RedisDatabase:
    """Класс для работы с Redis базой данных"""
    
    def __init__(self):
        self.client = None
    
    async def connect(self):
        """Подключение к Redis"""
        global redis_client
        try:
            self.client = redis.from_url(
                settings.REDIS_CONNECTION_URL,
                encoding="utf-8",
                decode_responses=True
            )
            redis_client = self.client
            # Тестируем подключение
            await self.client.ping()
            logger.info("✅ Redis подключение установлено")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Redis: {e}")
            raise
    
    async def disconnect(self):
        """Отключение от Redis"""
        if self.client:
            await self.client.close()
            logger.info("✅ Redis соединение закрыто")
    
    async def set_user(self, user_id: int, user_data: Dict[str, Any], ttl: Optional[int] = None):
        """Сохранить данные пользователя"""
        key = f"user:{user_id}"
        data = json.dumps(user_data, default=str)
        if ttl:
            await self.client.setex(key, ttl, data)
        else:
            await self.client.set(key, data)
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя"""
        key = f"user:{user_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def delete_user(self, user_id: int):
        """Удалить пользователя"""
        key = f"user:{user_id}"
        await self.client.delete(key)
    
    async def set_wallet(self, user_id: int, wallet_data: Dict[str, Any]):
        """Сохранить данные кошелька"""
        key = f"wallet:{user_id}"
        data = json.dumps(wallet_data, default=str)
        await self.client.set(key, data)
    
    async def get_wallet(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные кошелька"""
        key = f"wallet:{user_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def add_bet(self, bet_data: Dict[str, Any]) -> str:
        """Добавить ставку"""
        bet_id = f"bet:{datetime.utcnow().timestamp()}:{bet_data['user_id']}"
        data = json.dumps(bet_data, default=str)
        await self.client.set(bet_id, data)
        return bet_id
    
    async def get_user_bets(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить ставки пользователя"""
        pattern = f"bet:*:{user_id}"
        keys = await self.client.keys(pattern)
        keys.sort(reverse=True)  # Сортируем по убыванию (новые сначала)
        
        bets = []
        for key in keys[:limit]:
            data = await self.client.get(key)
            if data:
                bet = json.loads(data)
                bet['id'] = key
                bets.append(bet)
        
        return bets
    
    async def add_transaction(self, transaction_data: Dict[str, Any]) -> str:
        """Добавить транзакцию"""
        transaction_id = f"transaction:{datetime.utcnow().timestamp()}:{transaction_data['user_id']}"
        data = json.dumps(transaction_data, default=str)
        await self.client.set(transaction_id, data)
        return transaction_id
    
    async def get_user_transactions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить транзакции пользователя"""
        pattern = f"transaction:*:{user_id}"
        keys = await self.client.keys(pattern)
        keys.sort(reverse=True)  # Сортируем по убыванию (новые сначала)
        
        transactions = []
        for key in keys[:limit]:
            data = await self.client.get(key)
            if data:
                transaction = json.loads(data)
                transaction['id'] = key
                transactions.append(transaction)
        
        return transactions
    
    async def increment_balance(self, user_id: int, amount_cents: int) -> int:
        """Увеличить баланс пользователя"""
        key = f"wallet:{user_id}"
        new_balance = await self.client.hincrby(key, "balance_cents", amount_cents)
        return new_balance
    
    async def decrement_balance(self, user_id: int, amount_cents: int) -> int:
        """Уменьшить баланс пользователя"""
        key = f"wallet:{user_id}"
        new_balance = await self.client.hincrby(key, "balance_cents", -amount_cents)
        return new_balance
    
    async def get_balance(self, user_id: int) -> int:
        """Получить баланс пользователя"""
        key = f"wallet:{user_id}"
        balance = await self.client.hget(key, "balance_cents")
        return int(balance) if balance else 0
    
    async def set_user_field(self, user_id: int, field: str, value: Any):
        """Установить поле пользователя"""
        key = f"user:{user_id}"
        await self.client.hset(key, field, json.dumps(value, default=str))
    
    async def get_user_field(self, user_id: int, field: str) -> Any:
        """Получить поле пользователя"""
        key = f"user:{user_id}"
        value = await self.client.hget(key, field)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    async def set_expiring_key(self, key: str, value: Any, ttl_seconds: int):
        """Установить ключ с TTL"""
        data = json.dumps(value, default=str)
        await self.client.setex(key, ttl_seconds, data)
    
    async def get_expiring_key(self, key: str) -> Any:
        """Получить значение ключа с TTL"""
        data = await self.client.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None
    
    async def delete_key(self, key: str):
        """Удалить ключ"""
        await self.client.delete(key)
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей"""
        pattern = "user:*"
        keys = await self.client.keys(pattern)
        
        users = []
        for key in keys:
            data = await self.client.get(key)
            if data:
                user = json.loads(data)
                user['id'] = key.split(':')[1]
                users.append(user)
        
        return users
    
    async def get_user_count(self) -> int:
        """Получить количество пользователей"""
        pattern = "user:*"
        keys = await self.client.keys(pattern)
        return len(keys)


# Глобальный экземпляр базы данных
db = RedisDatabase()


async def init_redis():
    """Инициализация Redis"""
    await db.connect()


async def close_redis():
    """Закрытие Redis соединения"""
    await db.disconnect()


async def get_redis() -> RedisDatabase:
    """Получить экземпляр Redis базы данных"""
    return db
