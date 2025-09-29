import sys
from PySide6.QtWidgets import QApplication
from utils import ensure_app_dirs
from config import AppConfig
from gui import MainWindow

def main():
    app = QApplication(sys.argv)
    ensure_app_dirs()  
    cfg = AppConfig.load()
    w = MainWindow(start_minimized=bool(cfg.get("start_minimized", False)))
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
