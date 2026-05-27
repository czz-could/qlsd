@echo off
chcp 65001 >nul
mode con cols=80 lines=25
echo ======================================
echo      Auto Build Script
echo ======================================
echo.

:: ===== Set New Version Number Here =====
set NEW_VERSION=1.4.0
:: ========================================

echo [1/5] Cleaning old files...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /f /q *.spec 2>nul
echo OK.
echo.

echo [2/5] Building v%NEW_VERSION% ...
echo Please wait...
echo.

:: Auto-answer 'y' to PyInstaller directory prompt
echo y | pyinstaller --onedir --windowed ^
    --name "BridgeMonitor_v%NEW_VERSION%" ^
    --hidden-import PyQt5.sip ^
    --hidden-import pyqtgraph ^
    gyro_bridge_full.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo [3/5] Build successful!
    echo.
    echo [4/5] Copying config file...
    copy /y config.json "dist\BridgeMonitor_v%NEW_VERSION%\config.json" >nul
    if exist "dist\BridgeMonitor_v%NEW_VERSION%\config.json" (
        echo OK.
        echo.
        echo [5/5] Generating release notes...
        
        :: Create release instruction file
        echo ======================================== > dist\release_note.txt
        echo   Release Note >> dist\release_note.txt
        echo ======================================== >> dist\release_note.txt
        echo. >> dist\release_note.txt
        echo Version: v%NEW_VERSION% >> dist\release_note.txt
        echo Output: dist\BridgeMonitor_v%NEW_VERSION%\ >> dist\release_note.txt
        echo. >> dist\release_note.txt
        echo Steps: >> dist\release_note.txt
        echo   1. Compress the folder to .zip >> dist\release_note.txt
        echo   2. Upload to GitHub Release ^(Tag: v%NEW_VERSION%^)>> dist\release_note.txt
        echo   3. Update download_url in version_info.json >> dist\release_note.txt
        echo. >> dist\release_note.txt
        echo   Tip: Change version number at line 9 in this script >> dist\release_note.txt
        
        echo OK: dist\release_note.txt
        echo.
        echo ======================================
        echo   BUILD SUCCESS!
        echo   Output: dist\BridgeMonitor_v%NEW_VERSION%\
        echo   Note: dist\release_note.txt
        echo ======================================
    ) else (
        echo ERROR: Config file copy failed!
        echo    Manual: copy config.json "dist\BridgeMonitor_v%NEW_VERSION%\config.json"
    )
) else (