# 07 · Fluidd, Caddy и Telegram Web App

## Fluidd — единый UI фермы

| Параметр | Значение |
|----------|----------|
| URL | `https://printer.example.com` (только LAN/VPN) |
| Образ | `ghcr.io/fluidd-core/fluidd:latest` (nginx + SPA) |
| Docker | `/srv/services/fluidd/docker-compose.yml` |
| Порт | `127.0.0.1:8082 → Caddy` |
| Контейнер | `fluidd` |

### Первичная настройка (один раз в каждом браузере)
1. Зайти на `https://printer.example.com`
2. В диалоге «Добавить принтер» → URL API: `https://printer.example.com/p1/` (с trailing slash!)
3. Добавить `/p2/` и `/p3/` через Настройки → Принтеры → Добавить
4. Настройки сохраняются в `localStorage` браузера

> **Trailing slash обязателен!** Без него Caddy `route /p1/*` не матчит запрос, и он проваливается в Fluidd SPA.

## Caddy — reverse proxy

### Блок printer.example.com
```caddy
printer.example.com {
  @notAllowed not remote_ip 127.0.0.1/32 192.168.1.0/24 fdXX:XXXX:XXXX::/64 10.10.10.0/24
  respond @notAllowed 403
  encode zstd gzip

  # Камеры (порядок важен — webcam перед общим /pN/*)
  route /p1/webcam/* { uri strip_prefix /p1; reverse_proxy 192.168.10.101:80 }
  route /p2/webcam/* { uri strip_prefix /p2; reverse_proxy 192.168.10.102:80 }
  route /p3/webcam/* { uri strip_prefix /p3; reverse_proxy 192.168.10.103:80 }

  # Moonraker API
  route /p1/* { uri strip_prefix /p1; reverse_proxy 192.168.10.101:7125 }
  route /p2/* { uri strip_prefix /p2; reverse_proxy 192.168.10.102:7125 }
  route /p3/* { uri strip_prefix /p3; reverse_proxy 192.168.10.103:7125 }

  # Fallback — Fluidd SPA
  reverse_proxy 127.0.0.1:8082
}
```

### Почему `route`, а не `handle_path`
Caddy **молча консолидирует** overlapping `handle_path` матчеры. Если `/pN/webcam/*` и `/pN/*` оба заданы как `handle_path`, более специфичный правило **пропадает** из adapted-конфига без предупреждения. `route` сохраняет порядок.

### Доступ по IP-адресам

| Источник | Результат |
|----------|-----------|
| `127.0.0.1` (localhost) | ✅ Разрешён |
| `192.168.1.0/24` (LAN брата) | ✅ Разрешён |
| `fdXX:XXXX:XXXX::/64` (IPv6) | ✅ Разрешён |
| `10.10.10.0/24` (WireGuard VPN) | ✅ Разрешён |
| Всё остальное | ❌ `403 Forbidden` |

> **Подсеть `192.168.10.0/24` (домашняя сеть kovis) НЕ включена в whitelist.** Доступ из домашней сети kovis возможен только через VPN (WireGuard на телефоне).

## Telegram Web App интеграция

В меню управления каждого принтера (файл `control.py`) добавлены две кнопки:

### 🌐 Открыть Fluidd
```python
InlineKeyboardButton(
    text="🌐 Открыть Fluidd",
    web_app=WebAppInfo(url=printer["webapp_url"])  # https://printer.example.com
)
```

### 🎥 Камера принтера
```python
InlineKeyboardButton(
    text="🎥 Камера принтера",
    web_app=WebAppInfo(url=printer["camera_url"])  # https://printer.example.com/pN/webcam/?action=stream
)
```

### Ограничение Web App
Встроенный браузер Telegram (Web App) может обходить VPN-туннель телефона и отправлять запросы через обычный интернет. В результате Caddy видит публичный IP и возвращает `403 Forbidden`.

**Рекомендация:** Для просмотра Fluidd и камер использовать обычный мобильный браузер с включённым WireGuard VPN (1 тап для подключения).

## DNS

### Публичный (reg.ru)
```
printer.example.com  A  <PUBLIC_IP>
```
Нужен для выпуска Let's Encrypt сертификата.

### Внутренний (dnsmasq на роутере hermes, LAN брата)
```
printer.example.com → 192.168.1.204
```
LAN/VPN-клиенты ходят сразу на atlas, не через hairpin.

### На роутере kovis (Routerich)
Настроен:
```bash
uci add_list dhcp.@dnsmasq[0].address='/printer.example.com/192.168.1.204'
uci commit dhcp; /etc/init.d/dnsmasq restart
```
Трафик идет в WG-туннель, роутер маскарадит его в свой адрес `10.10.10.2`, а он в whitelist Caddy — добавлять `192.168.10.0/24` не нужно. Без этой записи имя резолвится в публичный IP, запрос идет через интернет и Caddy отвечает `403`. После правки на ПК — `ipconfig /flushdns`.

## Caddy Runbook

```bash
# Статус
ssh atlas 'docker ps --filter name=fluidd'
# Обновить Fluidd
ssh atlas 'cd /srv/services/fluidd && sudo docker compose pull && sudo docker compose up -d'
# Логи
ssh atlas 'docker logs -f fluidd'
# Перечитать Caddyfile
ssh atlas 'docker exec caddy caddy reload --config /etc/caddy/Caddyfile'
```
