import aiohttp
import urllib.parse
from typing import Dict, Any, List
from src.config import PRINTERS, MOONRAKER_PORT

# короткие таймауты, иначе выключенный принтер подвешивает кнопки
API_TIMEOUT = aiohttp.ClientTimeout(total=3.0, connect=1.5)

async def fetch_printer_data(session: aiohttp.ClientSession, name: str, ip: str) -> Dict[str, Any]:
    url = f"http://{ip}:{MOONRAKER_PORT}/printer/objects/query?print_stats&extruder&heater_bed&display_status"
    try:
        async with session.get(url, timeout=API_TIMEOUT) as response:
            if response.status == 200:
                data = await response.json()
                return {"name": name, "ip": ip, "status": "online", "data": data}
            else:
                return {"name": name, "ip": ip, "status": "error", "error_msg": f"HTTP {response.status}"}
    except Exception as e:
        return {"name": name, "ip": ip, "status": "offline", "error_msg": "Нет связи (таймаут)"}

async def get_all_printers_data() -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
        tasks = [fetch_printer_data(session, p["name"], p["ip"]) for p in PRINTERS.values()]
        from asyncio import gather
        return list(await gather(*tasks))

async def pause_printer(ip: str) -> int:
    url = f"http://{ip}:{MOONRAKER_PORT}/printer/print/pause"
    async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
        async with session.post(url) as response:
            return response.status

async def resume_printer(ip: str) -> int:
    url = f"http://{ip}:{MOONRAKER_PORT}/printer/print/resume"
    async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
        async with session.post(url) as response:
            return response.status

async def cancel_printer(ip: str) -> int:
    url = f"http://{ip}:{MOONRAKER_PORT}/printer/print/cancel"
    async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
        async with session.post(url) as response:
            return response.status

async def upload_gcode_file(ip: str, file_path: str, file_name: str) -> int:
    url = f"http://{ip}:{MOONRAKER_PORT}/server/files/upload"
    UPLOAD_TIMEOUT = aiohttp.ClientTimeout(total=15.0, connect=2.0)
    async with aiohttp.ClientSession(timeout=UPLOAD_TIMEOUT) as session:
        with open(file_path, 'rb') as f:
            form = aiohttp.FormData()
            form.add_field('file', f, filename=file_name)
            async with session.post(url, data=form) as response:
                return response.status

async def start_gcode_print(ip: str, file_name: str) -> int:
    encoded_filename = urllib.parse.quote(file_name)
    url = f"http://{ip}:{MOONRAKER_PORT}/printer/print/start?filename={encoded_filename}"
    async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
        async with session.post(url) as response:
            return response.status
