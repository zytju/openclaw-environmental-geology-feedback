@echo off
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>&1
if errorlevel 1 (
  echo 请先按指南安装 OpenClaw，再关闭并重新打开终端。
  pause
  exit /b 1
)
node course.mjs start
pause
