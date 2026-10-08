# 04 · Деплой и контейнеризация

## Расположение на сервере atlas

```
/home/kovis/printernaya/Bot/
├── .env
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── sing-box-config.json
├── bot.py
└── src/
    └── ... (модульная кодовая база)
```

- **Пользователь:** `kovis` (группа `docker`, NOPASSWD-sudo)
- **SSH-доступ:** `ssh kovis@192.168.1.204` (ключ ed25519)

## Docker Compose стек

```yaml
version: '3.8'
services:
  bot:
    build: .
    container_name: 3dprinter_bot
    restart: unless-stopped
    depends_on:
      - proxy
    env_file:
      - .env

  proxy:
    image: ghcr.io/sagernet/sing-box:latest
    container_name: 3dprinter_proxy
    restart: unless-stopped
    command: run -c /etc/sing-box/config.json
    volumes:
      - ./sing-box-config.json:/etc/sing-box/config.json
```

### Docker-сеть
Оба контейнера автоматически попадают в одну bridge-сеть Docker Compose. Бот обращается к прокси по имени `proxy:1080`.

## Dockerfile

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

## Зависимости (requirements.txt)

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `aiogram` | 3.4.1 | Telegram Bot Framework (async) |
| `aiohttp` | 3.9.3 | HTTP-клиент для Moonraker API |
| `python-dotenv` | 1.0.1 | Загрузка .env файлов |
| `google-generativeai` | ≥0.5.2 | Google Gemini AI SDK |
| `aiohttp-socks` | latest | SOCKS/HTTP proxy для aiogram |

## Процедура деплоя (обновление кода)

### 1. Копирование файлов с локальной машины
```bash
# Из PowerShell на Windows (исключая venv):
scp -r bot.py Dockerfile docker-compose.yml requirements.txt .env sing-box-config.json src kovis@192.168.1.204:/home/kovis/printernaya/Bot/
```



### 2. Пересборка и запуск
```bash
ssh kovis@192.168.1.204
cd /home/kovis/printernaya/Bot
docker compose up -d --build
```

### 3. Проверка
```bash
docker compose ps          # Статус контейнеров
docker logs 3dprinter_bot --tail 30  # Логи бота
docker logs 3dprinter_proxy --tail 10  # Логи прокси
```

## Переменные окружения (.env)

```env
BOT_TOKEN=<токен от @BotFather>
USER_ID=<YOUR_TELEGRAM_ID>
GEMINI_API_KEY=<ключ Google AI Studio>

WEBAPP_URL_1=https://printer.example.com
WEBAPP_URL_2=https://printer.example.com
WEBAPP_URL_3=https://printer.example.com

CAMERA_URL_1=https://printer.example.com/p1/webcam/?action=stream
CAMERA_URL_2=https://printer.example.com/p2/webcam/?action=stream
CAMERA_URL_3=

GEMINI_PROXY=http://proxy:1080
```



## Известная проблема: Docker bind-mount inode trap

При обновлении файлов через `mv newfile oldfile` (например, обновление `Caddyfile`) создаётся **новый inode**, а bind-mount одиночного файла в контейнер привязан к старому. Контейнер перестаёт видеть изменения до рестарта.

**Решение:** Использовать `cat newcontent > existingfile` (сохраняет inode) или `docker restart <container>`.
