# 05 · VLESS Reality прокси-сайдкар

## Назначение

Контейнер `3dprinter_proxy` на базе `sing-box` решает две проблемы:
1. **Gemini API геоблок** — Google блокирует запросы с российских IP → трафик идёт через VLESS Reality в Италии
2. **Telegram API блокировка** — провайдер atlas (Ростелеком) режет `api.telegram.org` → aiogram получает `ServerDisconnectedError` без прокси

## Конфигурация (sing-box-config.json)

```json
{
  "log": { "level": "info" },
  "inbounds": [
    {
      "type": "mixed",
      "tag": "mixed-in",
      "listen": "0.0.0.0",
      "listen_port": 1080
    }
  ],
  "outbounds": [
    {
      "type": "vless",
      "tag": "vless-out",
      "server": "<VLESS_SERVER>",
      "server_port": 443,
      "uuid": "<UUID>",
      "flow": "xtls-rprx-vision",
      "tls": {
        "enabled": true,
        "server_name": "<SNI>",
        "utls": { "enabled": true, "fingerprint": "chrome" },
        "reality": {
          "enabled": true,
          "public_key": "<REALITY_PUBLIC_KEY>",
          "short_id": "<SHORT_ID>"
        }
      }
    }
  ]
}
```

## Параметры подключения

| Параметр | Значение |
|----------|----------|
| Inbound (слушает) | `0.0.0.0:1080` (mixed HTTP/SOCKS5) |
| Outbound протокол | VLESS Reality (XTLS-RPRX-Vision) |
| Сервер прокси | `<VLESS_SERVER>:443` (Италия) |
| SNI | `<SNI>` |
| Fingerprint | Chrome (uTLS) |
| Docker имя | `3dprinter_proxy` / `proxy` |

## Интеграция с ботом

### Gemini API (gemini.py)
```python
if GEMINI_PROXY:
    os.environ["HTTP_PROXY"] = GEMINI_PROXY      # http://proxy:1080
    os.environ["HTTPS_PROXY"] = GEMINI_PROXY
    os.environ["NO_PROXY"] = "192.168.10.101,192.168.10.102,192.168.10.103,..."
```

### Telegram API (bot.py)
```python
tg_proxy = os.getenv("TG_PROXY") or os.getenv("GEMINI_PROXY")
if tg_proxy:
    session = AiohttpSession(proxy=tg_proxy)
    bot = Bot(token=BOT_TOKEN, session=session)
```

> **Ключевой момент:** aiogram по умолчанию создаёт сессию с `trust_env=False`, поэтому переменные `HTTP_PROXY` не подхватываются автоматически. Прокси передаётся явно через `AiohttpSession(proxy=...)`.

## Маршрутизация трафика

| Трафик | Маршрут |
|--------|---------|
| → `api.telegram.org` | Через VLESS прокси (Италия) |
| → `generativelanguage.googleapis.com` | Через VLESS прокси (Италия) |
| → `192.168.10.101/102/103` | Напрямую через WireGuard (NO_PROXY) |
| → `127.0.0.1`, `localhost` | Напрямую (NO_PROXY) |

## Происхождение конфигурации

Конфигурация VLESS Reality была извлечена из бэкапа настроек `Podkop` на роутере Routerich AX3000. Это тот же прокси-сервер в Италии, который роутер использует для обхода блокировок.
