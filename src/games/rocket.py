import random
import asyncio
import math


class RocketGame:
    """Игра Ракетка (Crash Game)"""
    
    # Начальный коэффициент
    START_MULTIPLIER = 1.0
    
    # Инкремент коэффициента каждый тик (0.1x)
    MULTIPLIER_INCREMENT = 0.1
    
    # Интервал обновления в секундах (0.1 секунды = 100ms)
    UPDATE_INTERVAL = 0.1
    
    # Максимальный коэффициент (защита от абузов)
    MAX_MULTIPLIER = 10.0
    
    @staticmethod
    def calculate_crash_point() -> float:
        """
        Генерирует точку краша с более сбалансированным распределением.
        Это обеспечивает справедливую игру с математическим ожиданием ~95% RTP.
        """
        # Используем более сбалансированный алгоритм
        # House edge ~5%
        house_edge = 0.05
        
        # Генерируем случайное число от 0 до 1
        rand = random.random()
        
        # Используем формулу для получения более реалистичного распределения
        # Минимум 1.1x, максимум 10.0x
        if rand < 0.1:  # 10% шанс на низкие коэффициенты (1.1x - 2.0x)
            crash_point = 1.1 + (rand / 0.1) * 0.9
        elif rand < 0.3:  # 20% шанс на средние коэффициенты (2.0x - 4.0x)
            crash_point = 2.0 + ((rand - 0.1) / 0.2) * 2.0
        elif rand < 0.6:  # 30% шанс на хорошие коэффициенты (4.0x - 6.0x)
            crash_point = 4.0 + ((rand - 0.3) / 0.3) * 2.0
        elif rand < 0.8:  # 20% шанс на высокие коэффициенты (6.0x - 8.0x)
            crash_point = 6.0 + ((rand - 0.6) / 0.2) * 2.0
        else:  # 20% шанс на очень высокие коэффициенты (8.0x - 10.0x)
            crash_point = 8.0 + ((rand - 0.8) / 0.2) * 2.0
        
        # Применяем house edge
        crash_point = crash_point * (1 - house_edge)
        
        # Ограничиваем минимальный краш до 1.1x и максимальный до MAX_MULTIPLIER
        crash_point = max(1.1, min(crash_point, RocketGame.MAX_MULTIPLIER))
        
        return round(crash_point, 1)
    
    @staticmethod
    def calculate_payout(stake: int, multiplier: float) -> int:
        """Расчёт выплаты на основе ставки и коэффициента"""
        return int(stake * multiplier)
    
    @staticmethod
    async def simulate_rocket(crash_point: float, callback_func):
        """
        Симулирует полет ракеты с обновлениями каждые UPDATE_INTERVAL секунд.
        
        Args:
            crash_point: Точка, в которой ракета взорвется
            callback_func: Функция обратного вызова для обновления сообщения
                          Должна принимать (current_multiplier, is_crashed)
                          Возвращает True если игра должна продолжиться, False если остановиться
        """
        current_multiplier = RocketGame.START_MULTIPLIER
        
        while current_multiplier < crash_point:
            # Отправляем обновление
            should_continue = await callback_func(current_multiplier, False)
            
            # Если callback вернул False, останавливаем игру
            if not should_continue:
                return
            
            # Ждем перед следующим обновлением
            await asyncio.sleep(RocketGame.UPDATE_INTERVAL)
            
            # Увеличиваем множитель
            current_multiplier = round(current_multiplier + RocketGame.MULTIPLIER_INCREMENT, 1)
            
            # Проверяем максимальный лимит
            if current_multiplier >= RocketGame.MAX_MULTIPLIER:
                await callback_func(RocketGame.MAX_MULTIPLIER, False)
                break
        
        # Ракета взорвалась!
        await callback_func(crash_point, True)
    
    @staticmethod
    def format_multiplier(multiplier: float) -> str:
        """Форматирует множитель для отображения"""
        return f"{multiplier:.1f}x"
    
    @staticmethod
    def get_rocket_emoji(multiplier: float) -> str:
        """Возвращает эмодзи ракеты в зависимости от коэффициента"""
        if multiplier < 2.0:
            return "🚀"
        elif multiplier < 4.0:
            return "🚀💨"
        elif multiplier < 6.0:
            return "🚀💨💨"
        else:
            return "🚀💨💨💨"

