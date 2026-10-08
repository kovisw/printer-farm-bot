@echo off
REM ============================================================================
REM Добавляет cors_domains: https://printer.example.com в moonraker.conf на трёх
REM принтерах и перезапускает Moonraker. Если у тебя другой SSH-пользователь
REM (не root) или другие IP — поправь переменные ниже.
REM Требуется: cors-fix.sh РЯДОМ с этим .bat и встроенный ssh из Windows 10+.
REM ============================================================================

setlocal EnableDelayedExpansion
chcp 65001 >nul

set "USER=root"
set "PRINTERS=192.168.10.101 192.168.10.102 192.168.10.103"

if not exist "%~dp0cors-fix.sh" (
    echo [ERR] не найден "%~dp0cors-fix.sh" - положи его рядом с этим .bat
    pause
    exit /b 1
)

set "FAIL=0"
for %%I in (%PRINTERS%) do (
    echo.
    echo ============================== %%I ==============================
    type "%~dp0cors-fix.sh" | ssh -o StrictHostKeyChecking=accept-new %USER%@%%I "cat > /tmp/cors-fix.sh && sh /tmp/cors-fix.sh; rc=$?; rm -f /tmp/cors-fix.sh; exit $rc"
    if errorlevel 1 (
        echo [FAIL] %%I - смотри сообщение выше
        set /a FAIL+=1
    ) else (
        echo [OK] %%I готов
    )
)

echo.
echo ==================================================================
if "%FAIL%"=="0" (
    echo Все принтеры обновлены. Открой https://printer.example.com - Fluidd должен подцепить /p1 /p2 /p3.
) else (
    echo Сбоев: %FAIL%. Проверь вывод выше. Бэкапы оригиналов лежат на каждом принтере: /opt/config/moonraker.conf.bak-...
)
echo ==================================================================
pause
endlocal
