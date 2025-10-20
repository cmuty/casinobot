import secrets


class RouletteGame:
    """Мини-рулетка"""
    
    RED_NUMBERS = [1, 3, 5, 7, 9]
    BLACK_NUMBERS = [2, 4, 6, 8, 10]
    
    @staticmethod
    def spin() -> int:
        """Вращение рулетки"""
        return secrets.randbelow(10) + 1
    
    @staticmethod
    def get_color(number: int) -> str:
        """Получить цвет числа"""
        return 'red' if number in RouletteGame.RED_NUMBERS else 'black'
    
    @staticmethod
    def calculate_payout(bet_type: str, bet_value, result: int, stake: int) -> int:
        """Расчёт выплаты - сбалансированная версия"""
        if bet_type == 'number':
            if result == bet_value:
                return int(stake * 2.2)  # Было 3x, стало 2.2x
        elif bet_type in ['red', 'black']:
            if result in bet_value:
                return int(stake * 1.5)  # Было 1.8x, стало 1.5x
        elif bet_type == 'even':
            if result in [2, 4, 6, 8, 10]:  # Четные числа
                return int(stake * 1.5)
        elif bet_type == 'odd':
            if result in [1, 3, 5, 7, 9]:  # Нечетные числа
                return int(stake * 1.5)
        elif bet_type == 'high':
            if result in [6, 7, 8, 9, 10]:  # Высокие числа
                return int(stake * 1.5)
        elif bet_type == 'low':
            if result in [1, 2, 3, 4, 5]:  # Низкие числа
                return int(stake * 1.5)
        
        return 0