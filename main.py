"""Главный файл запуска бота"""
import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers import router, setup_bot_commands

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)


async def main():
    """Главная функция запуска бота"""
    dp = Dispatcher()
    dp.include_router(router)
    
    # Устанавливаем команды при запуске
    await setup_bot_commands(bot)
    
    logger.info("Бот запущен!")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
