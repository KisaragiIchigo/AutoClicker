import os, sys
from typing import Optional
from PySide6.QtGui import QGuiApplication

APP_NAME = "AutoClicker"


BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))


CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOGS_DIR   = os.path.join(BASE_DIR, "logs")

def ensure_app_dirs() -> None:
    for d in (CONFIG_DIR, LOGS_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass

def resource_path(rel_path: str) -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = BASE_DIR
    return os.path.join(base, rel_path)

def brand_font_family() -> str:

    fam = "メイリオ"
    try:
        return fam
    except Exception:
        return "Sans Serif"

def is_admin() -> bool:
    try:
        if os.name != "nt":
            return True  
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def screen_size() -> Optional[tuple[int, int]]:
    try:
        scr = QGuiApplication.primaryScreen().geometry()
        return (scr.width(), scr.height())
    except Exception:
        return None
