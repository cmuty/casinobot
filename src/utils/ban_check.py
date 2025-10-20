from aiogram.types import Message
from sqlalchemy import select
from src.models import User


async def check_if_banned(message: Message) -> bool:
    """
    Проверяет, заблокирован ли пользователь.
    Возвращает True, если пользователь заблокирован, иначе False.
    """
    from src.database import async_session_maker
    
    telegram_id = message.from_user.id
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        if user.is_banned:
            await message.answer(
                "🚫 <b>Вы заблокированы в нашей системе</b>\n\n"
                "Доступ к боту ограничен.\n"
                "Обратитесь к администратору для получения дополнительной информации."
            )
            return True
    
    return False

