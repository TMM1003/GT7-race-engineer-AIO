@echo off
setlocal

python -m pip install -r requirements.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm --clean gt7-machine-learning-tool.spec
