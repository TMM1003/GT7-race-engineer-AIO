pip install pyinstaller

rmdir /s /q build
rmdir /s /q dist

pyinstaller --noconfirm --onefile --windowed ^
  --name gt7-telemetry-ML ^
  --paths . ^
  src/app.py