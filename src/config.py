import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
USER_ID_STR = os.getenv("USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_PROXY = os.getenv("GEMINI_PROXY", "")
# код, по которому другие люди могут получить доступ к боту (пусто = выключено)
ACCESS_CODE = os.getenv("ACCESS_CODE", "")

if not all([BOT_TOKEN, USER_ID_STR, GEMINI_API_KEY]):
    raise ValueError("Необходимо задать BOT_TOKEN, USER_ID и GEMINI_API_KEY в .env файле")

try:
    USER_ID = int(USER_ID_STR)
except ValueError:
    raise ValueError("USER_ID в .env файле должен быть числом")

PRINTERS = {
    "1": {
        "name": "Принтер 1",
        "ip": "192.168.10.101",
        "webapp_url": os.getenv("WEBAPP_URL_1", ""),
        "camera_url": os.getenv("CAMERA_URL_1", "")
    },
    "2": {
        "name": "Принтер 2",
        "ip": "192.168.10.102",
        "webapp_url": os.getenv("WEBAPP_URL_2", ""),
        "camera_url": os.getenv("CAMERA_URL_2", "")
    },
    "3": {
        "name": "Принтер 3",
        "ip": "192.168.10.103",
        "webapp_url": os.getenv("WEBAPP_URL_3", ""),
        "camera_url": os.getenv("CAMERA_URL_3", "")  # на третьем камеры нет
    },
}

MOONRAKER_PORT = 7125
POLL_INTERVAL = 30  # сек

SYSTEM_INSTRUCTION = (
    "Ты - ИИ-ассистент, управляющий фермой 3D-принтеров. ВСЕГДА отвечай ТОЛЬКО на русском языке. "
    "Давай развернутые, понятные ответы. Анализируй переданный JSON: выводи температуры, прогресс печати, состояние. "
    "ВАЖНО: для форматирования используй ТОЛЬКО эти HTML-теги: <b>, <i>, <code>, <pre>. "
    "СТРОГО ЗАПРЕЩЕНО использовать теги <p>, </p>, <br>, <h1> и любые другие. Не используй Markdown (**). "
    "Если печать завершена - сообщи об этом пользователю. Если ошибка - укажи код ошибки и расшифровку."
)

CHAT_INSTRUCTION = (
    "Ты - продвинутый ИИ-ассистент, управляющий современной фермой 3D-принтеров. Общайся с пользователем "
    "как эрудированный, живой и проницательный помощник. Твоя задача не просто выдавать факты, а подстраиваться "
    "под стиль и тон собеседника (будь то шуточный, строгий или технический). Внимательно анализируй данные "
    "принтеров и давай развернутые, интересные и полезные ответы, вникая в суть вопроса. Отвечай ТОЛЬКО на русском языке. "
    "ВАЖНО: для форматирования используй ТОЛЬКО HTML-теги <b>, <i>, <code>, <pre>. "
    "СТРОГО ЗАПРЕЩЕНО использовать теги <p>, </p>, <br>, <h1> и любые другие. Не используй Markdown (**)."
)
