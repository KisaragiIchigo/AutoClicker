python -m pip install --upgrade pip
pip install pyinstaller pynput PySide6


pyinstaller autoclicker.py ^
  --name AutoClicker ^
  --onefile ^
  --noconsole ^
  --uac-admin ^
  --add-data "assets;assets"
