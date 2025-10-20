"""
Сервис для работы с рейтингами и лидербордами
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload

from src.database import get_session
from src.models import User, Bet
from src.models.rating import UserRating, LeaderboardReward, UserCredit, CreditLimit
from src.services.wallet_service import wallet_service
from src.config import settings


class RatingService:
    """Сервис для работы с рейтингами"""
    
    @staticmethod
    async def update_user_rating(user_id: int, bet_amount: int, win_amount: int, period: str = 'daily') -> None:
        """Обновляет рейтинг пользователя"""
        period_start = RatingService._get_period_start(period)
        
        async for session in get_session():
            # Ищем существующий рейтинг
            result = await session.execute(
                select(UserRating).where(
                    and_(
                        UserRating.user_id == user_id,
                        UserRating.period == period,
                        UserRating.period_start == period_start
                    )
                )
            )
            rating = result.scalar_one_or_none()
            
            if not rating:
                # Создаем новый рейтинг
                rating = UserRating(
                    user_id=user_id,
                    period=period,
                    period_start=period_start,
                    total_wins=0,
                    total_losses=0,
                    total_winnings=0,
                    total_bets=0
                )
                session.add(rating)
            
            # Обновляем статистику
            rating.total_bets += 1
            if win_amount > 0:
                rating.total_wins += 1
                rating.total_winnings += win_amount
            else:
                rating.total_losses += 1
            
            rating.last_updated = datetime.utcnow()
            await session.commit()
    
    @staticmethod
    async def get_leaderboard(period: str = 'daily', limit: int = 10) -> List[Dict]:
        """Получает лидерборд за период"""
        period_start = RatingService._get_period_start(period)
        
        async for session in get_session():
            result = await session.execute(
                select(UserRating, User)
                .join(User, UserRating.user_id == User.id)
                .where(
                    and_(
                        UserRating.period == period,
                        UserRating.period_start == period_start,
                        UserRating.total_winnings > 0
                    )
                )
                .order_by(desc(UserRating.total_winnings))
                .limit(limit)
            )
            
            leaderboard = []
            for rating, user in result:
                leaderboard.append({
                    'user_id': user.id,
                    'username': user.username or f"User{user.id}",
                    'first_name': user.first_name,
                    'total_winnings': rating.total_winnings,
                    'total_wins': rating.total_wins,
                    'total_losses': rating.total_losses,
                    'total_bets': rating.total_bets,
                    'win_rate': round((rating.total_wins / rating.total_bets * 100) if rating.total_bets > 0 else 0, 1)
                })
            
            return leaderboard
    
    @staticmethod
    async def calculate_daily_rewards() -> None:
        """Вычисляет и создает награды за места в дневном лидерборде"""
        leaderboard = await RatingService.get_leaderboard('daily', 3)
        
        if not leaderboard:
            return
        
        rewards = [
            {'position': 1, 'amount': 150000},  # $1500
            {'position': 2, 'amount': 70000},   # $700
            {'position': 3, 'amount': 40000}    # $400
        ]
        
        async for session in get_session():
            for i, player in enumerate(leaderboard[:3]):
                reward_data = rewards[i]
                
                # Проверяем, не выдана ли уже награда
                existing_reward = await session.execute(
                    select(LeaderboardReward).where(
                        and_(
                            LeaderboardReward.user_id == player['user_id'],
                            LeaderboardReward.period == 'daily',
                            LeaderboardReward.position == reward_data['position'],
                            func.date(LeaderboardReward.rewarded_at) == func.date(datetime.utcnow())
                        )
                    )
                )
                
                if not existing_reward.scalar_one_or_none():
                    reward = LeaderboardReward(
                        user_id=player['user_id'],
                        position=reward_data['position'],
                        period='daily',
                        reward_amount=reward_data['amount'],
                        is_claimed=False
                    )
                    session.add(reward)
            
            await session.commit()
    
    @staticmethod
    async def claim_reward(user_id: int, reward_id: int) -> bool:
        """Забирает награду пользователем"""
        async for session in get_session():
            result = await session.execute(
                select(LeaderboardReward).where(
                    and_(
                        LeaderboardReward.id == reward_id,
                        LeaderboardReward.user_id == user_id,
                        LeaderboardReward.is_claimed == False
                    )
                )
            )
            reward = result.scalar_one_or_none()
            
            if not reward:
                return False
            
            # Начисляем награду
            await wallet_service.add_balance(user_id, reward.reward_amount)
            
            # Отмечаем награду как полученную
            reward.is_claimed = True
            await session.commit()
            
            return True
    
    @staticmethod
    async def get_user_rewards(user_id: int) -> List[Dict]:
        """Получает награды пользователя"""
        async for session in get_session():
            result = await session.execute(
                select(LeaderboardReward).where(
                    LeaderboardReward.user_id == user_id
                ).order_by(desc(LeaderboardReward.rewarded_at))
            )
            
            rewards = []
            for reward in result.scalars():
                rewards.append({
                    'id': reward.id,
                    'position': reward.position,
                    'period': reward.period,
                    'amount': reward.reward_amount,
                    'is_claimed': reward.is_claimed,
                    'rewarded_at': reward.rewarded_at
                })
            
            return rewards
    
    @staticmethod
    def _get_period_start(period: str) -> datetime:
        """Получает начало периода"""
        now = datetime.utcnow()
        
        if period == 'daily':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            # Начало недели (понедельник)
            days_since_monday = now.weekday()
            return (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'monthly':
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return now


class CreditService:
    """Сервис для работы с кредитами"""
    
    CREDIT_LIMITS = {
        'daily_1k': {'amount': 100000, 'days': 1},      # $1000 на 1 день
        'weekly_5k': {'amount': 500000, 'days': 7},      # $5000 на 7 дней
        'monthly_15k': {'amount': 1500000, 'days': 30}   # $15000 на 30 дней
    }
    
    @staticmethod
    async def can_take_credit(user_id: int, credit_type: str) -> Tuple[bool, str]:
        """Проверяет, может ли пользователь взять кредит"""
        if credit_type not in CreditService.CREDIT_LIMITS:
            return False, "Неверный тип кредита"
        
        async for session in get_session():
            # Проверяем, есть ли активные кредиты
            result = await session.execute(
                select(UserCredit).where(
                    and_(
                        UserCredit.user_id == user_id,
                        UserCredit.status == 'active'
                    )
                )
            )
            active_credits = result.scalars().all()
            
            if active_credits:
                return False, "У вас уже есть активный кредит"
            
            # Проверяем лимиты
            result = await session.execute(
                select(CreditLimit).where(
                    and_(
                        CreditLimit.user_id == user_id,
                        CreditLimit.limit_type == credit_type
                    )
                )
            )
            limit = result.scalar_one_or_none()
            
            if not limit:
                return True, "Можно взять кредит"
            
            credit_info = CreditService.CREDIT_LIMITS[credit_type]
            days_limit = credit_info['days']
            
            if credit_type == 'daily_1k':
                # Раз в день
                if limit.last_used and (datetime.utcnow() - limit.last_used).days < 1:
                    return False, f"Кредит можно взять раз в день. Последний раз: {limit.last_used.strftime('%d.%m.%Y %H:%M')}"
            elif credit_type == 'weekly_5k':
                # Раз в неделю
                if limit.last_used and (datetime.utcnow() - limit.last_used).days < 7:
                    return False, f"Кредит можно взять раз в неделю. Последний раз: {limit.last_used.strftime('%d.%m.%Y %H:%M')}"
            elif credit_type == 'monthly_15k':
                # Раз в месяц
                if limit.last_used and (datetime.utcnow() - limit.last_used).days < 30:
                    return False, f"Кредит можно взять раз в месяц. Последний раз: {limit.last_used.strftime('%d.%m.%Y %H:%M')}"
            
            return True, "Можно взять кредит"
    
    @staticmethod
    async def take_credit(user_id: int, amount: int, limit_type: str) -> bool:
        """Выдает кредит пользователю"""
        async for session in get_session():
            # Проверяем лимиты
            result = await session.execute(
                select(CreditLimit).where(
                    and_(
                        CreditLimit.user_id == user_id,
                        CreditLimit.limit_type == limit_type
                    )
                )
            )
            limit = result.scalar_one_or_none()
            
            if not limit:
                # Создаем новый лимит
                limit = CreditLimit(
                    user_id=user_id,
                    limit_type=limit_type,
                    last_used=None,
                    usage_count=0
                )
                session.add(limit)
            
            # Проверяем, можно ли взять кредит
            if limit.last_used:
                days_limit = 3 if limit_type == 'daily_1k' else (7 if limit_type == 'weekly_5k' else 30)
                time_diff = datetime.utcnow() - limit.last_used
                if time_diff.days < days_limit:
                    return False
            
            # Создаем кредит
            due_date = datetime.utcnow() + timedelta(days=7)  # 7 дней на возврат
            interest_rate = 1.1  # 10% процентов
            amount_to_repay = int(amount * interest_rate)
            
            credit = UserCredit(
                user_id=user_id,
                amount=amount,
                interest_rate=interest_rate,
                due_date=due_date,
                amount_to_repay=amount_to_repay,
                status='active'
            )
            session.add(credit)
            
            # Обновляем лимит
            limit.last_used = datetime.utcnow()
            limit.usage_count += 1
            
            await session.commit()
            return True
    
    @staticmethod
    async def get_user_credits(user_id: int) -> List[Dict]:
        """Получает кредиты пользователя"""
        async for session in get_session():
            result = await session.execute(
                select(UserCredit).where(
                    UserCredit.user_id == user_id
                ).order_by(desc(UserCredit.issued_at))
            )
            
            credits = []
            for credit in result.scalars():
                credits.append({
                    'id': credit.id,
                    'amount': credit.amount,
                    'amount_to_repay': credit.amount_to_repay,
                    'interest_rate': credit.interest_rate,
                    'issued_at': credit.issued_at,
                    'due_date': credit.due_date,
                    'status': credit.status
                })
            
            return credits
    
    @staticmethod
    async def check_overdue_credits() -> None:
        """Проверяет просроченные кредиты"""
        async for session in get_session():
            result = await session.execute(
                select(UserCredit).where(
                    and_(
                        UserCredit.status == 'active',
                        UserCredit.due_date < datetime.utcnow()
                    )
                )
            )
            
            for credit in result.scalars():
                credit.status = 'overdue'
                credit.last_updated = datetime.utcnow()
            
            await session.commit()

    @staticmethod
    async def get_available_credits(user_id: int) -> List[Dict]:
        """Получает доступные кредиты для пользователя"""
        async for session in get_session():
            # Получаем лимиты пользователя
            result = await session.execute(
                select(CreditLimit).where(CreditLimit.user_id == user_id)
            )
            limits = result.scalars().all()
            
            available_credits = []
            
            # Проверяем каждый тип лимита
            credit_types = [
                ('daily_1k', 100000, 3),  # $1000 каждые 3 дня
                ('weekly_5k', 500000, 7),  # $5000 каждую неделю
                ('monthly_15k', 1500000, 30)  # $15000 каждый месяц
            ]
            
            for limit_type, amount, days in credit_types:
                # Ищем существующий лимит
                limit = next((l for l in limits if l.limit_type == limit_type), None)
                
                if limit:
                    # Проверяем, можно ли взять кредит
                    if limit.last_used:
                        time_diff = datetime.utcnow() - limit.last_used
                        if time_diff.days >= days:
                            available_credits.append({
                                'limit_type': limit_type,
                                'amount': amount,
                                'days': days
                            })
                    else:
                        # Если никогда не использовался
                        available_credits.append({
                            'limit_type': limit_type,
                            'amount': amount,
                            'days': days
                        })
                else:
                    # Если лимит не существует, создаем его
                    new_limit = CreditLimit(
                        user_id=user_id,
                        limit_type=limit_type,
                        last_used=None,
                        usage_count=0
                    )
                    session.add(new_limit)
                    available_credits.append({
                        'limit_type': limit_type,
                        'amount': amount,
                        'days': days
                    })
            
            await session.commit()
            return available_credits

    @staticmethod
    async def repay_credit(user_id: int, credit_id: int) -> Tuple[bool, str]:
        """Возврат кредита пользователем"""
        async for session in get_session():
            # Получаем кредит
            result = await session.execute(
                select(UserCredit).where(
                    and_(
                        UserCredit.id == credit_id,
                        UserCredit.user_id == user_id,
                        UserCredit.status == 'active'
                    )
                )
            )
            credit = result.scalar_one_or_none()
            
            if not credit:
                return False, "Кредит не найден или уже погашен"
            
            # Проверяем баланс пользователя
            from src.services.wallet_service import wallet_service
            balance = await wallet_service.get_balance(user_id)
            
            if balance < credit.amount_to_repay:
                return False, f"Недостаточно средств. Нужно: ${credit.amount_to_repay/100:.0f}, есть: ${balance/100:.0f}"
            
            # Списываем средства
            await wallet_service.debit(user_id, credit.amount_to_repay, f"credit_repayment:{credit_id}")
            
            # Обновляем статус кредита
            credit.status = 'paid'
            credit.last_updated = datetime.utcnow()
            
            await session.commit()
            return True, f"Кредит ${credit.amount/100:.0f} погашен! Возвращено: ${credit.amount_to_repay/100:.0f}"
    
    @staticmethod
    async def auto_repay_from_winnings(user_id: int, winnings: int) -> Tuple[int, str]:
        """Автоматический возврат кредитов из выигрыша"""
        async for session in get_session():
            # Получаем активные кредиты пользователя
            result = await session.execute(
                select(UserCredit).where(
                    and_(
                        UserCredit.user_id == user_id,
                        UserCredit.status == 'active'
                    )
                ).order_by(UserCredit.due_date.asc())  # Сначала самые срочные
            )
            credits = result.scalars().all()
            
            if not credits:
                return winnings, ""
            
            remaining_winnings = winnings
            repaid_credits = []
            
            for credit in credits:
                if remaining_winnings >= credit.amount_to_repay:
                    # Полностью погашаем кредит
                    remaining_winnings -= credit.amount_to_repay
                    credit.status = 'paid'
                    credit.last_updated = datetime.utcnow()
                    repaid_credits.append(f"${credit.amount/100:.0f}")
                else:
                    # Частично погашаем кредит
                    credit.amount_to_repay -= remaining_winnings
                    repaid_credits.append(f"${remaining_winnings/100:.0f} из ${credit.amount/100:.0f}")
                    remaining_winnings = 0
                    break
            
            await session.commit()
            
            if repaid_credits:
                return remaining_winnings, f"Автоматически погашены кредиты: {', '.join(repaid_credits)}"
            else:
                return winnings, "Недостаточно выигрыша для погашения кредитов"


class VIPService:
    """Сервис для работы с VIP статусом"""
    
    @staticmethod
    async def apply_vip_multiplier(user_id: int, win_amount: int) -> Tuple[int, str]:
        """Применяет VIP множитель к выигрышу"""
        async for session in get_session():
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.is_vip or not user.vip_multiplier_enabled:
                return win_amount, ""
            
            # Применяем множитель
            multiplier = user.vip_multiplier_value / 100  # 130 -> 1.3
            bonus_amount = int(win_amount * (multiplier - 1))  # Дополнительная сумма
            total_win = win_amount + bonus_amount
            
            return total_win, f"⭐ VIP Бонус - +{multiplier:.1f}x (+${bonus_amount/100:.0f})"
    
    @staticmethod
    async def apply_vip_cashback(user_id: int, loss_amount: int) -> Tuple[int, str]:
        """Применяет VIP возврат при проигрыше"""
        async for session in get_session():
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.is_vip or not user.vip_cashback_enabled:
                return 0, ""
            
            # Рассчитываем возврат
            cashback_percentage = user.vip_cashback_percentage / 100  # 10 -> 0.1
            cashback_amount = int(loss_amount * cashback_percentage)
            
            if cashback_amount > 0:
                # Начисляем возврат на баланс
                from src.services.wallet_service import wallet_service
                await wallet_service.credit(user_id, cashback_amount, "vip_cashback")
                
                return cashback_amount, f"💰 VIP Возврат - ${cashback_amount/100:.0f}"
            
            return 0, ""
    
    @staticmethod
    async def get_vip_info(user_id: int) -> Dict:
        """Получает информацию о VIP статусе пользователя"""
        async for session in get_session():
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {}
            
            return {
                'is_vip': user.is_vip,
                'multiplier_enabled': user.vip_multiplier_enabled,
                'multiplier_value': user.vip_multiplier_value / 100,
                'cashback_enabled': user.vip_cashback_enabled,
                'cashback_percentage': user.vip_cashback_percentage
            }
