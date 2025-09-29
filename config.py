import json, os, time
from typing import Dict, Any, List
from utils import CONFIG_DIR, ensure_app_dirs

CFG_FILE = os.path.join(CONFIG_DIR, "[config]AutoClickerQt_setting.json")

_DEFAULTS = {
    "hotkey": "Ctrl+Alt",
    "start_minimized": False,
    "profiles": {},
    "last_profile": None,
    "profiles_history": [] 
}

_PROFILE_DEFAULT = {
    "button": "left",
    "delay_ms": 100,
    "burst1_enabled": False, "burst1_sec": 0, "burst1_ms": 50,
    "burst2_enabled": False, "burst2_sec": 0, "burst2_ms": 20,
    "normal_sec": 0,
    "click_mode": "follow",
    "click_params": {},
    "key_to_repeat": None,
    "key_sequence": [],
    "recorded_points": [] 
}

def _migrate_profile(p: Dict[str, Any]) -> Dict[str, Any]:
    out = _PROFILE_DEFAULT.copy()
    if not isinstance(p, dict): return out
    out.update({
        "button": p.get("button", out["button"]),
        "delay_ms": int(p.get("delay_ms", out["delay_ms"])),
        "click_mode": p.get("click_mode", out["click_mode"]),
        "click_params": p.get("click_params", out["click_params"]) or {},
        "key_to_repeat": p.get("key_to_repeat", out["key_to_repeat"]),
        "normal_sec": int(p.get("normal_sec", out["normal_sec"])),
        "recorded_points": p.get("recorded_points", out["recorded_points"]) or []
    })
    b1_sec = int(p.get("burst1_sec", 0)); b1_ms = int(p.get("burst1_ms", out["burst1_ms"]))
    b2_sec = int(p.get("burst2_sec", 0)); b2_ms = int(p.get("burst2_ms", out["burst2_ms"]))
    out["burst1_sec"] = b1_sec; out["burst1_ms"] = b1_ms
    out["burst2_sec"] = b2_sec; out["burst2_ms"] = b2_ms
    out["burst1_enabled"] = bool(p.get("burst1_enabled", b1_sec > 0))
    out["burst2_enabled"] = bool(p.get("burst2_enabled", b2_sec > 0))
    ks = p.get("key_sequence", [])
    if not isinstance(ks, list): ks = []
    out["key_sequence"] = [str(x).strip().upper() for x in ks if str(x).strip()]
    return out

def _migrate_all(data: Dict[str, Any]) -> Dict[str, Any]:
    out = _DEFAULTS.copy()
    out.update({k: data.get(k, v) for k, v in _DEFAULTS.items()})
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict): profiles = {}
    migrated = {name: _migrate_profile(p) for name, p in profiles.items()}
    out["profiles"] = migrated
    lp = data.get("last_profile")
    out["last_profile"] = lp if isinstance(lp, str) and lp in migrated else None
    # 履歴
    hist = data.get("profiles_history", [])
    if isinstance(hist, list):
        # 形式を軽く正規化
        clean = []
        for item in hist[-10:]:
            try:
                clean.append({
                    "name": str(item.get("name")),
                    "at":  int(item.get("at", int(time.time()))),
                    "data": _migrate_profile(item.get("data", {}))
                })
            except Exception:
                pass
        out["profiles_history"] = clean[-10:]
    else:
        out["profiles_history"] = []
    return out

class AppConfig:
    @staticmethod
    def load() -> dict:
        ensure_app_dirs()
        if os.path.exists(CFG_FILE):
            try:
                with open(CFG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                cfg = _migrate_all(data)
                AppConfig.save(cfg)
                return cfg
            except Exception:
                pass
        cfg = _DEFAULTS.copy()
        AppConfig.save(cfg)
        return cfg

    @staticmethod
    def save(data: dict) -> None:
        ensure_app_dirs()
        d = _DEFAULTS.copy()
        if isinstance(data, dict):
            d["hotkey"] = data.get("hotkey", d["hotkey"])
            d["start_minimized"] = bool(data.get("start_minimized", d["start_minimized"]))
            # profiles
            profs = data.get("profiles", {})
            if isinstance(profs, dict):
                clean = {name: _migrate_profile(p) for name, p in profs.items()}
                d["profiles"] = clean
                # last_profile
                lp = data.get("last_profile")
                d["last_profile"] = lp if isinstance(lp, str) and lp in clean else None
            # history
            hist = data.get("profiles_history", [])
            if isinstance(hist, list):
                d["profiles_history"] = hist[-10:]
        try:
            with open(CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def push_history(cfg: dict, name: str, snapshot: Dict[str, Any]) -> dict:
        """履歴へ追加（最大10件）"""
        item = {"name": name, "at": int(time.time()), "data": _migrate_profile(snapshot)}
        hist: List[Dict[str, Any]] = cfg.get("profiles_history", [])
        if not isinstance(hist, list): hist = []
        hist.append(item)
        cfg["profiles_history"] = hist[-10:]
        return cfg
