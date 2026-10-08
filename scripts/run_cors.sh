#!/bin/bash
for ip in 192.168.10.101 192.168.10.102 192.168.10.103; do
  echo "=== Applying cors-fix to $ip ==="
  sshpass -p "${PRINTER_SSH_PASSWORD:?задай PRINTER_SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$ip 'cat > /tmp/cors-fix.sh && sh /tmp/cors-fix.sh; rc=$?; rm -f /tmp/cors-fix.sh; exit $rc' < "$(dirname "$0")/cors-fix.sh"
done
