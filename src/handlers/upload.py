import os
import time
import logging
import urllib.parse
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.config import PRINTERS
from src.client.moonraker import fetch_printer_data, upload_gcode_file, start_gcode_print

logger = logging.getLogger(__name__)
router = Router()

class UploadGcode(StatesGroup):
    waiting_for_file = State()

@router.callback_query(F.data.startswith("up_") | F.data.startswith("upprint_"))
async def cb_prepare_upload(callback: CallbackQuery, state: FSMContext):
    action, printer_id = callback.data.split("_")
    auto_print = (action == "upprint")
    printer = PRINTERS.get(printer_id)
    if not printer:
        return
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        data = await fetch_printer_data(session, printer["name"], printer["ip"])
        
    if data.get("status") == "online":
        try:
            p_state = data["data"]["result"]["status"]["print_stats"]["state"]
            if p_state in ("printing", "paused"):
                await callback.answer("❌ Принтер сейчас занят!", show_alert=True)
                return
        except KeyError:
            pass
    else:
        await callback.answer("❌ Принтер недоступен!", show_alert=True)
        return
        
    await state.update_data(printer_id=printer_id, auto_print=auto_print, timestamp=time.time())
    await state.set_state(UploadGcode.waiting_for_file)
    
    mode = "загрузки и печати" if auto_print else "загрузки"
    await callback.message.edit_text(
        f"Отправьте файл .gcode для {mode} на {printer['name']} в течение 1 минуты.", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="upload_cancel")]])
    )

@router.callback_query(UploadGcode.waiting_for_file, F.data == "upload_cancel")
async def cb_upload_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from src.handlers.menu import get_main_menu
    await callback.message.edit_text("Загрузка отменена.", reply_markup=get_main_menu())

@router.message(UploadGcode.waiting_for_file, F.document, F.document.file_name.endswith(".gcode"))
async def handle_gcode(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    from src.handlers.menu import get_main_menu
    
    if time.time() - data.get("timestamp", 0) > 60:
        await state.clear()
        await message.answer("⏳ Время ожидания вышло. Пожалуйста, начните заново.", reply_markup=get_main_menu())
        return
        
    if message.document.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой! Лимит Telegram 20 МБ.")
        return
        
    printer_id = data["printer_id"]
    auto_print = data["auto_print"]
    printer = PRINTERS[printer_id]
    
    file_id = message.document.file_id
    file_name = message.document.file_name
    
    await message.answer(f"Скачиваю файл {file_name} и загружаю на {printer['name']}...")
    
    file = await bot.get_file(file_id)
    file_path = f"{file_id}_{file_name}"
    
    try:
        await bot.download_file(file.file_path, file_path)
        
        status = await upload_gcode_file(printer["ip"], file_path, file_name)
        if status == 201:
            if auto_print:
                start_status = await start_gcode_print(printer["ip"], file_name)
                if start_status == 200:
                    await message.answer(f"🚀 Печать файла {file_name} на {printer['name']} успешно запущена!", reply_markup=get_main_menu())
                else:
                    await message.answer(f"Файл загружен, но ошибка запуска печати: {start_status}", reply_markup=get_main_menu())
            else:
                await message.answer(f"✅ Файл {file_name} успешно загружен на {printer['name']}.", reply_markup=get_main_menu())
        else:
            await message.answer(f"Ошибка загрузки на {printer['name']}: HTTP {status}", reply_markup=get_main_menu())
    except Exception as e:
        await message.answer(f"Ошибка при загрузке: {e}", reply_markup=get_main_menu())
    finally:
        await state.clear()
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as ex:
                logger.error(f"Не удалось удалить временный файл {file_path}: {ex}")

@router.message(F.document, F.document.file_name.endswith(".gcode"))
async def handle_gcode_no_state(message: Message):
    # если файл прислали просто так, без выбора принтера
    await message.answer("Сначала зайдите в меню нужного принтера и выберите 'Загрузить файл' или 'Загрузить и печатать'.")
