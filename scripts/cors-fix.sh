#!/bin/sh
# Добавляет cors_domains для https://printer.example.com в /opt/config/moonraker.conf
# и перезапускает Moonraker. Идемпотентно: повторный запуск ничего не сломает.
set -e

CONF=/opt/config/moonraker.conf
TS=$(date +%F-%H%M%S)

if [ ! -f "$CONF" ]; then
  echo "[ERR] не найден $CONF — проверь путь"
  exit 1
fi

# Идемпотентность: если уже есть — выходим
if grep -A30 '^\[authorization\]' "$CONF" | grep -q 'printer.example.com'; then
  echo "[SKIP] cors_domains уже содержит printer.example.com — ничего не делаю"
  exit 0
fi

cp "$CONF" "$CONF.bak-$TS"
echo "[OK] бэкап: $CONF.bak-$TS"

awk '
BEGIN { a=0; h=0; d=0 }
/^\[authorization\]/ { a=1; print; next }
/^\[/ {
  if (a && !h && !d) { print "cors_domains:"; print "    https://printer.example.com"; d=1 }
  a=0; print; next
}
{
  if (a && /^cors_domains:/) h=1
  print
}
END {
  if (a && !h && !d) { print "cors_domains:"; print "    https://printer.example.com" }
}
' "$CONF" > /tmp/moonraker.conf.new

# Sanity check: новый файл не короче бэкапа
OLD=$(wc -c < "$CONF")
NEW=$(wc -c < /tmp/moonraker.conf.new)
if [ "$NEW" -lt "$OLD" ]; then
  echo "[ERR] новый файл КОРОЧЕ оригинала ($NEW < $OLD) — отмена, бэкап не трогаю"
  rm -f /tmp/moonraker.conf.new
  exit 1
fi

mv /tmp/moonraker.conf.new "$CONF"
echo "[OK] $CONF обновлён (+$((NEW-OLD)) байт)"

curl -X POST http://127.0.0.1:7125/server/restart
echo "[OK] moonraker перезапущен, жду 10с..."
sleep 10

echo "--- [authorization] после правки ---"
awk '/^\[authorization\]/{f=1;print;next} /^\[/{f=0} f' "$CONF"

CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:7125/server/info)
echo "--- Moonraker self-check: HTTP $CODE ---"
if [ "$CODE" = "200" ]; then
  echo "[DONE] всё ок"
else
  echo "[WARN] Moonraker не отвечает 200 — проверь логи: journalctl -u moonraker -n 30"
fi
