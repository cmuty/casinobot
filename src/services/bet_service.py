from sqlalchemy import select, func
from src.models import Bet, User
from src.services.wallet_service import wallet_service
import logging

logger = logging.getLogger(__name__)


class BetService:
    """Сервис для работы со ставками"""
    
    @staticmethod
    async def create_bet(
        user_id: int,
        chat_id: int,
        game_type: str,
        stake_cents: int
    ) -> Bet:
        """Создать ставку"""
        from src.database import async_session_maker
        
        # Списываем средства
        await wallet_service.debit(user_id, stake_cents, f'bet:{game_type}')
        
        async with async_session_maker() as session:
            bet = Bet(
                user_id=user_id,
                chat_id=chat_id,
                game_type=game_type,
                stake_cents=stake_cents,
                status='pending'
            )
            session.add(bet)
            await session.commit()
            await session.refresh(bet)
            
            logger.info(f"🎰 Bet created: user={user_id}, game={game_type}, stake={stake_cents}")
            
            return bet
    
    @staticmethod
    async def complete_bet(bet_id: int, result: str, payout_cents: int) -> Bet:
        """Завершить ставку"""
        from src.database import async_session_maker
        
        async with async_session_maker() as session:
            result_obj = await session.execute(
                select(Bet).where(Bet.id == bet_id)
            )
            bet = result_obj.scalar_one()
            
            bet.result = result
            bet.payout_cents = payout_cents
            bet.status = 'completed'
            
            # Начисляем выигрыш
            if payout_cents > 0:
                await wallet_service.credit(
                    bet.user_id,
                    payout_cents,
                    f'win:{bet.game_type}:{bet_id}'
                )
            
            await session.commit()
            await session.refresh(bet)
            
            logger.info(f"✅ Bet completed: id={bet_id}, payout={payout_cents}")
            
            return bet
    
    @staticmethod
    async def get_user_stats(user_id: int) -> dict:
        """Получить статистику пользователя"""
        from src.database import async_session_maker
        
        async with async_session_maker() as session:
            # Всего ставок
            total_bets = await session.execute(
                select(func.count(Bet.id)).where(Bet.user_id == user_id)
            )
            total_bets = total_bets.scalar() or 0
            
            # Всего поставлено
            total_wagered = await session.execute(
                select(func.sum(Bet.stake_cents)).where(Bet.user_id == user_id)
            )
            total_wagered = total_wagered.scalar() or 0
            
            # Всего выиграно
            total_won = await session.execute(
                select(func.sum(Bet.payout_cents)).where(Bet.user_id == user_id)
            )
            total_won = total_won.scalar() or 0
            
            # Винрейт
            winrate = (total_won / total_wagered * 100) if total_wagered > 0 else 0
            
            return {
                'total_bets': total_bets,
                'total_wagered_cents': total_wagered,
                'total_won_cents': total_won,
                'winrate': round(winrate, 2)
            }


bet_service = BetService()