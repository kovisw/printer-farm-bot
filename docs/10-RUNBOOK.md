# 10 · Операционный Runbook

## Ежедневные проверки

### Быстрая проверка (1 минута)
```bash
# Все ли контейнеры живы?
ssh kovis@192.168.1.204 'docker ps --filter name=3dprinter --format "{{.Names}}: {{.Status}}"'

# Последние ошибки в логах бота
ssh kovis@192.168.1.204 'docker logs 3dprinter_bot --tail 10 2>&1 | grep -i error'
```

### Полная проверка (3 минуты)
```bash
# WireGuard-туннель
ssh kovis@192.168.1.204 'sudo wg show wg0 | grep -E "endpoint|latest|transfer"'

# Ping принтеров
ssh kovis@192.168.1.204 'for i in 101 102 103; do echo -n "192.168.10.$i: "; ping -c1 -W1 192.168.10.$i >/dev/null 2>&1 && echo OK || echo FAIL; done'

# Caddy
ssh kovis@192.168.1.204 'docker ps --filter name=caddy --format "{{.Status}}"'
```

## Процедуры обновления

### Обновление кода бота

**1. Подготовка (локально на Windows):**
```powershell
# Из папки проекта:
scp -r bot.py src kovis@192.168.1.204:/home/kovis/printernaya/Bot/
```

**2. Пересборка (на atlas):**
```bash
ssh kovis@192.168.1.204
cd /home/kovis/printernaya/Bot
docker compose down
docker compose build --no-cache
docker compose up -d
docker logs -f 3dprinter_bot  # Ctrl+C после "Фоновый мониторинг принтеров запущен"
```

**3. Верификация:**
```bash
docker compose ps  # Оба сервиса Up
docker logs 3dprinter_bot --tail 5  # Нет ошибок
# Отправить /start в Telegram → меню должно появиться
```

### Обновление .env (секреты)
```bash
scp .env kovis@192.168.1.204:/home/kovis/printernaya/Bot/.env
ssh kovis@192.168.1.204 'cd /home/kovis/printernaya/Bot && docker compose restart bot'
```

### Обновление прокси-конфига
```bash
scp sing-box-config.json kovis@192.168.1.204:/home/kovis/printernaya/Bot/sing-box-config.json
ssh kovis@192.168.1.204 'cd /home/kovis/printernaya/Bot && docker compose restart proxy'
```

### Обновление Fluidd
```bash
ssh kovis@192.168.1.204 'cd /srv/services/fluidd && sudo docker compose pull && sudo docker compose up -d'
```

### Обновление Caddyfile
```bash
# ВАЖНО: не использовать mv! Bind-mount = inode trap.
# Метод: редактируем через cat
ssh kovis@192.168.1.204 'cat > /srv/services/files/caddy/Caddyfile << "EOF"
... новое содержимое ...
EOF'
ssh kovis@192.168.1.204 'docker exec caddy caddy reload --config /etc/caddy/Caddyfile'
```

## Процедуры восстановления

### Перезапуск бота (мягкий)
```bash
ssh kovis@192.168.1.204 'cd /home/kovis/printernaya/Bot && docker compose restart bot'
```

### Полный перезапуск стека
```bash
ssh kovis@192.168.1.204 'cd /home/kovis/printernaya/Bot && docker compose down && docker compose up -d'
```

### Восстановление WireGuard-туннеля
```bash
ssh kovis@192.168.1.204 'sudo systemctl restart wg-quick@wg0'
```
На стороне роутера: перезагрузить AmneziaWG-интерфейс через LuCI.

### Принтер не отвечает
1. Проверить `ping 192.168.10.10N` через atlas
2. Если unreachable → перезагрузить принтер по питанию
3. Ждать ~60 секунд
4. Проверить `nmap -sn 192.168.10.10N`

## Git-процедуры (репозиторий Spec/Сервер)

### Коммит изменений
```bash
cd Spec/Сервер
git add -A
git commit -m "docs(section): describe what changed"
git push origin master
```

### Формат коммитов
```
docs(3dprinter): add camera stream buttons to web app spec
fix(caddy): correct webcam route ordering in printer block
chore(deploy): update deployment runbook
```

### Откат ошибочного коммита
```bash
git revert HEAD
git push origin master
```

## Мониторинг без бота

Если бот недоступен, можно проверить принтеры напрямую:

```bash
# Moonraker API
ssh kovis@192.168.1.204 'curl -s http://192.168.10.101:7125/printer/objects/query?print_stats | python3 -m json.tool'

# Через Fluidd в браузере (нужен VPN)
# https://printer.example.com

# SSH к принтеру
ssh kovis@192.168.1.204 'sshpass -p "$PRINTER_SSH_PASSWORD" ssh -o StrictHostKeyChecking=no root@192.168.10.101'
```

## Контакты и ответственность

| Область | Ответственный | Контакт |
|---------|--------------|---------|
| Принтеры, роутер, физическая сеть | kovis (я) | Telegram (USER_ID: <YOUR_TELEGRAM_ID>) |
| Сервер atlas, Docker, Caddy, WG | брат | — |
| Код бота, спецификации | kovis | — |
| DNS (reg.ru), публичный IP | брат | — |
