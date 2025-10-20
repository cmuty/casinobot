import random


class DiceGame:
    """Дуэль на костях"""
    
    @staticmethod
    def roll() -> int:
        """Бросок кубика (1-6)"""
        return random.randint(1, 6)
    
    @staticmethod
    def calculate_payout(player_value: int, bot_value: int, stake: int) -> int:
        """Расчёт выплаты - сбалансированная версия"""
        if player_value > bot_value:
            # Уменьшаем множитель выигрыша для баланса
            return int(stake * 1.3)  # Было 1.5, стало 1.3
        elif player_value == bot_value:
            # Ничья - возврат ставки
            return stake
        else:
            # Проигрыш
            return 0