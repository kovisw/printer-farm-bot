# 06 · Спецификации 3D-принтеров

## Общие ТТХ (все 3 принтера одинаковые)

| Параметр | Значение |
|----------|----------|
| Модель | Flashforge Adventurer 5M |
| Прошивка | Модифицированный Klipper / Forge-X (от DrA1ex) |
| Кинематика | CoreXY |
| Макс. скорость печати | 600 мм/с |
| Макс. ускорение | 20 000 мм/с² |
| Область печати | 220 × 220 × 220 мм |
| Экструдер | Direct Drive, быстросъёмное сопло, до 280°C |
| Стол | Подогреваемый до 110°C, магнитная PEI-пластина |
| Калибровка | Автокалибровка стола + Input Shaping (компенсация резонансов) |
| Датчики | Датчик окончания филамента |
| Подключение | Ethernet + Wi-Fi |
| ОС | BusyBox  |
| SSH-доступ | `root`) |

## Сетевые параметры

| Принтер | IP-адрес | MAC-адрес | Moonraker | Webcam | 
|---------|----------|-----------|-----------|--------|
| Принтер 1 | `192.168.10.101` | `XX:XX:XX:XX:XX:XX` | `:7125` | `:80/webcam/` |  
| Принтер 2 | `192.168.10.102` | `XX:XX:XX:XX:XX:XX` | `:7125` | `:80/webcam/` |  
| Принтер 3 | `192.168.10.103` | `XX:XX:XX:XX:XX:XX` | `:7125` | `:80/webcam/` |

## Moonraker API (основные endpoints)

Базовый URL: `http://192.168.10.10N:7125`

### Чтение состояния
```
GET /printer/objects/query?print_stats&extruder&heater_bed&display_status
```
Ответ содержит:
```json
{
  "result": {
    "status": {
      "print_stats": {
        "state": "printing|paused|standby|complete|error|cancelled",
        "filename": "model.gcode",
        "print_duration": 3600.0,
        "message": "Klipper error description"
      },
      "extruder": { "temperature": 210.5, "target": 215.0 },
      "heater_bed": { "temperature": 60.2, "target": 60.0 },
      "display_status": { "progress": 0.75 }
    }
  }
}
```

### Управление печатью
```
POST /printer/print/pause
POST /printer/print/resume
POST /printer/print/cancel
POST /printer/print/start?filename=<encoded_name>
```

### Загрузка файлов
```
POST /server/files/upload
Content-Type: multipart/form-data
Field: file=@model.gcode
```
Успешный ответ: HTTP 201.

### Перезапуск Moonraker
```
POST /server/restart
```
> На принтерах Forge-X нет `systemctl`. Перезапуск Moonraker — только через API или через `/etc/init.d/S99root` скрипт.

### Конфигурационные файлы принтера
```
GET  /server/files/config/mod_data/user.moonraker.conf
POST /server/files/upload  (root=config, filename=mod_data/user.moonraker.conf)
```
Файл `user.moonraker.conf` — **не reserved**, обновляется через API без SSH. Содержит `cors_domains: *` и `trusted_clients: 0.0.0.0/0` по умолчанию (Forge-X).

## Вебкамеры (MJPEG через busybox httpd принтера)

На принтере `mjpg_streamer` слушает `localhost:8080`, наружу его отдает busybox `httpd` на `:80` (nginx там нет). `httpd` работает в chroot `/data/.mod/.forge-x`, конфиг — `/data/.mod/.forge-x/etc/httpd.conf`:

```
P:/webcam/:localhost:8080/
P:/p1/webcam/:localhost:8080/     # на втором принтере — /p2/webcam/
```

Вторая строка нужна, чтобы камера работала и в Fluidd на сервере, и в локальном Fluidd принтера (см. [11-HISTORY](11-HISTORY.md), грабля 10). Файл принадлежит Forge-X — после обновления мода проверить, что строка на месте.

`httpd` не перечитывает конфиг по HUP, нужен перезапуск (в SSH-сессии `chroot` не в PATH):
```sh
kill $(cat /data/.mod/.forge-x/run/httpd.pid); sleep 1
/usr/sbin/chroot /data/.mod/.forge-x /opt/config/mod/.root/S70httpd start
```

> `mjpg_streamer` не любит частые переподключения: несколько запросов подряд дают пустой ответ даже на `/webcam/`. Проверять с паузой в пару секунд.

### Через Caddy (HTTPS):
```
https://printer.example.com/p1/webcam/?action=stream   # Принтер 1
https://printer.example.com/p2/webcam/?action=stream   # Принтер 2
https://printer.example.com/p3/webcam/?action=stream   # Принтер 3 (HTTP 500 — нет камеры)
```

### Настройка stream_url в Moonraker
В `user.moonraker.conf` секция `[webcam cam]` → `stream_url` должен быть `/pN/webcam/?action=stream` (а не `/webcam/...`), иначе Fluidd промахивается при резолве URL.

> **Snapshot endpoint** (`?action=snapshot`) у этого `mjpg_streamer` не работает — превью камеры в Fluidd недоступно, только live-стрим.

## Известные проблемы принтеров

1. **Сброс IP-адреса:** Принтеры периодически теряют назначенный IP и получают новый от DHCP. Решено привязкой MAC→IP через `uci` на роутере (Static Leases).

2. **Потеря сетевого подключения:** Оранжевая лампочка на Ethernet-порте принтера + зелёная на роутере = физический линк есть, но ОС не инициализирует сетевой интерфейс. **Решение:** Перезагрузка принтера по питанию (тумблер на задней панели).


3. **Отсутствие snapshot:** `?action=snapshot` не поддерживается прошивкой камеры — только live-стрим `?action=stream`.

4. **Самообновление заводской прошивки:** версия `5.1.9` ломает связку с Forge-X 1.4.1 (E0120, дубль пина `PA8`, подробности — [11-HISTORY](11-HISTORY.md), грабля 9). Серверы обновлений закрыты на роутере. Klipper после правки конфига перезапускать только `NEW_RESTART`, не `RESTART` — иначе зависает заводской экран.
