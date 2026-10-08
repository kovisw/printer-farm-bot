import asyncio
import time
import re
import logging
import os
from typing import Any
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from aiogram.types import Message
from src.config import GEMINI_API_KEY, SYSTEM_INSTRUCTION, CHAT_INSTRUCTION, GEMINI_PROXY

logger = logging.getLogger(__name__)

# gemini не работает с российских ip, поэтому через прокси
if GEMINI_PROXY:
    os.environ["HTTP_PROXY"] = GEMINI_PROXY
    os.environ["HTTPS_PROXY"] = GEMINI_PROXY
    os.environ["http_proxy"] = GEMINI_PROXY
    os.environ["https_proxy"] = GEMINI_PROXY
    # принтеры должны идти напрямую через wireguard
    os.environ["NO_PROXY"] = "192.168.10.101,192.168.10.102,192.168.10.103,127.0.0.1,localhost,192.168.10.0/24"
    logger.info(f"Gemini через прокси: {GEMINI_PROXY}")

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
)

def clean_html_for_telegram(text: str) -> str:
    # телеграм падает на <p>, <br> и т.п., а gemini их все равно иногда пишет
    text = re.sub(r"\*\*|\_\_", "", text)
    
    text = text.replace("<p>", "").replace("</p>", "\n")
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    
    text = re.sub(r"</?h[1-6]>", "\n", text)
    
    # остальные теги кроме разрешенных просто вырезаем
    allowed_tags = ["b", "i", "code", "pre"]
    
    tags = re.findall(r"<[^>]+>", text)
    for tag in tags:
        match = re.match(r"^</?([a-zA-Z0-9]+)", tag)
        if match:
            tag_name = match.group(1).lower()
            if tag_name not in allowed_tags:
                text = text.replace(tag, "")
        else:
            text = text.replace(tag, "")
            
    return text.strip()

async def generate_report_from_llm(data: Any, prompt_addition: str = "", system_instruction: str = SYSTEM_INSTRUCTION) -> str:
    data_str = str(data)
    base_prompt = (
        f"{prompt_addition}\n\nДанные для анализа:\n{data_str}" 
        if prompt_addition 
        else f"Проанализируй эти данные от 3D-принтеров и выдай короткий отчет:\n{data_str}"
    )
    prompt = f"{system_instruction}\n\n{base_prompt}"
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return clean_html_for_telegram(response.text)
    except Exception as e:
        logger.error(f"Ошибка при запросе к Gemini: {e}")
        return f"⚠️ Ошибка при генерации отчета Gemini: {e}"

async def stream_report_from_llm(
    data: Any, 
    message: Message, 
    reply_markup=None, 
    prompt_addition: str = "", 
    system_instruction: str = SYSTEM_INSTRUCTION
):
    # сейчас не используется - стриминг упирался в лимиты телеграма на edit_text
    data_str = str(data)
    base_prompt = (
        f"{prompt_addition}\n\nДанные для анализа:\n{data_str}" 
        if prompt_addition 
        else f"Проанализируй эти данные от 3D-принтеров и выдай короткий отчет:\n{data_str}"
    )
    prompt = f"{system_instruction}\n\n{base_prompt}"
    
    current_text = ""
    last_edit = 0
    try:
        response = await model.generate_content_async(prompt, stream=True)
        async for chunk in response:
            current_text += chunk.text
            if time.time() - last_edit > 1.5:
                clean_text = clean_html_for_telegram(current_text)
                try:
                    await message.edit_text(clean_text + " ✍️...", reply_markup=reply_markup)
                    last_edit = time.time()
                except Exception:
                    pass
                    
        clean_text = clean_html_for_telegram(current_text)
        try:
            await message.edit_text(clean_text, reply_markup=reply_markup)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка при потоковой генерации: {e}")
        try:
            await message.edit_text(f"⚠️ Ошибка при генерации отчета: {e}", reply_markup=reply_markup)
        except Exception:
            pass
