@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_installer.ps1" %*
