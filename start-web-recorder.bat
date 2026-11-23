@echo off
chcp 65001 >nul
title ATP 本地 Web 录制服务 (带界面弹窗)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch-local-web-recorder.ps1"

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [提示] 录制服务已退出，按任意键关闭窗口...
  pause >nul
)
