# 02 · Сетевая конфигурация

## Узлы сети

| Узел | IP-адрес | Роль |
|------|----------|------|
| Сервер `atlas` | `192.168.1.204` (LAN), `10.10.10.1` (WG) | Docker-хост, Caddy, бот, Fluidd |
| Роутер `Routerich AX3000` | `192.168.10.1` (LAN), `10.10.10.2` (WG) | OpenWrt-шлюз домашней сети принтеров |
| Принтер 1 | `192.168.10.101` | Flashforge 5M, Moonraker :7125, камера :80 |
| Принтер 2 | `192.168.10.102` | Flashforge 5M, Moonraker :7125, камера :80 (нестабильна) |
| Принтер 3 | `192.168.10.103` | Flashforge 5M, Moonraker :7125, камеры нет |

## WireGuard туннель (atlas ↔ Routerich)

### Сторона atlas (сервер, `/etc/wireguard/wg0.conf`)
```ini
[Interface]
Address = 10.10.10.1/32
ListenPort = 51820
PrivateKey = <hidden>

[Peer]
# kovis (роутер принтерной)
PublicKey = <hidden>
AllowedIPs = 10.10.10.2/32, 192.168.10.0/24
```

### Сторона Routerich (клиент, AmneziaWG)
```
Протокол: AmneziaWG (совместимость с WG: jc=0, jmin=0, jmax=0, s1=0, s2=0, h1=1, h2=2, h3=3, h4=4)
Tunnel IP: 10.10.10.2/32
Peer PublicKey: <hidden>
Endpoint: <PUBLIC_IP>:51820
AllowedIPs: 10.10.10.0/24, 192.168.1.204/32
PersistentKeepalive: 25
```

### Firewall на Routerich
- Зона `vpn` (интерфейс `wg0`): Input=ACCEPT, Output=ACCEPT, Forward=REJECT
- Masquerade=1, MSS Clamping=1
- Forwarding: `lan → vpn`, `vpn → lan` (двунаправленный транзит)

## DHCP Static Leases (Routerich)

Принтеры привязаны к фиксированным IP по MAC-адресам через `uci`:

| Принтер | MAC-адрес | Фиксированный IP |
|---------|-----------|-------------------|
| Принтер 1 | `XX:XX:XX:XX:XX:XX` | `192.168.10.101` |
| Принтер 2 | `XX:XX:XX:XX:XX:XX` | `192.168.10.102` |
| Принтер 3 | `XX:XX:XX:XX:XX:XX` | `192.168.10.103` |

```bash
# Команды для привязки (уже выполнены):
uci add dhcp host
uci set dhcp.@host[-1].name='Printer1'
uci set dhcp.@host[-1].mac='XX:XX:XX:XX:XX:XX'
uci set dhcp.@host[-1].ip='192.168.10.101'
# ... аналогично для остальных
uci commit dhcp
/etc/init.d/dnsmasq restart
```

> **Известная проблема:** Принтеры периодически теряют сетевое подключение (оранжевая лампочка на Ethernet-разъёме). Лечится перезагрузкой принтера по питанию (выключить тумблер → 5 сек → включить).

## DNS-переопределения на Routerich (dnsmasq)

```bash
uci add_list dhcp.@dnsmasq[0].address='/cloud.example.com/192.168.1.204'
# printer.example.com НЕ переопределён — доступ только через VPN
uci commit dhcp
/etc/init.d/dnsmasq restart
```

## Caddy (reverse proxy на atlas)

### printer.example.com
```caddy
printer.example.com {
  @notAllowed not remote_ip 127.0.0.1/32 192.168.1.0/24 fdXX:XXXX:XXXX::/64 10.10.10.0/24
  respond @notAllowed 403
  encode zstd gzip

  # Камеры (через nginx принтера на :80)
  route /p1/webcam/* { uri strip_prefix /p1; reverse_proxy 192.168.10.101:80 }
  route /p2/webcam/* { uri strip_prefix /p2; reverse_proxy 192.168.10.102:80 }
  route /p3/webcam/* { uri strip_prefix /p3; reverse_proxy 192.168.10.103:80 }

  # Moonraker API
  route /p1/* { uri strip_prefix /p1; reverse_proxy 192.168.10.101:7125 }
  route /p2/* { uri strip_prefix /p2; reverse_proxy 192.168.10.102:7125 }
  route /p3/* { uri strip_prefix /p3; reverse_proxy 192.168.10.103:7125 }

  # Fluidd SPA (fallback)
  reverse_proxy 127.0.0.1:8082
}
```

> **Важно:** Использован `route`, а не `handle_path` — Caddy молча консолидирует overlapping `handle_path` матчеры, и более-специфичные правила (webcam) пропадают.

### URL-схема

| URL | Назначение |
|-----|------------|
| `https://printer.example.com` | Fluidd SPA (UI) |
| `https://printer.example.com/p1/` | Moonraker API принтера 1 |
| `https://printer.example.com/p1/webcam/?action=stream` | MJPEG-стрим камеры принтера 1 |
| `https://printer.example.com/p2/`, `/p3/` | Аналогично для принтеров 2 и 3 |

### Доступ
- Из LAN брата (`192.168.1.0/24`) — работает напрямую
- Из VPN (`10.10.10.0/24`) — работает через туннель
- Из домашней сети kovis (`192.168.10.0/24`) — требуется VPN на устройстве + DNS override на роутере
- Из публичного интернета — `403 Forbidden`

## Podkop / sing-box (policy routing на Routerich)

### Outbound "MAIN" (VLESS Reality)
- Назначение: Google AI, Gemini, GFWList
- Сервер: `<VLESS_SERVER>:443`
- SNI: `<SNI>`
- Transport: UDP over TCP

### Outbound "YOUTUBE_DISCORD" (AmneziaWG/WARP)
- Назначение: YouTube, Discord, Telegram
- Протокол: AmneziaWG через WARP endpoint

### Исключения маршрутизации
```bash
uci add_list podkop.settings.routing_excluded_ips='192.168.1.204'
```
IP сервера atlas исключён из proxy routing, чтобы WireGuard-туннель работал напрямую.

## Открытые порты на atlas (наружу)

| Порт | Протокол | Сервис |
|------|----------|--------|
| 22 | TCP | SSH |
| 80 | TCP | Caddy (HTTP → HTTPS redirect) |
| 443 | TCP | Caddy (HTTPS) |
| 51820 | UDP | WireGuard |
