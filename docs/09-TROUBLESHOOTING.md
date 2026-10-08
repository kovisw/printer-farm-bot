# 09 · Книга ошибок и устранение неполадок

## 🔴 Критические проблемы

### 1. Принтер отвалился (офлайн)
**Симптомы:** Бот не видит принтер. Оранжевая лампочка на Ethernet-разъёме принтера.

**Диагностика:**
```bash
# С сервера atlas:
ping -c 3 192.168.10.10N
nmap -sn 192.168.10.100-103
```

**Решение:** Перезагрузка принтера по питанию (тумблер сзади). Ждать ~60 секунд до инициализации сети.

**Причина:** DHCP-клиент (`udhcpc`) на BusyBox иногда зависает при переподключении Ethernet.

---

### 2. ServerDisconnectedError (Telegram API)
**Симптомы:** Бот крашится с `aiohttp.client_exceptions.ServerDisconnectedError`, не может получать обновления.

**Причина:** Провайдер Ростелеком фильтрует `api.telegram.org`.

**Решение:** Убедиться, что прокси-сайдкар работает:
```bash
docker ps --filter name=3dprinter_proxy
docker logs 3dprinter_proxy --tail 20
```
Перезапуск: `docker compose restart proxy`

---

### 3. 403 Forbidden при открытии Fluidd/камеры в Telegram
**Симптомы:** Кнопка Web App в Telegram показывает пустую страницу или ошибку 403.

**Причина:** Встроенный браузер Telegram Web App **обходит VPN** телефона и отправляет запросы с публичного IP. Caddy видит этот IP и блокирует.

**Решение:** Использовать обычный браузер + WireGuard VPN на телефоне. Web App кнопки — только для информации.

---

### 4. Gemini API ошибки (403/429)
**Симптомы:** ИИ-отчёты не генерируются, в логах `Error generating report from Gemini`.

**Причины:**
- Прокси не работает → проверить `docker logs 3dprinter_proxy`
- Исчерпан лимит API ключа → подождать или сменить ключ
- Геоблок сменился → проверить, что прокси-IP не в России

**Проверка:**
```bash
docker exec 3dprinter_bot python -c "import google.generativeai as genai; genai.configure(api_key='...'); print('OK')"
```

## 🟡 Типовые ошибки разработки

### 5. Git Bash пути на Windows
**Ошибка:** `scp` с путями вида `/c/Users/...` — Git Bash конвертирует `C:\` в MSYS-путь.

**Решение:** Использовать PowerShell, а не Git Bash, для `scp` и `ssh` команд.

---

### 6. Копирование venv через SCP
**Ошибка:** `scp -r ./ ...` копирует venv с Windows → Linux. Python ломается в Docker.

**Решение:** Никогда не копировать `venv/`. Указывать файлы явно:
```bash
scp -r bot.py Dockerfile docker-compose.yml requirements.txt .env sing-box-config.json src kovis@192.168.1.204:/home/kovis/printernaya/Bot/
```

---

### 7. moonraker.conf заблокирован (read-only)
**Ошибка:** Moonraker не даёт редактировать `moonraker.conf` — файл помечен как `reserved`.

**Решение:** Использовать `user.moonraker.conf` (путь: `mod_data/user.moonraker.conf`). Он не заблокирован и применяется поверх основного.

---

### 8. Нет systemctl на принтере
**Ошибка:** `systemctl restart moonraker` → `command not found`.

**Причина:** Принтеры работают на BusyBox (не systemd).

**Решение:** Перезапуск через API: `POST /server/restart` или `/etc/init.d/S99root restart`.

---

### 9. Timeout при опросе принтера (зависает UI)
**Ошибка:** При оффлайн-принтере бот "зависает" на 60+ секунд перед ответом.

**Решение (уже применено):** Таймауты снижены до `connect=1.5s, total=3.0s`:
```python
API_TIMEOUT = aiohttp.ClientTimeout(total=3.0, connect=1.5)
```

---

### 10. Gemini streaming Rate Limits
**Ошибка:** Потоковая генерация вызывает `TelegramRetryAfter` (429) — Telegram не даёт обновлять сообщение чаще 1 раза в секунду.

**Решение (уже применено):** Минимальный интервал обновления 1.5 сек:
```python
if time.time() - last_edit > 1.5:
    await message.edit_text(current_text + " ✍️...", ...)
```

---

### 11. Docker bind-mount inode trap
**Ошибка:** Обновление конфига через `mv tmp config` → контейнер не видит изменений.

**Причина:** `mv` создаёт новый inode; bind-mount привязан к старому.

**Решение:** `cat newcontent > existingfile` (сохраняет inode) или `docker restart`.

---

### 12. PowerShell `$(...)` expansion в SSH
**Ошибка:** Команда вида `ssh atlas 'cp file file.bak-$(date +%F)'` — PowerShell интерпретирует `$()` как свою подстановку.

**Решение:** Экранировать или использовать простые имена: `ssh atlas "cp file file.bak"`.

---

### 13. Caddy handle_path overlap
**Ошибка:** Вложенные пути (`/p1/webcam/*` внутри `/p1/*`) молча теряются при использовании `handle_path`.

**Причина:** Caddy consolidates overlapping matchers during config adaptation.

**Решение:** Использовать `route` вместо `handle_path`.

---

### 14. E0120 на экране, `pin PA8 used multiple times in config`
**Причина:** заводская прошивка (после самообновления до 5.1.9) подменила `printer.base.cfg` и дописала в `printer.cfg` второй блок света на `PA8`.

**Решение:** закомментировать активный `[led chamber_light]` в `printer.cfg`, затем `NEW_RESTART` (не `RESTART`). Повторять после каждой перезагрузки, пока не обновлен Forge-X. Подробности — [11-HISTORY](11-HISTORY.md), грабля 9.

---

### 15. Локально камеры в Fluidd не работают, через сервер — работают
**Причина:** `stream_url` в Moonraker = `/pN/webcam/...`, а busybox `httpd` принтера знает только `/webcam/` → `404`.

**Решение:** строка `P:/pN/webcam/:localhost:8080/` в `httpd.conf` принтера и перезапуск `httpd` (см. [06-PRINTERS](06-PRINTERS.md), «Вебкамеры»).

## 🟢 Полезные диагностические команды

```bash
# Статус контейнеров
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Логи бота (последние 50 строк)
docker logs 3dprinter_bot --tail 50

# Проверка WireGuard-туннеля
ssh kovis@192.168.1.204 'sudo wg show wg0'

# Ping принтеров через atlas
ssh kovis@192.168.1.204 'for i in 101 102 103; do ping -c1 -W1 192.168.10.$i 2>&1 | head -2; done'

# Сканирование подсети принтеров
ssh kovis@192.168.1.204 'nmap -sn 192.168.10.100-103'

# Проверка Moonraker API вручную
ssh kovis@192.168.1.204 'curl -s http://192.168.10.101:7125/printer/objects/query?print_stats | python3 -m json.tool'

# Проверка Caddy
ssh kovis@192.168.1.204 'docker exec caddy caddy validate --config /etc/caddy/Caddyfile'

# DNS-проверка
nslookup printer.example.com
ssh kovis@192.168.1.204 'nslookup printer.example.com'
```
