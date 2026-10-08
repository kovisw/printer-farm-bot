import os
import sys
import subprocess

# Автоматически устанавливаем paramiko, если его нет
try:
    import paramiko
except ImportError:
    print("[INFO] Устанавливаем библиотеку paramiko для автоматизации SSH...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

PRINTERS = ["192.168.10.101", "192.168.10.102", "192.168.10.103"]
USER = "root"
PASSWORD = os.environ["PRINTER_SSH_PASSWORD"]
SCRIPT_PATH = "cors-fix.sh"
REMOTE_TEMP_PATH = "/tmp/cors-fix.sh"

if not os.path.exists(SCRIPT_PATH):
    print(f"[ERR] Файл {SCRIPT_PATH} не найден! Положите скрипт рядом.")
    sys.exit(1)

print("=== Запуск автоматического применения cors-fix.sh на принтерах ===")

for ip in PRINTERS:
    print(f"\n==================== Подключение к {ip} ====================")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(ip, username=USER, password=PASSWORD, timeout=5)
        print(f"[OK] Успешное SSH подключение к {ip}")
        
        # Передаем файл cors-fix.sh на принтер через SFTP
        sftp = client.open_sftp()
        sftp.put(SCRIPT_PATH, REMOTE_TEMP_PATH)
        sftp.close()
        print(f"[OK] Скрипт скопирован в {REMOTE_TEMP_PATH}")
        
        # Запускаем скрипт
        print("[INFO] Запуск выполнения скрипта на принтере...")
        stdin, stdout, stderr = client.exec_command(f"sh {REMOTE_TEMP_PATH} && rm -f {REMOTE_TEMP_PATH}")
        
        # Читаем вывод
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        
        if out:
            print("--- Вывод скрипта ---")
            print(out.strip())
        if err:
            print("--- Ошибки скрипта ---")
            print(err.strip())
            
        print(f"[SUCCESS] Принтер {ip} успешно обновлен!")
        
    except Exception as e:
        print(f"[FAIL] Ошибка при работе с {ip}: {e}")
    finally:
        client.close()

print("\n============================================================")
print("Все операции завершены.")
