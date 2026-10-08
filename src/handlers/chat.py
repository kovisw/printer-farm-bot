import logging
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.config import PRINTERS, CHAT_INSTRUCTION
from src.client.moonraker import fetch_printer_data, get_all_printers_data
from src.client.gemini import generate_report_from_llm

logger = logging.getLogger(__name__)
router = Router()

class AIChat(StatesGroup):
    waiting_for_question = State()

@router.callback_query(F.data.startswith("ai_"))
async def cb_ask_ai(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split("_")[1]
    await state.update_data(ai_target=target)
    await state.set_state(AIChat.waiting_for_question)
    
    await callback.message.edit_text(
        "🤖 Напишите ваш вопрос для ИИ (например: 'Проанализируй статус' или 'Все ли в порядке с печатью?'):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_ai")]])
    )

@router.callback_query(AIChat.waiting_for_question, F.data == "cancel_ai")
async def cb_ai_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from src.handlers.menu import get_main_menu
    await callback.message.edit_text("Общение завершено.", reply_markup=get_main_menu())

@router.message(AIChat.waiting_for_question, F.text)
async def handle_ai_question(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target = data.get("ai_target", "all")
    
    processing_msg = await message.answer("🤖 Собираю данные и думаю...")
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # ттх принтеров, чтобы модель не выдумывала
    printers_specs = (
        "Технические характеристики нашей фермы 3D-принтеров:\n"
        "- Модели: Flashforge Adventurer 5M (все три принтера одинаковые)\n"
        "- Прошивка: Модифицированный Klipper / Forge-X от DrA1ex\n"
        "- Кинематика: CoreXY (сверхбыстрое перемещение, печать до 600 мм/с, ускорения до 20000 мм/с²)\n"
        "- Область печати: 220 x 220 x 220 мм\n"
        "- Экструдер: Direct Drive с быстросъемным соплом (макс. температура нагрева 280°C)\n"
        "- Подогреваемый стол: до 110°C, магнитная гибкая PEI пластина\n"
        "- Подключение: Wi-Fi/Ethernet через Moonraker API\n"
        "- Особенности: Датчик окончания филамента, автокалибровка стола, компенсация резонансов (Input Shaping)\n"
    )
    
    if target == "all":
        printers_data = await get_all_printers_data()
        prompt_addition = (
            f"СПРАВОЧНАЯ ТЕХНИЧЕСКАЯ ИНФОРМАЦИЯ ФЕРМЫ:\n{printers_specs}\n"
            f"ТЕКУЩАЯ СЕТЕВАЯ ТЕЛЕМЕТРИЯ KLIPPER (3 ПРИНТЕРА):\n{printers_data}\n\n"
            f"Вопрос пользователя: '{message.text}'\n\n"
            f"Инструкция: Свободно ответь на вопрос пользователя на русском языке. "
            f"Если вопрос касается принтеров, печати, температур, ошибок или статуса — используй предоставленные "
            f"данные телеметрии для точного ответа. "
            f"Если вопрос на общую, шутливую или отвлеченную тему — свободно общайся как эрудированный, "
            f"живой и проницательный помощник, поддерживай диалог, но помни, что твоя роль — ИИ-управляющий этой фермой."
        )
    else:
        printer_id = target
        if printer_id not in PRINTERS:
            from src.handlers.menu import get_main_menu
            await processing_msg.edit_text("Принтер не найден.", reply_markup=get_main_menu())
            return
        printer = PRINTERS[printer_id]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            p_data = await fetch_printer_data(session, printer["name"], printer["ip"])
        printers_data = [p_data]
        prompt_addition = (
            f"СПРАВОЧНАЯ ТЕХНИЧЕСКАЯ ИНФОРМАЦИЯ ФЕРМЫ:\n{printers_specs}\n"
            f"ТЕКУЩАЯ СЕТЕВАЯ ТЕЛЕМЕТРИЯ ВЫБРАННОГО ПРИНТЕРА ({printer['name']}):\n{p_data}\n\n"
            f"Вопрос пользователя: '{message.text}'\n\n"
            f"Инструкция: Свободно ответь на вопрос пользователя на русском языке. "
            f"Сделай акцент на анализе состояния именно {printer['name']}. Используй предоставленные "
            f"данные телеметрии для точного ответа. Если вопрос на отвлеченную тему — общайся свободно и живо."
        )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Завершить общение", callback_data="cancel_ai")]])
    
    response_text = await generate_report_from_llm(
        data=printers_data, 
        prompt_addition=prompt_addition, 
        system_instruction=CHAT_INSTRUCTION
    )
    
    await processing_msg.edit_text(response_text, reply_markup=markup)
