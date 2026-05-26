@echo off
chcp 65001 >nul
mode con cols=80 lines=25
echo ======================================
echo      自动清理 + 一键打包
echo ======================================
echo.
echo [1/3] 正在删除旧打包文件...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /f /q *.spec 2>nul
echo ✓ 清理完成
echo.

echo [2/3] 开始打包...
echo 正在调用 PyInstaller，请稍候...
echo.
pyinstaller --onefile --windowed ^
    --name "桥梁模型箱采集上位机" ^
    --hidden-import PyQt5.sip ^
    --hidden-import pyqtgraph ^
    gyro_bridge_full.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo [3/3] ✓ 打包成功！
    echo.
    echo ======================================
    echo  📦 程序位置: dist\桥梁模型箱采集上位机.exe
    echo ======================================
) else (
    echo.
    echo ======================================
    echo  ❌ 打包失败！请检查错误信息
    echo ======================================
)
echo.
pause