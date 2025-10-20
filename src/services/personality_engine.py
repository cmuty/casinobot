import random
from typing import Optional, Dict, Any
from enum import Enum
from src.models import User # Импортируем модель User для получения персональности

class PersonalityType(str, Enum):
    PLAYFUL = "playful"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    FREAK = "freak"

class PersonalityEngine:
    """Движок для динамического изменения тона в зависимости от контекста"""
    
    PERSONALITIES = {
        PersonalityType.PLAYFUL: lambda: PlayfulPersonality(),
        PersonalityType.NEUTRAL: lambda: NeutralPersonality(),
        PersonalityType.FORMAL: lambda: FormalPersonality(),
        PersonalityType.FREAK: lambda: FreakPersonality(),
    }
    
    @staticmethod
    async def get_message(
        event: str,
        user: User, # Передаём объект пользователя
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Получение сообщения с учётом персональности пользователя
        
        Args:
            event: Тип события (win, loss, jackpot, etc.)
            user: Объект пользователя (из базы данных)
            context: Дополнительный контекст (сумма, стрик и т.д.)
        """
        # Получаем персональность пользователя, fallback на PLAYFUL
        personality = getattr(user, 'personality', PersonalityType.PLAYFUL)
        
        print(f"DEBUG PERSONALITY: User {user.telegram_id}, personality from DB: '{personality}', type: {type(personality)}")
        
        # Проверяем что личность валидна (сравниваем со значениями enum)
        valid_personalities = [p.value for p in PersonalityType]
        print(f"DEBUG PERSONALITY: Valid personalities: {valid_personalities}")
        
        if personality not in valid_personalities:
            print(f"DEBUG PERSONALITY: Invalid personality '{personality}', falling back to PLAYFUL")
            personality = PersonalityType.PLAYFUL.value
        
        # Конвертируем строку в enum
        personality_enum = PersonalityType(personality)
        print(f"DEBUG PERSONALITY: Final personality enum: {personality_enum}")

        personality_func = PersonalityEngine.PERSONALITIES.get(
            personality_enum,
            PersonalityEngine.PERSONALITIES[PersonalityType.PLAYFUL]
        )
        personality_obj = personality_func()
        
        return personality_obj.get_message(event, context or {})

class PlayfulPersonality:
    """Игривая персональность с юмором"""
    
    EMOJIS = {
        'win': ['🎉', '🥳', '🎊', '💰', '🤑'],
        'loss': ['😅', '😔', '🙈', '💔', '😢'],
        'jackpot': ['💎', '👑', '🚀', '⭐', '🎆']
    }
    
    def get_message(self, event: str, context: Dict[str, Any]) -> str:
        if event == 'big_win':
            multiplier = context.get('multiplier', 2)
            if multiplier >= 50:
                return random.choice([
                    f"🤯 ВАУ! Ты только что сорвал x{multiplier}! Это же почти ограбление казино! (Шучу, мы рады за тебя! 😄)",
                    f"💥 БУМ! x{multiplier}! Твоя карма сегодня на высоте! 🌟",
                    f"🚀 КОСМОС! x{multiplier}! Луна уже не предел для тебя! 🌙"
                ])
            elif multiplier >= 10:
                return random.choice([
                    f"🎉 Отлично! x{multiplier}! Удача явно решила подружиться с тобой! 🍀",
                    f"💪 Красавчик! x{multiplier}! Так держать! 🔥"
                ])
            else:
                return random.choice([
                    f"🎊 Ура! Выигрыш x{multiplier}! Поздравляем! 🥳",
                    f"🤑 Удача на твоей стороне! x{multiplier} — отличный результат! 💰"
                ])
        
        elif event == 'slots_loss':
            return random.choice([
                f"😅 Эх, барабаны не на твоей стороне сегодня... Но знаешь что говорят: не везёт в картах — повезёт в любви! 💕",
                f"😔 Не повезло... Но не сдавайся! Следующая ставка может быть суперудачной! 🍀",
                f"🙈 Ой-ой... Может, стоит сделать перерыв и вернуться с новыми силами? 💪"
            ])
        
        elif event == 'dice_win':
            return random.choice([
                f"🎲 Ха! Бот в шоке! Ты кинул кубик как профи! Удача явно на твоей стороне! 🍀",
                f"🎉 Победа! Бот проиграл, а ты — молодец! 🙌",
                f"💪 Крутанул кубик — и в точку! Так держать! 🔥"
            ])
        
        elif event == 'dice_loss':
            return random.choice([
                f"🎲 Упс... Бот сегодня в ударе! Но не сдавайся — реванш не за горами! 💪",
                f"😔 Бот победил... Но ты не вешай нос! Следующая игра — твоя! 🌟",
                f"😅 Кубик сегодня не на твоей стороне, но удача может измениться в любой момент! 🎲"
            ])
        
        elif event == 'jackpot':
            return random.choice([
                f"💎 СВЯТЫЕ СЛОТЫ! Ты только что сорвал ДЖЕКПОТ! Твоя удача зашкаливает! 🚀 Может, стоит застраховать этот момент? 😎",
                f"🎆 ВАУ! ДЖЕКПОТ! Это будет на обложке казино! 📸",
                f"👑 ЛЕГЕНДА! Ты сорвал джекпот! История только начинается! 🚀"
            ])
        
        elif event == 'low_balance':
            return random.choice([
                f"💸 Ой-ой, кошелёк похудел! Может, пора подкрепиться через /buy? Или попробуй поймать удачу за хвост с тем, что есть! 🎰",
                f"💰 Баланс на нуле? Не беда! Главное — верить в удачу! 🍀",
                f"😅 Кошель пуст? Не переживай, следующая ставка может всё изменить! 💪"
            ])
        
        elif event == 'daily_bonus':
            return random.choice([
                f"🎁 Твой ежедневный подарок готов! Как будто День рождения каждый день! 🎂",
                f"🎉 Бонус прибыл! Ура! С праздником! 🥳",
                f"🤑 Ежедневный бонус — твой ключик к удаче! Не забывай забирать! 💰"
            ])
        
        elif event == 'welcome_back':
            return random.choice([
                f"Йоу! С возвращением! Барабаны уже соскучились по тебе! 🎰",
                f"👋 Привет, чемпион! Готов к новым победам? 🏆",
                f"🎮 Возвращайся в игру! Удача ждёт тебя! 🍀"
            ])
        
        elif event == 'error_too_fast':
            return random.choice([
                f"⏰ Эй, эй, эй! Притормози, ковбой! Даже удаче нужна секундочка, чтобы перевести дух! 😅",
                f"😅 Медленнее! У тебя слишком быстрые руки! Подожди немного. ⏳",
                f"⏱️ Не спеши! Дай боту передышку. У тебя всё равно всё впереди! 💪"
            ])
        
        # Обработка неизвестного события
        return "Что-то пошло не так... Но мы работаем над этим! 🔧"

class NeutralPersonality:
    """Нейтральная персональность"""
    
    def get_message(self, event: str, context: Dict[str, Any]) -> str:
        if event == 'big_win':
            multiplier = context.get('multiplier', 2)
            return f"✅ Поздравляем с выигрышем x{multiplier}! Ваш баланс пополнен."
        elif event == 'slots_loss':
            return "❌ К сожалению, удача не на вашей стороне. Попробуйте ещё раз."
        elif event == 'dice_win':
            return "🎲 Победа! Ваш результат выше, чем у бота."
        elif event == 'dice_loss':
            return "🎲 Бот выиграл эту партию. Попробуйте снова."
        elif event == 'jackpot':
            return "🎰 Джекпот! Вы выиграли крупную сумму. Поздравляем!"
        elif event == 'low_balance':
            return "💰 Недостаточно средств. Пополните баланс через /buy."
        elif event == 'daily_bonus':
            return "🎁 Ежедневный бонус получен."
        elif event == 'welcome_back':
            balance = context.get('balance', 0)
            return f"Добро пожаловать обратно. Ваш баланс: ${balance / 100:.2f}."
        elif event == 'error_too_fast':
            return "⏰ Пожалуйста, подождите перед следующей ставкой."
        return "Сообщение не найдено."

class FormalPersonality:
    """Официальная персональность"""
    
    def get_message(self, event: str, context: Dict[str, Any]) -> str:
        if event == 'big_win':
            return "✅ Транзакция завершена успешно. Выигрыш зачислен на ваш счёт."
        elif event == 'slots_loss':
            return "ℹ️ Ставка не принесла выигрыша. Средства списаны согласно условиям игры."
        elif event == 'dice_win':
            return "✅ Результат положительный. Выплата произведена в соответствии с правилами."
        elif event == 'dice_loss':
            return "ℹ️ Результат отрицательный. Ставка не возвращается согласно условиям."
        elif event == 'jackpot':
            return "🏆 Уведомление: Достигнут максимальный выигрыш. Сумма зачислена на баланс."
        elif event == 'low_balance':
            return "⚠️ Баланс недостаточен для выполнения операции. Рекомендуем пополнить счёт."
        elif event == 'daily_bonus':
            return "📋 Ежедневное начисление бонуса выполнено."
        elif event == 'welcome_back':
            balance = context.get('balance', 0)
            return f"Здравствуйте. Текущий баланс счёта: ${balance / 100:.2f}."
        elif event == 'error_too_fast':
            return "⚠️ Превышена частота запросов. Повторите операцию через несколько секунд."
        return "Уведомление: операция выполнена."

class FreakPersonality:
    """Дерзкая персональность с острыми комментариями"""
    
    def get_message(self, event: str, context: Dict[str, Any]) -> str:
        if event == 'big_win':
            multiplier = context.get('multiplier', 2)
            if multiplier >= 50:
                return random.choice([
                    f"🔥 БЛЯТЬ! x{multiplier}! Ты реально сорвал банк! Ну ты и лакерный сын шлюхи! 😱",
                    f"💀 ЕБАТЬ! x{multiplier}! Это же пиздец какой выигрыш! Ты пидорас совсем ахуел! 🚀",
                    f"⚡ НАХУЙ! x{multiplier}! Ты только что обосрал всю статистику! Ебал тебе рот! 👑"
                ])
            elif multiplier >= 10:
                return random.choice([
                    f"💥 Охуенно! x{multiplier}! Пизда в канаве! 🔥",
                    f"🎯 Красота! x{multiplier}! Ты сегодня в ударе, братан! 💪"
                ])
            else:
                return random.choice([
                    f"🎉 Нормально! x{multiplier}! С таким иксом можно цыплять твою мамашку! 🎲",
                    f"💰 Хорошо! x{multiplier}! А теперь с таким иксом трахнем твою сестренку! 🔥"
                ])
        
        elif event == 'slots_loss':
            return random.choice([
                f"😤 Бля ебать ты гомункул ебанный просто лох ебанный пошел нахуй! 💪",
                f"💔 Ебать, барабаны сегодня не в духе... Но ты же не будешь больше депать хуесос? 🔥",
                f"😡 Сука, опять мимо... Но знаешь что? Надеюсь ты больше не выйграешь! 🍀"
            ])
        
        elif event == 'dice_win':
            return random.choice([
                f"🎲 Ебать! С такими попадалками тебе только трахать свою мать 😂",
                f"🔥 Ты сука конь ебанный каким хуем выйграл 💪",
                f"⚡ Нормально ты пидорас выйграл же нахуй! 🎯"
            ])
        
        elif event == 'dice_loss':
            return random.choice([
                f"🎲 Ну пошел нахуй че тебе сказать ты проебал утырок 💪",
                f"😤 Сука, проиграл... ну не судьба тебе отведать члена 🔥",
                f"💀 Ебать, не повезло... Но удача переменчива! Умри нахуй! 🍀"
            ])
        
        elif event == 'jackpot':
            return random.choice([
                f"💎 БЛЯТЬ! ДЖЕКПОТ! Ты ваще пидорас ахуел или че нахуй! 🚀",
                f"👑 НАХУЙ! ДЖЕКПОТ! Ты выблядок вообще страх потерял нахуй! 💀",
                f"🎆 ЕБАТЬ! ДЖЕКПОТ! Ты только что обосрал всю статистику, прям как я твою мать! 🔥"
            ])
        
        elif event == 'low_balance':
            return random.choice([
                f"💸 Бля, кошелек пустой... может ты последние трусы мамаши своей поставишь? 🎰",
                f"💰 Сука, баланс на нуле... иди кредит возьми я хуй знает 🍀",
                f"😅 Ебать, денег нет... нет у тебя сил даже на трусы мамаши своей поставить? 💪"
            ])
        
        elif event == 'daily_bonus':
            return random.choice([
                f"🎁 Ебать, тебе бичу дал нахуй бонуску 🎂",
                f"🎉 Ну че иди дэпай хули смотришь 🥳",
                f"🤑 Бля проебанная жопа мамаши твоей будет с этой 💰"
            ])
        
        elif event == 'welcome_back':
            return random.choice([
                f"Нахуй ты вернулся хуесос ебливый, я надеюсь что ты не вернешься больше 🎰",
                f"👋 Эй сын шлюхи готов пизды получать? 🏆",
                f"🎮 Пизда проебали нахуй, с тобой то точно нахуй 🍀"
            ])
        
        elif event == 'error_too_fast':
            return random.choice([
                f"⏰ Бля ты че нахуй делаешь хуесос, а ну ебало закрой 😅",
                f"😅 Сука, слишком быстро! Прям как я ебу твою мать ⏳",
                f"⏱️ Ебать, не торопись! Дай передернуть на твою сраку! 💪"
            ])
        
        # Обработка неизвестного события
        return "Бля, что-то пошло не так... Пошел ты нахуй! 🔧"

# Класс для эмоциональных реакций на основе истории игрока
# ПОКА НЕ РЕАЛИЗОВАН, ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ ЛОГИКА СТАТИСТИКИ
class EmotionalResponseSystem:
    """Система эмоциональных реакций на основе истории игрока (Заглушка)"""
    
    @staticmethod
    async def get_contextual_message(
        user: User,
        event: str,
        base_message: str
    ) -> str:
        """
        Добавление контекстуальных элементов к сообщению (Пока просто возвращает базовое сообщение)
        """
        # ЗДЕСЬ БУДЕТ ЛОГИКА НА ОСНОВЕ СТАТИСТИКИ И Т.Д.
        # Нужно будет реализовать с помощью bet_service.get_user_stats
        return base_message