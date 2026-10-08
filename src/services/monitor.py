import asyncio
import logging
from aiogram import Bot

from src.config import PRINTERS, POLL_INTERVAL, USER_ID
from src.client.moonraker import get_all_printers_data

logger = logging.getLogger(__name__)

# последнее известное состояние, алерт шлется только при смене
previous_states = {p["name"]: "unknown" for p in PRINTERS.values()}

async def monitor_printers_background(bot: Bot):
    logger.info("Мониторинг принтеров запущен")
    while True:
        try:
            printers_data = await get_all_printers_data()
            alerts = []
            
            for p_data in printers_data:
                name = p_data["name"]
                prev_state = previous_states.get(name, "unknown")
                
                if p_data["status"] != "online":
                    current_state = "offline"
                else:
                    try:
                        current_state = p_data["data"]["result"]["status"]["print_stats"]["state"]
                    except KeyError:
                        current_state = "unknown"
                
                if prev_state != "unknown" and prev_state != current_state:
                    if prev_state != "offline" and current_state == "offline":
                        error_msg = p_data.get("error_msg", "Нет связи (таймаут)")
                        alerts.append(f"🔌 <b>{name}</b> потерял связь (офлайн).\n⚠️ Ошибка: <code>{error_msg}</code>")
                    elif prev_state == "offline" and current_state != "offline":
                        alerts.append(f"🟢 <b>{name}</b> снова в сети.")
                    elif current_state != "offline":
                        if prev_state == "printing" and current_state in ("complete", "standby"):
                            alerts.append(f"✅ <b>{name}</b> успешно завершил печать! Пора снять деталь.")
                        elif current_state == "error":
                            klipper_err = "Неизвестный сбой Klipper"
                            try:
                                klipper_err = p_data["data"]["result"]["status"].get("print_stats", {}).get("message", "Неизвестный сбой")
                            except Exception:
                                pass
                            alerts.append(f"❌ <b>{name}</b> перешел в состояние ошибки!\n⚠️ Ошибка Klipper: <code>{klipper_err}</code>")
                        elif prev_state == "printing" and current_state in ("paused", "cancelled"):
                            state_rus = "приостановлена" if current_state == "paused" else "отменена"
                            alerts.append(f"⚠️ <b>{name}</b>: печать {state_rus}.")
                
                previous_states[name] = current_state

            if alerts:
                logger.info(f"Сработал триггер изменений состояния принтеров: {alerts}")
                
                # без gemini: уведомления должны доходить, даже если прокси лежит
                message_text = "<b>🔔 Уведомление фермы 3D-принтеров</b>\n\n"
                message_text += "\n\n".join(alerts)
                
                message_text += "\n\n<b>🌡 Актуальные температуры:</b>\n"
                for p_data in printers_data:
                    p_name = p_data["name"]
                    if p_data["status"] == "online":
                        try:
                            result = p_data["data"]["result"]["status"]
                            bed_temp = result.get("heater_bed", {}).get("temperature", 0)
                            ext_temp = result.get("extruder", {}).get("temperature", 0)
                            message_text += f"- {p_name}: Экструдер {ext_temp:.1f}°C | Стол {bed_temp:.1f}°C\n"
                        except Exception:
                            message_text += f"- {p_name}: Ошибка чтения сенсоров\n"
                    else:
                        message_text += f"- {p_name}: 🔴 Недоступен\n"
                
                await bot.send_message(chat_id=USER_ID, text=message_text)
                
        except Exception as e:
             logger.error(f"Ошибка в фоновом мониторинге: {e}")
             
        await asyncio.sleep(POLL_INTERVAL)
