# 03 · Кодовая база бота

## Структура проекта

```
bot_tg/
├── .env                    # Секреты и переменные окружения
├── Dockerfile              # python:3.10-slim, pip install, CMD python bot.py
├── docker-compose.yml      # Два сервиса: bot + proxy
├── requirements.txt        # aiogram 3.4.1, aiohttp 3.9.3, google-generativeai, aiohttp-socks
├── sing-box-config.json    # VLESS Reality прокси-конфиг
├── bot.py                  # Точка входа: Bot, Dispatcher, роутеры, фоновый мониторинг
│
└── src/
    ├── __init__.py
    ├── config.py            # Загрузка .env, конфигурация принтеров, промпты Gemini
    │
    ├── client/
    │   ├── moonraker.py     # Асинхронный HTTP-клиент для Klipper Moonraker API
    │   └── gemini.py        # Клиент Google Gemini с очисткой HTML и потоковой генерацией
    │
    ├── handlers/
    │   ├── menu.py          # /start, /menu, статусы принтеров, fallback-обработчик
    │   ├── control.py       # Пауза/Продолжить/Отмена, кнопки Fluidd Web App и Камера
    │   ├── upload.py        # FSM загрузки G-code файлов с таймаутом 60 сек
    │   └── chat.py          # FSM диалога с ИИ-агентом + спецификации принтеров
    │
    ├── middlewares/
    │   └── auth.py          # AuthMiddleware: белый список + код доступа из `ACCESS_CODE`
    │
    └── services/
        └── monitor.py       # Фоновый цикл опроса (30 сек), статические HTML-алерты
```

## bot.py — Точка входа

```python
# Ключевая логика:
1. Загружает BOT_TOKEN из config
2. Создаёт AiohttpSession(proxy=TG_PROXY or GEMINI_PROXY) для обхода блокировки Telegram API
3. Инициализирует Bot(parse_mode=HTML) + Dispatcher
4. Регистрирует AuthMiddleware глобально (message + callback_query)
5. Подключает роутеры в порядке: chat → upload → control → menu (menu последний — содержит fallback)
6. Запускает asyncio.create_task(monitor_printers_background(bot))
7. Стартует dp.start_polling(bot)
```

> **Важно:** Порядок регистрации роутеров критичен. `menu.router` содержит `@router.message()` без фильтров (fallback), поэтому должен быть последним.

## src/config.py — Конфигурация

### Переменные окружения (.env)
| Переменная | Назначение | Пример |
|------------|------------|--------|
| `BOT_TOKEN` | Telegram Bot API токен | `123456:ABC...` |
| `USER_ID` | Telegram ID владельца (для алертов и авторизации) | `<YOUR_TELEGRAM_ID>` |
| `GEMINI_API_KEY` | Google AI API ключ | `<ключ>` |
| `WEBAPP_URL_1/2/3` | URL Fluidd Web App для каждого принтера | `https://printer.example.com` |
| `CAMERA_URL_1/2/3` | URL MJPEG-стрима камеры | `https://printer.example.com/p1/webcam/?action=stream` |
| `GEMINI_PROXY` | HTTP-прокси для Gemini и Telegram API | `http://proxy:1080` |

### Конфигурация принтеров (словарь PRINTERS)
```python
PRINTERS = {
    "1": {"name": "Принтер 1", "ip": "192.168.10.101", "webapp_url": "...", "camera_url": "..."},
    "2": {"name": "Принтер 2", "ip": "192.168.10.102", "webapp_url": "...", "camera_url": "..."},
    "3": {"name": "Принтер 3", "ip": "192.168.10.103", "webapp_url": "...", "camera_url": ""},
}
```

### Константы
- `MOONRAKER_PORT = 7125`
- `POLL_INTERVAL = 30` (секунды между опросами фонового мониторинга)

### Системные промпты Gemini
- `SYSTEM_INSTRUCTION` — для генерации отчётов (HTML-теги: `<b>`, `<i>`, `<code>`, `<pre>` только)
- `CHAT_INSTRUCTION` — для свободного диалога (адаптация под стиль собеседника)

## src/client/moonraker.py — Moonraker API клиент

### Таймауты
```python
API_TIMEOUT = aiohttp.ClientTimeout(total=3.0, connect=1.5)   # Обычные запросы
UPLOAD_TIMEOUT = aiohttp.ClientTimeout(total=15.0, connect=2.0) # Загрузка файлов
```

### Функции
| Функция | HTTP | Endpoint | Возвращает |
|---------|------|----------|------------|
| `fetch_printer_data(session, name, ip)` | GET | `/printer/objects/query?print_stats&extruder&heater_bed&display_status` | `Dict` со статусом, температурами, прогрессом |
| `get_all_printers_data()` | GET | (все 3 принтера параллельно через `asyncio.gather`) | `List[Dict]` |
| `pause_printer(ip)` | POST | `/printer/print/pause` | HTTP status code |
| `resume_printer(ip)` | POST | `/printer/print/resume` | HTTP status code |
| `cancel_printer(ip)` | POST | `/printer/print/cancel` | HTTP status code |
| `upload_gcode_file(ip, path, name)` | POST | `/server/files/upload` (multipart form) | HTTP status code |
| `start_gcode_print(ip, name)` | POST | `/printer/print/start?filename=...` | HTTP status code |

## src/client/gemini.py — Google Gemini AI клиент

### Прокси-настройка
При наличии `GEMINI_PROXY` устанавливает `HTTP_PROXY`, `HTTPS_PROXY` и `NO_PROXY=192.168.10.101,192.168.10.102,192.168.10.103,...`.

### Модель
```python
model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=BLOCK_NONE)
```

### Функции
| Функция | Назначение |
|---------|------------|
| `clean_html_for_telegram(text)` | Удаляет Markdown (`**`, `__`), запрещённые теги (`<p>`, `<br>`, `<h1>`), оставляет только `<b>`, `<i>`, `<code>`, `<pre>` |
| `generate_report_from_llm(data, prompt, instruction)` | Статичная генерация отчёта (asyncio.to_thread) |
| `stream_report_from_llm(data, message, ...)` | Потоковая генерация с обновлением сообщения каждые 1.5 сек (защита от Rate Limits) |

## src/handlers/menu.py — Главное меню

### Команды
- `/start`, `/menu` → главное меню с inline-кнопками

### Inline-кнопки главного меню
```
🦾 Принтер 1  |  ⚡ Принтер 2
🚀 Принтер 3  |  🏭 Все принтеры
      🤖 Спросить у агента
```

### Ключевые функции
| Функция | Callback | Назначение |
|---------|----------|------------|
| `cb_status_all` | `status_all` | Опрос всех 3 принтеров параллельно |
| `cb_status_single` | `status_1/2/3` | Опрос одного принтера + меню управления |
| `generate_printer_status_text` | — | HTML-шаблон: состояние, файл, прогресс, ETA, температуры |
| `fallback_message` | `@router.message()` | Ловит все необработанные сообщения |

### Расчёт ETA
```python
remaining_seconds = (1.0 - progress) * (print_duration / progress)
# Выводит: "⏱ Осталось времени: X ч. Y мин."
```

## src/handlers/control.py — Управление печатью

### Кнопки управления (зависят от состояния)
**Во время печати (printing/paused):**
```
⏸ Пауза  |  ▶️ Продолжить
      🛑 Отменить печать
🌐 Открыть Fluidd  |  🎥 Камера принтера
          🔙 Назад в меню
```

**В режиме ожидания:**
```
📥 Загрузить файл
🖨 Загрузить и печатать
🌐 Открыть Fluidd  |  🎥 Камера принтера
          🔙 Назад в меню
```

### Web App кнопки
- `🌐 Открыть Fluidd` → `WebAppInfo(url=printer["webapp_url"])` — открывает `https://printer.example.com` в Telegram
- `🎥 Камера принтера` → `WebAppInfo(url=printer["camera_url"])` — открывает MJPEG-стрим в Telegram
- Камера скрыта для Принтера 3 (физически отсутствует, `camera_url=""`)

> **Ограничение:** Web App в Telegram работает через встроенный браузер, который может обходить VPN телефона. Результат — `403 Forbidden` от Caddy. Рекомендуется использовать обычный мобильный браузер + WireGuard VPN.

## src/handlers/upload.py — Загрузка G-code (FSM)

### Машина состояний (FSM)
```
cb_prepare_upload (callback: up_N / upprint_N)
    → Проверка: принтер онлайн? не печатает?
    → state = UploadGcode.waiting_for_file
    → Таймер: 60 секунд

handle_gcode (message: .gcode документ)
    → Скачивание файла через bot.download_file
    → upload_gcode_file → /server/files/upload
    → [если auto_print] start_gcode_print → /printer/print/start
    → Очистка FSM и временного файла
```

### Ограничения
- Максимальный размер файла: 20 МБ (лимит Telegram)
- Таймаут загрузки: 15 секунд
- Таймаут ожидания файла от пользователя: 60 секунд

## src/handlers/chat.py — ИИ-чат (FSM)

### Машина состояний
```
cb_ask_ai (callback: ai_all / ai_N)
    → state = AIChat.waiting_for_question

handle_ai_question (message: текст)
    → Показ "typing..." в чате
    → Сбор телеметрии всех/одного принтера
    → Формирование промпта с ТТХ фермы + живые данные Klipper
    → generate_report_from_llm (статичный ответ, без стриминга)
    → Вывод ответа целиком
```

### ТТХ принтеров (вшиты в промпт)
```
- Модель: Flashforge Adventurer 5M
- Прошивка: Klipper / Forge-X (DrA1ex)
- Кинематика: CoreXY, до 600 мм/с, ускорения до 20000 мм/с²
- Область печати: 220×220×220 мм
- Экструдер: Direct Drive, до 280°C
- Стол: до 110°C, магнитная PEI
```

## src/middlewares/auth.py — Авторизация

### Логика
1. Владелец (`USER_ID` из `.env`) авторизован автоматически
2. Другие пользователи могут получить доступ, отправив код доступа из `ACCESS_CODE`
3. Авторизованные пользователи хранятся в `AUTH_USERS` (in-memory set)
4. Неавторизованным: "Введите ключ доступа:"

> **Известное ограничение:** `AUTH_USERS` хранится в памяти — при перезапуске контейнера все дополнительные пользователи теряют авторизацию (кроме владельца).

## src/services/monitor.py — Фоновый мониторинг

### Цикл работы
```
Каждые 30 секунд:
  → get_all_printers_data() (все 3 параллельно)
  → Сравнение с предыдущими состояниями
  → При изменении → HTML-алерт → bot.send_message(USER_ID)
```

### Детектируемые события
| Переход | Алерт |
|---------|-------|
| online → offline | 🔌 Принтер X потерял связь (офлайн) |
| offline → online | 🟢 Принтер X снова в сети |
| printing → complete/standby | ✅ Принтер X завершил печать! Пора снять деталь |
| * → error | ❌ Принтер X в состоянии ошибки + код Klipper |
| printing → paused/cancelled | ⚠️ Принтер X: печать приостановлена/отменена |

### Формат алерта
```html
<b>🔔 Уведомление фермы 3D-принтеров</b>

✅ <b>Принтер 1</b> успешно завершил печать! Пора снять деталь.

<b>🌡 Актуальные температуры:</b>
- Принтер 1: Экструдер 25.3°C | Стол 24.1°C
- Принтер 2: 🔴 Недоступен
- Принтер 3: Экструдер 23.8°C | Стол 22.5°C
```

> **Важно:** Алерты генерируются **без участия Gemini AI** — чисто статические HTML-шаблоны. Поэтому уведомления доходят независимо от доступности прокси или Gemini API.
