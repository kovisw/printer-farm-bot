#!/bin/bash
for ip in 192.168.10.101 192.168.10.102 192.168.10.103; do
  echo "=== Restarting Moonraker on $ip ==="
  sshpass -p "${PRINTER_SSH_PASSWORD:?задай PRINTER_SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$ip '/etc/init.d/moonraker restart'
done
