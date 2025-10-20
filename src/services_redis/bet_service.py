from typing import Dict, List
from src.redis_db import db
from src.models_redis import Bet
from src.services_redis.wallet_service import wallet_service
import logging

logger = logging.getLogger(__name__)


class BetService:
    """Сервис для работы со ставками в Redis"""
    
    @staticmethod
    async def create_bet(
        user_id: int,
        chat_id: int,
        game_type: str,
        stake_cents: int
    ) -> Bet:
        """Создать ставку"""
        # Списываем средства
        await wallet_service.debit(user_id, stake_cents, f'bet:{game_type}')
        
        bet = Bet(
            user_id=user_id,
            chat_id=chat_id,
            game_type=game_type,
            stake_cents=stake_cents,
            status='pending'
        )
        
        bet_id = await db.add_bet(bet.to_dict())
        bet_dict = bet.to_dict()
        bet_dict['id'] = bet_id
        
        logger.info(f"🎰 Bet created: user={user_id}, game={game_type}, stake={stake_cents}")
        
        return Bet.from_dict(bet_dict)
    
    @staticmethod
    async def complete_bet(bet_id: str, result: str, payout_cents: int) -> Bet:
        """Завершить ставку"""
        # Получаем ставку по ID
        bet_data = await db.get_expiring_key(bet_id)
        if not bet_data:
            raise ValueError(f"Bet {bet_id} not found")
        
        bet = Bet.from_dict(bet_data)
        bet.result = result
        bet.payout_cents = payout_cents
        bet.status = 'completed'
        
        # Обновляем ставку
        await db.set_expiring_key(bet_id, bet.to_dict(), 86400)  # TTL 24 часа
        
        # Начисляем выигрыш
        if payout_cents > 0:
            await wallet_service.credit(
                bet.user_id,
                payout_cents,
                f'win:{bet.game_type}:{bet_id}'
            )
        
        logger.info(f"✅ Bet completed: id={bet_id}, payout={payout_cents}")
        
        return bet
    
    @staticmethod
    async def get_user_stats(user_id: int) -> Dict:
        """Получить статистику пользователя"""
        bets = await db.get_user_bets(user_id, limit=1000)  # Получаем больше ставок для статистики
        
        total_bets = len(bets)
        total_wagered = sum(bet['stake_cents'] for bet in bets)
        total_won = sum(bet['payout_cents'] for bet in bets)
        
        # Винрейт
        winrate = (total_won / total_wagered * 100) if total_wagered > 0 else 0
        
        return {
            'total_bets': total_bets,
            'total_wagered_cents': total_wagered,
            'total_won_cents': total_won,
            'winrate': round(winrate, 2)
        }
    
    @staticmethod
    async def get_user_bets(user_id: int, limit: int = 50) -> List[Bet]:
        """Получить ставки пользователя"""
        bets_data = await db.get_user_bets(user_id, limit)
        return [Bet.from_dict(bet_data) for bet_data in bets_data]


bet_service = BetService()
