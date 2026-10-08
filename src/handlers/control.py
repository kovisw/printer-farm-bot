import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from src.config import PRINTERS
from src.client.moonraker import pause_printer, resume_printer, cancel_printer

logger = logging.getLogger(__name__)
router = Router()

def get_printer_control_menu(printer_id: str, state: str) -> InlineKeyboardMarkup:
    buttons = []
    
    if state in ("printing", "paused"):
        buttons.append([
            InlineKeyboardButton(text="⏸ Пауза", callback_data=f"pause_{printer_id}"),
            InlineKeyboardButton(text="▶️ Продолжить", callback_data=f"resume_{printer_id}")
        ])
        buttons.append([InlineKeyboardButton(text="🛑 Отменить печать", callback_data=f"cancel_{printer_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="📥 Загрузить файл", callback_data=f"up_{printer_id}")])
        buttons.append([InlineKeyboardButton(text="🖨 Загрузить и печатать", callback_data=f"upprint_{printer_id}")])
        
    # fluidd и камера открываются как web app
    printer = PRINTERS.get(printer_id)
    if printer:
        row = []
        if printer.get("webapp_url"):
            row.append(InlineKeyboardButton(
                text="🌐 Открыть Fluidd", 
                web_app=WebAppInfo(url=printer["webapp_url"])
            ))
        if printer.get("camera_url"):
            row.append(InlineKeyboardButton(
                text="🎥 Камера принтера", 
                web_app=WebAppInfo(url=printer["camera_url"])
            ))
        if row:
            buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("pause_"))
async def cb_pause(callback: CallbackQuery):
    printer_id = callback.data.split("_")[1]
    printer = PRINTERS.get(printer_id)
    if not printer:
        return
        
    status = await pause_printer(printer["ip"])
    if status == 200:
        await callback.answer(f"Печать на {printer['name']} поставлена на паузу.", show_alert=True)
    else:
        await callback.answer(f"Ошибка паузы: HTTP {status}", show_alert=True)

@router.callback_query(F.data.startswith("cancel_"))
async def cb_cancel(callback: CallbackQuery):
    printer_id = callback.data.split("_")[1]
    printer = PRINTERS.get(printer_id)
    if not printer:
        return
        
    status = await cancel_printer(printer["ip"])
    if status == 200:
        await callback.answer(f"Печать на {printer['name']} отменена.", show_alert=True)
    else:
        await callback.answer(f"Ошибка отмены: HTTP {status}", show_alert=True)

@router.callback_query(F.data.startswith("resume_"))
async def cb_resume(callback: CallbackQuery):
    printer_id = callback.data.split("_")[1]
    printer = PRINTERS.get(printer_id)
    if not printer:
        return
        
    status = await resume_printer(printer["ip"])
    if status == 200:
        await callback.answer(f"Печать на {printer['name']} возобновлена.", show_alert=True)
    else:
        await callback.answer(f"Ошибка возобновления: HTTP {status}", show_alert=True)
