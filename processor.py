import threading, time, random
from dataclasses import dataclass
from typing import Optional, Set, Dict, Any, List
from pynput import mouse, keyboard
from PySide6.QtCore import QObject, Signal

@dataclass(frozen=True)
class HotkeySpec:
    ctrl: bool = True
    alt: bool = True
    shift: bool = False
    key: Optional[str] = None  # 'A', 'F8', None=修飾のみ

    @staticmethod
    def from_string(spec: str) -> Optional["HotkeySpec"]:
        if not spec: return None
        parts = [p.strip() for p in spec.replace("＋","+").split("+") if p.strip()]
        ctrl = any(p.lower()=="ctrl" for p in parts)
        alt  = any(p.lower()=="alt" for p in parts)
        shift= any(p.lower()=="shift" for p in parts)
        main = [p for p in parts if p.lower() not in ("ctrl","alt","shift")]
        key = main[0].upper() if main else None
        if key and not (key.isalnum() or (len(key)>=2 and key[0]=="F" and key[1:].isdigit())):
            return None
        return HotkeySpec(ctrl=ctrl, alt=alt, shift=shift, key=key)

    def matches(self, pressed: Set[object]) -> bool:
        def any_pressed(*cands): return any(k in pressed for k in cands if k is not None)
        # 修飾（左右どちらでもOK）
        if self.ctrl  and not any_pressed(keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, getattr(keyboard.Key, "ctrl", None)):   return False
        if self.alt   and not any_pressed(keyboard.Key.alt_l,  keyboard.Key.alt_r,  getattr(keyboard.Key, "alt",  None)):  return False
        if self.shift and not any_pressed(getattr(keyboard.Key, "shift_l", keyboard.Key.shift),
                                          getattr(keyboard.Key, "shift_r", keyboard.Key.shift),
                                          keyboard.Key.shift):                                                                return False
        if self.key is None: return True
        # 文字
        for k in list(pressed):
            try:
                if isinstance(k, keyboard.KeyCode) and k.char and k.char.upper()==self.key:
                    return True
            except Exception:
                pass
        # Fキー
        if self.key.startswith("F"):
            try:
                n = int(self.key[1:]); fkey = getattr(keyboard.Key, f"f{n}", None)
                if fkey and fkey in pressed: return True
            except Exception:
                pass
        return False

class AutoClickEngine(QObject):
    state_changed = Signal(bool)            # True=開始, False=停止
    point_recorded = Signal(int, int)       # F12記録時 (x, y)

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._running = False

        # 連打ターゲット
        self._button = "left"        # 'left'|'right'|'key'
        self._delay_ms = 100
        self._key_to_repeat: Optional[str] = None
        self._key_sequence: List[str] = []
        self._seq_idx = 0

        # バースト
        self._b1_enabled = False; self._b1_sec = 0; self._b1_ms = 50
        self._b2_enabled = False; self._b2_sec = 0; self._b2_ms = 20
        self._normal_sec = 0  # 0=無限

        # 座標
        self._click_mode = "follow"  # 'follow'|'fixed'|'random_rect'|'recorded'
        self._click_params: Dict[str, Any] = {}
        self._record_points: List[tuple[int,int]] = []
        self._rec_idx = 0

        # 入出力
        self._mouse = mouse.Controller()
        self._keybd = keyboard.Controller()

        # ホットキー
        self._hotkey = HotkeySpec()
        self._pressed: Set[object] = set()
        self._combo_active = False
        self._hotkey_muted = False  # ミュート（GUIのメニュー中など）

        self._worker_thread: Optional[threading.Thread] = None
        self._kb_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._kb_listener.daemon = True
        self._kb_listener.start()

    # ===== 公開API =====
    def set_params(self, *, button: str, delay_ms: int,
                   burst1_enabled: bool, burst1_sec: int, burst1_ms: int,
                   burst2_enabled: bool, burst2_sec: int, burst2_ms: int,
                   normal_sec: int,
                   click_mode: str, click_params: Dict[str, Any],
                   key_to_repeat: Optional[str],
                   key_sequence: List[str],
                   recorded_points: List[tuple[int,int]]):
        with self._lock:
            self._button = button if button in ("left","right","key") else "left"
            self._delay_ms = max(1, int(delay_ms))
            self._b1_enabled = bool(burst1_enabled); self._b1_sec = max(0, int(burst1_sec)); self._b1_ms = max(1, int(burst1_ms))
            self._b2_enabled = bool(burst2_enabled); self._b2_sec = max(0, int(burst2_sec)); self._b2_ms = max(1, int(burst2_ms))
            self._normal_sec = max(0, int(normal_sec))
            self._click_mode = click_mode if click_mode in ("follow","fixed","random_rect","recorded") else "follow"
            self._click_params = dict(click_params or {})
            # 記録点
            self._record_points = [(int(x),int(y)) for (x,y) in (recorded_points or [])]
            if not self._record_points:
                self._rec_idx = 0
            else:
                self._rec_idx %= len(self._record_points)
            # キー列
            norm = []
            for t in key_sequence or []:
                s = str(t).strip().upper()
                if not s: continue
                if s.isalnum() or (s.startswith("F") and s[1:].isdigit()):
                    norm.append(s)
            self._key_sequence = norm
            self._seq_idx = 0
            self._key_to_repeat = (key_to_repeat.upper() if key_to_repeat else None)

    def update_hotkey(self, spec: HotkeySpec):
        with self._lock:
            self._hotkey = spec
            self._combo_active = False

    def set_hotkey_muted(self, muted: bool):
        with self._lock:
            self._hotkey_muted = bool(muted)
            self._combo_active = False
            self._pressed.clear()

    def is_running(self) -> bool:
        with self._lock: return self._running

    def toggle(self): self._toggle()

    def shutdown(self):
        with self._lock: self._running = False
        try:
            if self._kb_listener: self._kb_listener.stop()
        except Exception:
            pass

    # ===== キーボードフック =====
    def _on_press(self, key):
        try:
            # F12記録はミュート中でも受け付ける
            if key == keyboard.Key.f12:
                pos = self._mouse.position
                self.point_recorded.emit(int(pos[0]), int(pos[1]))
                return
            with self._lock:
                if self._hotkey_muted:
                    return
                self._pressed.add(key)
                hk = self._hotkey
            now_active = hk.matches(self._pressed) if hk else False
            if now_active and not self._combo_active:
                self._toggle()
            self._combo_active = now_active
        except Exception:
            pass

    def _on_release(self, key):
        try:
            with self._lock:
                if self._hotkey_muted:
                    return
                self._pressed.discard(key)
                hk = self._hotkey
            self._combo_active = hk.matches(self._pressed) if hk else False
        except Exception:
            self._combo_active = False

    # ===== 実行制御 =====
    def _toggle(self):
        start_thread = False
        with self._lock:
            self._running = not self._running
            running = self._running
            start_thread = running and (self._worker_thread is None or not self._worker_thread.is_alive())
            if running:
                self._seq_idx = 0
                self._rec_idx = 0
                self._t0 = time.perf_counter()
        self.state_changed.emit(running)
        if start_thread:
            self._worker_thread = threading.Thread(target=self._loop, daemon=True)
            self._worker_thread.start()

    def _loop(self):
        while self.is_running():
            try:
                with self._lock:
                    button = self._button; delay_ms = self._delay_ms
                    b1_en, b1_sec, b1_ms = self._b1_enabled, self._b1_sec, self._b1_ms
                    b2_en, b2_sec, b2_ms = self._b2_enabled, self._b2_sec, self._b2_ms
                    mode = self._click_mode; cp = dict(self._click_params)
                    seq = list(self._key_sequence); idx = self._seq_idx
                    key_single = self._key_to_repeat
                    rec_pts = list(self._record_points); rec_idx = self._rec_idx

                now = time.perf_counter()
                elapsed = now - getattr(self, "_t0", now)
                # 遅延選択（段1→段2→通常）
                if b1_en and elapsed < b1_sec:      use_delay = b1_ms
                elif b1_en and b2_en and elapsed < (b1_sec + b2_sec): use_delay = b2_ms
                elif (not b1_en) and b2_en and elapsed < b2_sec:     use_delay = b2_ms
                else:                                               use_delay = delay_ms

                # クリック位置
                if mode == "fixed":
                    x = int(cp.get("x", 0)); y = int(cp.get("y", 0)); self._mouse.position = (x, y)
                elif mode == "random_rect":
                    x1 = int(cp.get("x1", 0)); x2 = int(cp.get("x2", 100))
                    y1 = int(cp.get("y1", 0)); y2 = int(cp.get("y2", 100))
                    if x1 > x2: x1, x2 = x2, x1
                    if y1 > y2: y1, y2 = y2, y1
                    self._mouse.position = (random.randint(x1, x2), random.randint(y1, y2))
                elif mode == "recorded" and rec_pts:
                    x, y = rec_pts[rec_idx]
                    self._mouse.position = (int(x), int(y))
                    with self._lock:
                        self._rec_idx = (rec_idx + 1) % len(rec_pts)

                # 発火
                if button == "key":
                    if seq:
                        self._send_key(seq[idx])
                        with self._lock:
                            self._seq_idx = (self._seq_idx + 1) % len(seq)
                    else:
                        self._send_key(key_single)
                else:
                    btn = mouse.Button.left if button == "left" else mouse.Button.right
                    self._mouse.click(btn)

                time.sleep(max(0.001, use_delay/1000.0))
            except Exception:
                time.sleep(0.1)

    def _send_key(self, spec: Optional[str]):
        if not spec: return
        s = spec.upper()
        try:
            if s.startswith("F") and s[1:].isdigit():
                fk = getattr(keyboard.Key, f"f{int(s[1:])}", None)
                if fk: self._keybd.press(fk); self._keybd.release(fk); return
            if len(s) == 1 and s.isalnum():
                self._keybd.press(s); self._keybd.release(s); return
            self._keybd.press(s); self._keybd.release(s)
        except Exception:
            pass
