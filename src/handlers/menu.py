import logging
import aiohttp
from typing import Dict, Any, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from src.config import PRINTERS, MOONRAKER_PORT
from src.client.moonraker import fetch_printer_data, get_all_printers_data

logger = logging.getLogger(__name__)
router = Router()

def get_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🦾 Принтер 1", callback_data="status_1"),
            InlineKeyboardButton(text="⚡ Принтер 2", callback_data="status_2")
        ],
        [
            InlineKeyboardButton(text="🚀 Принтер 3", callback_data="status_3"),
            InlineKeyboardButton(text="🏭 Все принтеры", callback_data="status_all")
        ],
        [
            InlineKeyboardButton(text="🤖 Спросить у агента", callback_data="ai_all")
        ]
    ])

def generate_printer_status_text(printer_name: str, data: Dict[str, Any]) -> str:
    if data.get("status") != "online":
         return f"🧊 <b>{printer_name}</b>: 🔴 Недоступен ({data.get('error_msg', 'Нет связи')})"
         
    try:
         result = data["data"]["result"]["status"]
         state = result.get("print_stats", {}).get("state", "unknown")
         filename = result.get("print_stats", {}).get("filename", "")
         progress = result.get("display_status", {}).get("progress", 0)
         
         bed_temp = result.get("heater_bed", {}).get("temperature", 0)
         bed_target = result.get("heater_bed", {}).get("target", 0)
         
         ext_temp = result.get("extruder", {}).get("temperature", 0)
         ext_target = result.get("extruder", {}).get("target", 0)
         
         text = f"🧊 <b>{printer_name}</b>: 🟢 Онлайн\n"
         text += f"Состояние: <b>{state}</b>\n"
         if state in ("printing", "paused") and filename:
             text += f"Файл: <code>{filename}</code>\n"
             text += f"Прогресс: <b>{progress * 100:.1f}%</b>\n"
             
             # оставшееся время по пропорции от уже прошедшего
             print_duration = result.get("print_stats", {}).get("print_duration", 0)
             if progress > 0.001 and progress < 1.0:
                 remaining_seconds = (1.0 - progress) * (print_duration / progress)
                 hours = int(remaining_seconds // 3600)
                 minutes = int((remaining_seconds % 3600) // 60)
                 seconds = int(remaining_seconds % 60)
                 if hours > 0:
                     eta_str = f"<b>{hours} ч. {minutes} мин.</b>"
                 else:
                     eta_str = f"<b>{minutes} мин. {seconds} сек.</b>"
                 text += f"⏱ Осталось времени: {eta_str}\n"
             elif progress >= 1.0:
                 text += "⏱ Осталось времени: <b>Готово</b>\n"
             else:
                 text += "⏱ Осталось времени: <b>Расчет...</b>\n"
             
         text += f"🌡 Экструдер: {ext_temp:.1f}°C / {ext_target:.1f}°C\n"
         text += f"🌡 Стол: {bed_temp:.1f}°C / {bed_target:.1f}°C"
         
         return text
    except Exception as e:
         return f"🧊 <b>{printer_name}</b>: 🟠 Ошибка разбора данных ({e})"

def generate_all_printers_status_text(printers_data: List[Dict[str, Any]]) -> str:
    return "\n\n".join(generate_printer_status_text(p["name"], p) for p in printers_data)

@router.message(Command("start", "menu"))
async def cmd_start(message: Message):
    await message.answer("Управление фермой 3D-принтеров. Выберите действие:", reply_markup=get_main_menu())

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=get_main_menu())

@router.callback_query(F.data == "status_all")
async def cb_status_all(callback: CallbackQuery):
    await callback.message.edit_text("🔄 Опрашиваю все принтеры...")
    printers_data = await get_all_printers_data()
    text = generate_all_printers_status_text(printers_data)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data.startswith("status_"))
async def cb_status_single(callback: CallbackQuery):
    printer_id = callback.data.split("_")[1]
    if printer_id not in PRINTERS:
        return
    printer = PRINTERS[printer_id]
    await callback.message.edit_text(f"🔄 Опрашиваю {printer['name']}...")
    
    from src.client.moonraker import API_TIMEOUT
    async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
        data = await fetch_printer_data(session, printer["name"], printer["ip"])
    
    printer_state = "standby"
    if data.get("status") == "online":
        try:
            printer_state = data["data"]["result"]["status"]["print_stats"]["state"]
        except KeyError:
            pass
            
    text = generate_printer_status_text(printer["name"], data)
    from src.handlers.control import get_printer_control_menu
    reply_markup = get_printer_control_menu(printer_id, printer_state)
    await callback.message.edit_text(text, reply_markup=reply_markup)

@router.message()
async def fallback_message(message: Message):
    await message.answer("Я не понимаю это сообщение. Воспользуйтесь меню:", reply_markup=get_main_menu())
