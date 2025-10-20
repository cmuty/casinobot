import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Переименовываем импорт настроек, чтобы не конфликтовал с роутером
from src.config import settings as app_settings  # <-- Переименован
from src.redis_db import init_redis, close_redis
from src.handlers import start, games, profile, bonus, admin, settings, buy, admin_panel, rating  # <-- Добавлен rating

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_bot():
    """Создать экземпляр бота"""
    return Bot(
        token=app_settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


async def create_dispatcher():
    """Создать диспетчер"""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(admin_panel.router)
    dp.include_router(games.router)
    dp.include_router(profile.router)
    dp.include_router(bonus.router)
    dp.include_router(admin.router)
    dp.include_router(settings.router)
    dp.include_router(buy.router)
    dp.include_router(rating.router)
    
    return dp


async def polling_main():
    """Запуск бота в режиме polling (для разработки)"""
    bot = await create_bot()
    dp = await create_dispatcher()
    
    # Инициализация Redis
    try:
        await init_redis()
        logger.info("✅ Redis initialized successfully")
    except Exception as e:
        logger.error(f"❌ Redis initialization failed: {e}")
        return
    
    # Запуск бота
    try:
        logger.info("🎰 LuckyStar Casino запущен в режиме polling")
        logger.info(f"Bot username: @{(await bot.get_me()).username}")
        await dp.start_polling(bot)
    finally:
        await close_redis()
        await bot.session.close()


async def webhook_main():
    """Запуск бота в режиме webhook (для продакшена)"""
    bot = await create_bot()
    dp = await create_dispatcher()
    
    # Инициализация Redis
    try:
        await init_redis()
        logger.info("✅ Redis initialized successfully")
    except Exception as e:
        logger.error(f"❌ Redis initialization failed: {e}")
        return
    
    # Настройка webhook
    webhook_url = f"{app_settings.WEBHOOK_URL}{app_settings.WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logger.info(f"✅ Webhook set to: {webhook_url}")
    
    # Создание aiohttp приложения
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=app_settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    # Запуск сервера
    port = app_settings.PORT
    logger.info(f"🎰 LuckyStar Casino запущен на порту {port}")
    logger.info(f"Bot username: @{(await bot.get_me()).username}")
    
    return app


async def main():
    """Главная функция запуска бота"""
    # Проверяем, запускаем ли мы в продакшене (Render)
    if app_settings.WEBHOOK_URL:
        # Продакшен режим с webhook
        app = await webhook_main()
        if app:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', app_settings.PORT)
            await site.start()
            
            # Держим сервер запущенным
            try:
                await asyncio.Future()  # Бесконечный цикл
            finally:
                await runner.cleanup()
    else:
        # Режим разработки с polling
        await polling_main()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")