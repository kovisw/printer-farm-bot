import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import BOT_TOKEN
from src.middlewares.auth import AuthMiddleware
from src.handlers import chat, upload, control, menu
from src.services.monitor import monitor_printers_background

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    # провайдер на сервере режет api.telegram.org, поэтому телеграм тоже идет через прокси.
    # по умолчанию тот же, что для gemini, можно задать отдельный TG_PROXY
    tg_proxy = os.getenv("TG_PROXY") or os.getenv("GEMINI_PROXY")
    session = None
    if tg_proxy:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=tg_proxy)
        logger.info(f"Telegram-сессия идёт через прокси: {tg_proxy}")
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher()

    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())

    # menu последним, в нем fallback на все сообщения
    dp.include_router(chat.router)
    dp.include_router(upload.router)
    dp.include_router(control.router)
    dp.include_router(menu.router)

    asyncio.create_task(monitor_printers_background(bot))

    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # для запуска на винде при отладке
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
