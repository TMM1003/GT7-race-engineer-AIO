pip install pyinstaller

rmdir /s /q build
rmdir /s /q dist

pyinstaller --noconfirm --onefile --windowed ^
  --name gt7-race-engineer ^
  --paths . ^
  src/app.py