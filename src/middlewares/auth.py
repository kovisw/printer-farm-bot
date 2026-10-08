from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from src.config import USER_ID, ACCESS_CODE

# владелец из .env пускается сразу, остальные - после ввода кода.
# хранится в памяти, после перезапуска контейнера надо вводить заново
AUTH_USERS = {USER_ID}

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not hasattr(event, "from_user") or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        if user_id in AUTH_USERS:
            return await handler(event, data)

        if ACCESS_CODE and hasattr(event, "text") and event.text and event.text.strip() == ACCESS_CODE:
            AUTH_USERS.add(user_id)
            from src.handlers.menu import get_main_menu
            await event.answer("✅ Доступ разрешен!", reply_markup=get_main_menu())
            return

        if hasattr(event, "answer"):
            if isinstance(event, Message):
                await event.answer("Введите ключ доступа:")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сначала введите ключ доступа в чат.", show_alert=True)
        return
