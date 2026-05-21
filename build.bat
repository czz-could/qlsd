@echo off
chcp 65001 >nul
mode con cols=80 lines=20
echo ======================================
echo      自动清理 + 一键打包
echo ======================================
echo 正在删除旧打包文件...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /f /q *.spec 2>nul

echo 开始打包...
pyinstaller --onefile --windowed --name "桥梁模型箱采集上位机" gyro_bridge_full.py

echo.
echo 打包完成！
echo 程序在 dist 文件夹里面
pause