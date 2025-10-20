"""
Логика игры в мины
"""
import random
import secrets
from typing import List, Tuple, Dict


class MinesGame:
    """Класс для игры в мины"""
    
    BOARD_SIZE = 5
    TOTAL_CELLS = BOARD_SIZE * BOARD_SIZE
    MINES_COUNT = 6  # Количество мин на поле (24% шанс попасть на мину)
    MAX_SAFE_MOVES = 15  # Максимальное количество безопасных ходов (защита от абуза)
    
    # Коэффициенты для каждого хода (сбалансированные)
    MULTIPLIERS = {
        1: 1.2,   # Первый ход - минимальный риск
        2: 1.4,  # Второй ход
        3: 1.8,   # Третий ход
        4: 2.2,   # Четвертый ход
        5: 2.8,   # Пятый ход
        6: 3.2,   # Шестой ход
        7: 4.0,   # Седьмой ход
        8: 6.0,   # Восьмой ход
        9: 8.0,   # Девятый ход
        10: 10.0,  # Десятый ход
        11: 12.0,  # Одиннадцатый ход
        12: 13.0,  # Двенадцатый ход
        13: 16.0,  # Тринадцатый ход
        14: 20.0, # Четырнадцатый ход
        15: 27.0, # Пятнадцатый ход - максимум
    }
    
    @classmethod
    def generate_mines(cls, user_id: int, nonce: int) -> List[int]:
        """Генерирует позиции мин на основе user_id и nonce"""
        # Используем комбинацию user_id, nonce и текущего времени для уникальности
        import time
        seed_value = hash(f"{user_id}_{nonce}_{int(time.time() * 1000)}")
        random.seed(seed_value)
        
        # Генерируем все возможные позиции
        all_positions = list(range(cls.TOTAL_CELLS))
        
        # Выбираем случайные позиции для мин
        mines = random.sample(all_positions, cls.MINES_COUNT)
        
        return sorted(mines)
    
    @classmethod
    def get_multiplier(cls, moves_count: int) -> float:
        """Возвращает коэффициент для текущего количества ходов"""
        # Ограничиваем максимальное количество ходов
        moves_count = min(moves_count, cls.MAX_SAFE_MOVES)
        return cls.MULTIPLIERS.get(moves_count, cls.MULTIPLIERS[cls.MAX_SAFE_MOVES])
    
    @classmethod
    def calculate_payout(cls, stake_cents: int, moves_count: int) -> int:
        """Рассчитывает выигрыш на основе ставки и количества ходов"""
        multiplier = cls.get_multiplier(moves_count)
        return int(stake_cents * multiplier)
    
    @classmethod
    def position_to_coords(cls, position: int) -> Tuple[int, int]:
        """Конвертирует позицию в координаты (row, col)"""
        return (position // cls.BOARD_SIZE, position % cls.BOARD_SIZE)
    
    @classmethod
    def coords_to_position(cls, row: int, col: int) -> int:
        """Конвертирует координаты в позицию"""
        return row * cls.BOARD_SIZE + col
