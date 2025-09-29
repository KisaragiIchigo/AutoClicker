import os
from PySide6.QtCore import Qt, QEvent, QTimer, QEasingCurve, QPropertyAnimation, QRect, Signal
from PySide6.QtGui import QIcon, QColor, QKeySequence, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication, QStyle,
    QGraphicsDropShadowEffect, QDialog, QTextBrowser, QSpinBox,
    QRadioButton, QGroupBox, QButtonGroup, QComboBox, QLineEdit,
    QMessageBox, QSystemTrayIcon, QMenu, QCheckBox
)
from utils import resource_path, brand_font_family, is_admin
from processor import AutoClickEngine, HotkeySpec
from config import AppConfig

# テーマ色
COLORS_STOP = {"PRIMARY":"#4169e1","HOVER":"#7000e0","GLASS":"rgba(5,5,51,200)","PANEL":"#4f8fda","BORDER":"3px solid rgba(65,105,225,255)","STATUS_BG":"#004080"}
COLORS_RUN  = {"PRIMARY":"#1db954","HOVER":"#139a44","GLASS":"rgba(5,51,20,200)","PANEL":"#2f9f6a","BORDER":"3px solid rgba(29,185,84,255)","STATUS_BG":"#0f6a3a"}
WINDOW_BG = "rgba(255,255,255,0)"
TITLE_COLOR, TEXT_COLOR = "#FFFFFF", "#FFFFFF"
CLOSEBTN_COLOR, MINBTN_COLOR, MAXBTN_COLOR = "#FF0000", "#FFD600", "#00C853"
RADIUS_WINDOW, RADIUS_CARD, RADIUS_PANEL, RADIUS_BUTTON, RADIUS_CLOSE = 18,16,10,8,6
RESIZE_MARGIN, GAP, PAD, MENU_WIDTH = 8,12,16,600

def build_qss(compact: bool, theme: dict) -> str:
    grad = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(255,255,255,50), stop:0.5 rgba(200,220,255,25), stop:1 rgba(255,255,255,8))")
    fam = brand_font_family()
    return f"""
    QWidget#bgRoot {{ background-color:{WINDOW_BG}; border-radius:{RADIUS_WINDOW}px; }}
    QWidget#glassRoot {{ background-color:{theme['GLASS']}; border:{theme['BORDER']}; border-radius:{RADIUS_CARD}px; background-image:{'none' if compact else grad}; }}
    QLabel#titleLabel {{ color:#fff; font-weight:bold; font-size:14pt; }}
    QLabel, QRadioButton {{ color:{TEXT_COLOR}; font-family:"{fam}"; font-size:11pt; }}
    QWidget.DarkPanel {{ background-color:{theme['PANEL']}; border:1px solid rgba(0,0,0,140); border-radius:{RADIUS_PANEL}px; padding:14px; }}
    QSpinBox, QLineEdit, QComboBox {{ background:#fffafa; color:#000; border:1px solid #777; border-radius:5px; padding:4px 8px; font-family:"{fam}"; font-size:11pt; min-width:86px; }}
    QGroupBox {{ color:{TEXT_COLOR}; font-size:11.2pt; font-weight:600; margin-top:6px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 6px; padding: 2px 4px; color:{TEXT_COLOR}; }}
    QPushButton {{ background-color:{theme['PRIMARY']}; color:#fff; border:none; border-radius:{RADIUS_BUTTON}px; padding:8px 14px; font-family:"{fam}"; font-size:11pt; }}
    QPushButton:hover {{ background-color:{theme['HOVER']}; }}
    QPushButton#minBtn, QPushButton#maxBtn, QPushButton#closeBtn {{ background:transparent; padding:0; border-radius:{RADIUS_CLOSE}px; }}
    QPushButton#minBtn {{ color:{MINBTN_COLOR}; }} QPushButton#maxBtn {{ color:{MAXBTN_COLOR}; }} QPushButton#closeBtn {{ color:{CLOSEBTN_COLOR}; }}
    QPushButton#minBtn:hover, QPushButton#maxBtn:hover, QPushButton#closeBtn:hover {{ background:rgba(153,179,255,0.10); }}
    QTextBrowser#readmeText {{ color:#fffafa; background:#333; border-radius:{RADIUS_PANEL}px; padding:12px; font-family:"{fam}"; font-size:11.3pt; }}
    QLabel#banner {{ background:#8B0000; color:#fff; padding:8px 12px; border-radius:8px; font-size:10.8pt; }}
    QWidget#menuPanel {{ background:{theme['GLASS']}; border:{theme['BORDER']}; border-top-right-radius:{RADIUS_CARD}px; border-bottom-right-radius:{RADIUS_CARD}px; background-image:{'none' if compact else grad}; }}
    QWidget#overlay {{ background:rgba(0,0,0,120); }}
    QLabel.menuCaption {{ color:#b8dcff; font-size:12pt; font-weight:700; }}
    """

def apply_drop_shadow(w: QWidget) -> QGraphicsDropShadowEffect:
    eff = QGraphicsDropShadowEffect(w); eff.setBlurRadius(28); eff.setOffset(0,3)
    c = QColor(0,0,0); c.setAlphaF(0.18); eff.setColor(c); w.setGraphicsEffect(eff); return eff

README_MD = r"""
# AutoClicker ©️2025 KisaragiIchigo

## できること
- 連打: **左クリック / 右クリック / 指定キー / キー列** の連打
- バースト: **段1 / 段2** をチェックで有効化（例: 50ms→20ms→通常100ms）
- クリック座標モード:
  - **現在位置**（マウス追従）
  - **固定座標**（X,Y指定）
  - **ランダム矩形**（Xmin/Xmax, Ymin/Ymax 内でランダム）
  - **記録操作**（**F12**で現在のカーソル座標を記録。記録順にループ再生）
- ハンバーガーメニューを**開いている間はホットキー無効化**（誤作動防止）
- プロファイル:
  - 値変更のたび**自動保存**（現在選択名に上書き）
  - **履歴10件**を保持（スナップショット）
  - 最後に選んだ**プロファイルを次回起動時に復元**
- 起動時最小化＆**トレイ常駐**
- 権限チェック（管理者権限じゃない時に注意喚起）

## 基本操作
1. 上段の「プロファイル」で名前を選択/入力  
   - **保存/上書**でプロファイル保存  
   - **適用**でそのプロファイルの値を反映  
2. 「連打ボタン」で **左/右/指定キー** を選ぶ  
   - 指定キーはメニュー内「指定キー（単発）」で設定  
   - **キー列**（例 `A,D,F8`）を入れると順番に送出  
3. 「クリック座標」でモードを選択  
   - **記録操作**を使うときは、狙いたい場所にマウスを置いて **F12** を押す → 座標が記録される（件数はメニューに表示）  
   - 「記録クリア」で記録点を全消去  
4. 「ディレイ/バースト」で持続と間隔を設定  
   - 段1/段2はチェックを入れると有効化  
5. **ホットキー**（デフォルト `Ctrl+Alt`）で開始/停止をトグル  
   - メニュー内のホットキー欄をクリックして、好みの組み合わせを押すと更新される  
   - メニューを開いている間は**常にミュート**されるから設定が安全

## ちょいテク
- **F12はミュート中でも座標記録**だけは受け付ける  
- **キー列**は英数とFnキー（F1〜F24）に対応  
- 記録操作モードは**記録順にループ**してクリック  
- 設定・ログは実行フォルダ直下の `config/` と `logs/` に保存（exeでもOK）

## トラブル対処
- 連打が止まらない/誤爆する → メニューを開く（ホットキー無効）  
- 権限不足っぽい → 管理者で再起動

"""


class ReadmeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("README ©️2025 KisaragiIchigo")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(850, 600); self.setMinimumSize(850, 600)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        bg = QWidget(); bg.setObjectName("bgRoot"); outer.addWidget(bg)
        bgL = QVBoxLayout(bg); bgL.setContentsMargins(GAP,GAP,GAP,GAP)
        card = QWidget(); card.setObjectName("glassRoot"); bgL.addWidget(card)
        cardL = QVBoxLayout(card); cardL.setContentsMargins(PAD,PAD,PAD,PAD); cardL.setSpacing(GAP)
        bar = QHBoxLayout(); title = QLabel("README"); title.setObjectName("titleLabel"); bar.addWidget(title); bar.addStretch(1)
        btn_close = QPushButton("x"); btn_close.setObjectName("closeBtn"); btn_close.setFixedSize(28,28); btn_close.clicked.connect(self.accept)
        bar.addWidget(btn_close); cardL.addLayout(bar)
        viewer = QTextBrowser(); viewer.setObjectName("readmeText"); viewer.setMarkdown(README_MD); viewer.setOpenExternalLinks(True)
        cardL.addWidget(viewer, 1)
        self._shadow = apply_drop_shadow(card)

class MainWindow(QWidget):
    engine_state_changed = Signal(bool)
    def __init__(self, start_minimized: bool = False):
        super().__init__()
        self.setWindowTitle("AutoClicker ©️2025 KisaragiIchigo")
        self._resizing = False; self._moving = False
        self._theme = COLORS_STOP
        # 記録点（GUI側でも保持）
        self._record_points: list[tuple[int,int]] = []

        # 参照ウィジェット（先宣言）
        self.ed_key_repeat: QLineEdit | None = None
        self.ed_key_sequence: QLineEdit | None = None
        self.ed_hotkey: QLineEdit | None = None
        self.chk_start_min: QCheckBox | None = None
        self.lbl_rec_count: QLabel | None = None

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        icon_file = resource_path(os.path.join("assets", "AutoClicker.ico"))
        self.setWindowIcon(QIcon(icon_file) if os.path.exists(icon_file) else self.style().standardIcon(QStyle.SP_ComputerIcon))

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        self.bg = QWidget(); self.bg.setObjectName("bgRoot"); root.addWidget(self.bg)
        bgL = QVBoxLayout(self.bg); bgL.setContentsMargins(GAP,GAP,GAP,GAP); bgL.setSpacing(GAP)
        self.card = QWidget(); self.card.setObjectName("glassRoot"); bgL.addWidget(self.card)
        self.shadow = apply_drop_shadow(self.card)
        main = QVBoxLayout(self.card); main.setContentsMargins(PAD,PAD,PAD,PAD); main.setSpacing(GAP)

        # タイトルバー
        bar = QHBoxLayout()
        title = QLabel("AutoClicker"); title.setObjectName("titleLabel"); bar.addWidget(title); bar.addStretch(1)
        self.btn_menu = QPushButton("≡"); self.btn_menu.setFixedSize(28,28); self.btn_menu.clicked.connect(lambda: self._toggle_menu(True)); bar.addWidget(self.btn_menu)
        btn_readme = QPushButton("ReadMe"); btn_readme.clicked.connect(self._open_readme); bar.addWidget(btn_readme)
        self.btn_min = QPushButton("＿"); self.btn_min.setObjectName("minBtn"); self.btn_min.setFixedSize(28,28); self.btn_min.clicked.connect(self.showMinimized); bar.addWidget(self.btn_min)
        self.btn_max = QPushButton("🗖"); self.btn_max.setObjectName("maxBtn"); self.btn_max.setFixedSize(28,28); self.btn_max.clicked.connect(self._toggle_max_restore); bar.addWidget(self.btn_max)
        self.btn_close = QPushButton("x"); self.btn_close.setObjectName("closeBtn"); self.btn_close.setFixedSize(28,28); self.btn_close.clicked.connect(self.close); bar.addWidget(self.btn_close)
        main.addLayout(bar)

        if not is_admin():
            banner = QLabel("⚠ 一部アプリでは管理者権限が必要です（権限不足だとクリックが届かない場合があります）。")
            banner.setObjectName("banner"); main.addWidget(banner)

        # メインパネル
        panel = QWidget(); panel.setProperty("class","DarkPanel"); pl = QVBoxLayout(panel); pl.setSpacing(12)

        # プロファイル
        row_pf = QHBoxLayout(); row_pf.addStretch(1); row_pf.addWidget(QLabel("プロファイル　:"))
        self.cmb_profile = QComboBox(); self.cmb_profile.setEditable(True); row_pf.addWidget(self.cmb_profile, 2)
        self.btn_pf_apply = QPushButton("適用"); self.btn_pf_save = QPushButton("保存/上書"); self.btn_pf_del = QPushButton("削除")
        row_pf.addWidget(self.btn_pf_apply); row_pf.addWidget(self.btn_pf_save); row_pf.addWidget(self.btn_pf_del); row_pf.addStretch(1)
        pl.addLayout(row_pf)

        # 連打ボタン
        gb_btn = QGroupBox("連打ボタン"); gbl = QHBoxLayout(gb_btn)
        self.rb_left = QRadioButton("左クリック"); self.rb_right = QRadioButton("右クリック"); self.rb_key = QRadioButton("指定キー/キー列")
        self.rb_left.setChecked(True)
        self._btn_group = QButtonGroup(gb_btn); [self._btn_group.addButton(rb) for rb in (self.rb_left,self.rb_right,self.rb_key)]
        gbl.addStretch(1); gbl.addWidget(self.rb_left); gbl.addWidget(self.rb_right); gbl.addWidget(self.rb_key); gbl.addStretch(1)
        pl.addWidget(gb_btn)

        # クリック座標
        gb_pos = QGroupBox("クリック座標"); gp = QHBoxLayout(gb_pos)
        self.rb_pos_follow = QRadioButton("現在位置"); self.rb_pos_fixed = QRadioButton("固定座標"); self.rb_pos_rand = QRadioButton("ランダム矩形"); self.rb_pos_rec = QRadioButton("記録操作")
        self.rb_pos_follow.setChecked(True)
        self._pos_group = QButtonGroup(gb_pos); [self._pos_group.addButton(rb) for rb in (self.rb_pos_follow,self.rb_pos_fixed,self.rb_pos_rand,self.rb_pos_rec)]
        gp.addStretch(1); gp.addWidget(self.rb_pos_follow); gp.addWidget(self.rb_pos_fixed); gp.addWidget(self.rb_pos_rand); gp.addWidget(self.rb_pos_rec); gp.addStretch(1)
        pl.addWidget(gb_pos)

        # ディレイ/バースト
        gb_burst = QGroupBox("ディレイ/バースト"); gl = QVBoxLayout(gb_burst)
        row_dur = QHBoxLayout(); row_dur.addStretch(1)
        row_dur.addWidget(QLabel("通常持続(秒)")); self.spin_norm_sec = QSpinBox(); self.spin_norm_sec.setRange(0,86400); self.spin_norm_sec.setValue(0); row_dur.addWidget(self.spin_norm_sec)
        row_dur.addSpacing(12); self.chk_b1 = QCheckBox("段１有効"); row_dur.addWidget(self.chk_b1)
        row_dur.addWidget(QLabel("段１持続(秒)")); self.spin_b1_sec = QSpinBox(); self.spin_b1_sec.setRange(0,120); self.spin_b1_sec.setValue(0); row_dur.addWidget(self.spin_b1_sec)
        row_dur.addSpacing(12); self.chk_b2 = QCheckBox("段２有効"); row_dur.addWidget(self.chk_b2)
        row_dur.addWidget(QLabel("段２持続(秒)")); self.spin_b2_sec = QSpinBox(); self.spin_b2_sec.setRange(0,120); self.spin_b2_sec.setValue(0); row_dur.addWidget(self.spin_b2_sec)
        row_dur.addStretch(1); gl.addLayout(row_dur)
        row_ms = QHBoxLayout(); row_ms.addStretch(1)
        row_ms.addWidget(QLabel("通常間隔(ms)")); self.spin_delay = QSpinBox(); self.spin_delay.setRange(1,10000); self.spin_delay.setValue(100); row_ms.addWidget(self.spin_delay)
        row_ms.addSpacing(12); row_ms.addWidget(QLabel("段１間隔(ms)")); self.spin_b1_ms = QSpinBox(); self.spin_b1_ms.setRange(1,10000); self.spin_b1_ms.setValue(50); row_ms.addWidget(self.spin_b1_ms)
        row_ms.addSpacing(12); row_ms.addWidget(QLabel("段２間隔(ms)")); self.spin_b2_ms = QSpinBox(); self.spin_b2_ms.setRange(1,10000); self.spin_b2_ms.setValue(20); row_ms.addWidget(self.spin_b2_ms)
        row_ms.addStretch(1); gl.addLayout(row_ms)
        pl.addWidget(gb_burst)

        # ステータス
        box_status = QGroupBox("") ; bs = QHBoxLayout(box_status)
        self.lbl_status = QLabel("停止中"); bs.addStretch(1); bs.addWidget(self.lbl_status); bs.addStretch(1)
        pl.addWidget(box_status)

        main.addWidget(panel)
        self.resize(860, 560); self.setMinimumSize(50, 50)

        # エンジン
        self.engine = AutoClickEngine()
        self.engine.state_changed.connect(self._on_engine_state)
        self.engine.point_recorded.connect(self._on_point_recorded)  # ★ F12受信

        # メニュー
        self._init_menu()

        # 設定ロード
        self.cfg = AppConfig.load()
        self._load_from_config()

        # イベント束ね
        for w in (self.spin_norm_sec, self.spin_b1_sec, self.spin_b2_sec, self.spin_delay, self.spin_b1_ms, self.spin_b2_ms):
            w.valueChanged.connect(self._on_ui_changed)
        for c in (self.chk_b1, self.chk_b2):
            c.stateChanged.connect(self._on_ui_changed)
        self._btn_group.buttonClicked.connect(self._on_ui_changed)
        self._pos_group.buttonClicked.connect(self._on_ui_changed)
        self.btn_pf_apply.clicked.connect(self._apply_profile)
        self.btn_pf_save.clicked.connect(self._save_profile)
        self.btn_pf_del.clicked.connect(self._delete_profile)
        self.cmb_profile.currentTextChanged.connect(self._on_profile_changed)

        # 背景でドラッグ/リサイズ
        self.bg.setMouseTracking(True); self.bg.installEventFilter(self)

        # UI定期
        self._ui_timer = QTimer(self); self._ui_timer.setInterval(250)
        self._ui_timer.timeout.connect(self._refresh_status_style); self._ui_timer.start()

        # トレイ
        self._init_tray()
        if self.cfg.get("start_minimized", False) and start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray.showMessage("AutoClicker", "バックグラウンドで待機中（ホットキーで開始/停止）")

        self._apply_theme(False)

    # ===== メニュー =====
    def _init_menu(self):
        self.overlay = QWidget(self); self.overlay.setObjectName("overlay"); self.overlay.setGeometry(0,0,self.width(),self.height()); self.overlay.hide()
        self.overlay.mousePressEvent = lambda e: self._toggle_menu(False)

        self.menuPanel = QWidget(self); self.menuPanel.setObjectName("menuPanel")
        self.menuPanel.setGeometry(-MENU_WIDTH, 0, MENU_WIDTH, self.height()); self.menuPanel.hide()
        v = QVBoxLayout(self.menuPanel); v.setContentsMargins(12,14,12,14); v.setSpacing(10)

        cap = QLabel("設定"); cap.setProperty("class","menuCaption"); v.addWidget(cap)

        v.addWidget(QLabel("指定キー（単発）"))
        self.ed_key_repeat = QLineEdit(); self.ed_key_repeat.setPlaceholderText("例: A / F8 / 0 （クリックしてキー入力）")
        self.ed_key_repeat.setReadOnly(True); self.ed_key_repeat.installEventFilter(self); v.addWidget(self.ed_key_repeat)

        v.addWidget(QLabel("キー列（カンマ区切り: 例 A,D,F8）"))
        self.ed_key_sequence = QLineEdit(); self.ed_key_sequence.setPlaceholderText("A,D,F8 など。空なら指定キーを使用")
        v.addWidget(self.ed_key_sequence)
        self.ed_key_sequence.textChanged.connect(self._on_ui_changed)

        # クリック座標XY＋記録
        v.addWidget(QLabel("クリック座標のXY設定"))
        row_fix = QHBoxLayout()
        row_fix.addWidget(QLabel("固定 X:")); self.spin_fx = QSpinBox(); self.spin_fx.setRange(0, 99999); row_fix.addWidget(self.spin_fx)
        row_fix.addWidget(QLabel("Y:")); self.spin_fy = QSpinBox(); self.spin_fy.setRange(0, 99999); row_fix.addWidget(self.spin_fy)
        v.addLayout(row_fix)
        row_rand1 = QHBoxLayout()
        row_rand1.addWidget(QLabel("ランダム Xmin:")); self.spin_rx1 = QSpinBox(); self.spin_rx1.setRange(0,99999); row_rand1.addWidget(self.spin_rx1)
        row_rand1.addWidget(QLabel("Xmax:")); self.spin_rx2 = QSpinBox(); self.spin_rx2.setRange(0,99999); self.spin_rx2.setValue(100); row_rand1.addWidget(self.spin_rx2)
        v.addLayout(row_rand1)
        row_rand2 = QHBoxLayout()
        row_rand2.addWidget(QLabel("ランダム Ymin:")); self.spin_ry1 = QSpinBox(); self.spin_ry1.setRange(0,99999); row_rand2.addWidget(self.spin_ry1)
        row_rand2.addWidget(QLabel("Ymax:")); self.spin_ry2 = QSpinBox(); self.spin_ry2.setRange(0,99999); self.spin_ry2.setValue(100); row_rand2.addWidget(self.spin_ry2)
        v.addLayout(row_rand2)

        # 記録操作の状況
        row_rec = QHBoxLayout()
        self.lbl_rec_count = QLabel("記録済み: 0件")
        btn_rec_clear = QPushButton("記録クリア")
        btn_rec_clear.clicked.connect(self._clear_record_points)
        row_rec.addWidget(self.lbl_rec_count); row_rec.addStretch(1); row_rec.addWidget(btn_rec_clear)
        v.addLayout(row_rec)

        # ホットキー
        v.addSpacing(6); v.addWidget(QLabel("ホットキー（開始/停止トグル）"))
        self.ed_hotkey = QLineEdit(); self.ed_hotkey.setPlaceholderText("ここをクリックして組み合わせを押す（例: Ctrl+Alt）")
        self.ed_hotkey.setReadOnly(True); self.ed_hotkey.installEventFilter(self); v.addWidget(self.ed_hotkey)

        self.chk_start_min = QCheckBox("起動時に最小化してトレイに常駐"); v.addWidget(self.chk_start_min)

        v.addStretch(1); btn_close = QPushButton("閉じる"); btn_close.clicked.connect(lambda: self._toggle_menu(False)); v.addWidget(btn_close)

        self.menu_anim = QPropertyAnimation(self.menuPanel, b"geometry", self)
        self.menu_anim.setDuration(220); self.menu_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._menu_visible = False; self._next_menu_visible = False
        self.menu_anim.finished.connect(self._after_menu)

    def _toggle_menu(self, show: bool | None = None):
        if show is None: show = not self._menu_visible
        h = self.height()
        self.menuPanel.setFixedHeight(h)
        self.overlay.setGeometry(0,0,self.width(),h)
        self.overlay.show(); self.overlay.raise_()
        self.menuPanel.show(); self.menuPanel.raise_()
        start = QRect(-MENU_WIDTH, 0, MENU_WIDTH, h) if show else QRect(self.menuPanel.geometry())
        end = QRect(0,0,MENU_WIDTH,h) if show else QRect(-MENU_WIDTH,0,MENU_WIDTH,h)
        self._next_menu_visible = show
        # ★ メニュー表示中は常時ミュート
        self.engine.set_hotkey_muted(True if show else False)
        self.menu_anim.stop(); self.menu_anim.setStartValue(start); self.menu_anim.setEndValue(end); self.menu_anim.start()

    def _after_menu(self):
        self._menu_visible = self._next_menu_visible
        if not self._menu_visible:
            self.menuPanel.hide(); self.overlay.hide()
            self.engine.set_hotkey_muted(False)

    # ===== トレイ =====
    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): self.tray = None; return
        icon_file = resource_path(os.path.join("assets", "AutoClicker.ico"))
        self.tray = QSystemTrayIcon(QIcon(icon_file) if os.path.exists(icon_file) else self.style().standardIcon(QStyle.SP_ComputerIcon), self)
        menu = QMenu()
        act_show   = QAction("ウィンドウを表示", self, triggered=lambda: (self.showNormal(), self.activateWindow()))
        act_toggle = QAction("開始/停止をトグル", self, triggered=self.engine.toggle)
        act_quit   = QAction("終了", self, triggered=self._quit)
        menu.addAction(act_show); menu.addAction(act_toggle); menu.addSeparator(); menu.addAction(act_quit)
        self.tray.setContextMenu(menu); self.tray.setToolTip("AutoClicker")
        self.tray.activated.connect(lambda r: (self.showNormal(), self.activateWindow()) if r==QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _quit(self):
        try:
            self._save_to_config(); self.engine.shutdown()
        finally:
            QApplication.quit()

    # ===== イベント =====
    def eventFilter(self, obj, e):
        # 背景: フレームレス移動/リサイズ
        if obj is self.bg:
            if e.type() == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                pos = self.mapFromGlobal(e.globalPosition().toPoint()); edges = self._edge_at(pos)
                if edges:
                    self._resizing = True; self._resize_edges = edges; self._start_geo = self.geometry(); self._start_mouse = e.globalPosition().toPoint()
                else:
                    self._moving = True; self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            elif e.type() == QEvent.MouseMove:
                if getattr(self, "_resizing", False):
                    self._resize_to(e.globalPosition().toPoint()); return True
                if getattr(self, "_moving", False) and (e.buttons() & Qt.LeftButton) and not self.isMaximized():
                    self.move(e.globalPosition().toPoint() - self._drag_offset); return True
            elif e.type() == QEvent.MouseButtonRelease:
                self._resizing = False; self._moving = False; return True

        # 指定キー（単発）
        if obj is self.ed_key_repeat:
            if e.type() == QEvent.FocusIn:
                self.ed_key_repeat.setText("（入力待ち…）"); return False
            if e.type() == QEvent.KeyPress:
                if e.key() in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt): return True
                txt = QKeySequence(e.key()).toString()
                self.ed_key_repeat.setText(txt if txt else ""); self._on_ui_changed(); return True

        # ホットキー（欄フォーカス中はミュート、閉じると解除）
        if obj is self.ed_hotkey:
            if e.type() == QEvent.FocusIn:
                self.engine.set_hotkey_muted(True)
                self.ed_hotkey.setText("（入力待ち…）"); return False
            if e.type() == QEvent.KeyPress:
                mods = []
                if e.modifiers() & Qt.ControlModifier: mods.append("Ctrl")
                if e.modifiers() & Qt.AltModifier:     mods.append("Alt")
                if e.modifiers() & Qt.ShiftModifier:   mods.append("Shift")
                key_txt = QKeySequence(e.key()).toString()
                spec = "+".join(mods + ([key_txt] if key_txt and e.key() not in (Qt.Key_Control,Qt.Key_Shift,Qt.Key_Alt) else [])) or "Ctrl+Alt"
                self.ed_hotkey.setText(spec)
                hk = HotkeySpec.from_string(spec)
                if hk: self.engine.update_hotkey(hk)
                return True
            if e.type() == QEvent.FocusOut:
                self.engine.set_hotkey_muted(self._menu_visible)  # メニューが開いていれば引き続きミュート
                return False

        return super().eventFilter(obj, e)

    # ===== データ収集 / エンジン連携 =====
    def _current_button(self) -> str:
        if self.rb_left.isChecked():  return "left"
        if self.rb_right.isChecked(): return "right"
        return "key"

    def _click_pos_mode(self):
        if self.rb_pos_fixed.isChecked():   return "fixed"
        if self.rb_pos_rand.isChecked():    return "random_rect"
        if self.rb_pos_rec.isChecked():     return "recorded"
        return "follow"

    def _gather_click_pos_params(self):
        mode = self._click_pos_mode()
        if mode == "fixed":
            return ("fixed", {"x": self.spin_fx.value(), "y": self.spin_fy.value()})
        if mode == "random_rect":
            x1,x2 = sorted([self.spin_rx1.value(), self.spin_rx2.value()])
            y1,y2 = sorted([self.spin_ry1.value(), self.spin_ry2.value()])
            return ("random_rect", {"x1": x1, "x2": x2, "y1": y1, "y2": y2})
        if mode == "recorded":
            return ("recorded", {})
        return ("follow", {})

    def _push_params(self):
        mode, params = self._gather_click_pos_params()
        seq_text = (self.ed_key_sequence.text().strip() if self.ed_key_sequence else "")
        key_seq = [t.strip() for t in seq_text.split(",") if t.strip()] if seq_text else []
        self.engine.set_params(
            button=self._current_button(),
            delay_ms=self.spin_delay.value(),
            burst1_enabled=self.chk_b1.isChecked(),
            burst1_sec=self.spin_b1_sec.value(),
            burst1_ms=self.spin_b1_ms.value(),
            burst2_enabled=self.chk_b2.isChecked(),
            burst2_sec=self.spin_b2_sec.value(),
            burst2_ms=self.spin_b2_ms.value(),
            normal_sec=self.spin_norm_sec.value(),
            click_mode=mode,
            click_params=params,
            key_to_repeat=(self.ed_key_repeat.text().strip() or None),
            key_sequence=key_seq,
            recorded_points=list(self._record_points)
        )

    # ===== 記録（F12） =====
    def _on_point_recorded(self, x: int, y: int):
        self._record_points.append((int(x), int(y)))
        if self.lbl_rec_count:
            self.lbl_rec_count.setText(f"記録済み: {len(self._record_points)}件")
        # 記録操作が未選択ならヒント的に切り替えはしない（ユーザー主導でOK）
        self._push_params()
        self._auto_save_current(snapshot_only=True)

    def _clear_record_points(self):
        self._record_points.clear()
        if self.lbl_rec_count:
            self.lbl_rec_count.setText("記録済み: 0件")
        self._push_params()
        self._auto_save_current(snapshot_only=True)

    # ===== プロファイル =====
    def _apply_profile(self):
        name = (self.cmb_profile.currentText() or "").strip()
        if not name: return
        p = (self.cfg.get("profiles") or {}).get(name)
        if p:
            self._load_profile(p)
            self.cfg["last_profile"] = name
            AppConfig.save(self.cfg)

    def _save_profile(self):
        name = (self.cmb_profile.currentText() or "NewProfile").strip()
        if not name:
            QMessageBox.warning(self, "保存", "プロファイル名を入力してね。"); return
        p = self._snapshot_profile()
        self.cfg.setdefault("profiles", {})[name] = p
        self.cfg["last_profile"] = name
        self.cfg = AppConfig.push_history(self.cfg, name, p)
        AppConfig.save(self.cfg)
        self._refresh_profile_list(select=name)
        QMessageBox.information(self, "保存", f"プロファイル '{name}' を保存したよ。")

    def _delete_profile(self):
        name = (self.cmb_profile.currentText() or "").strip()
        if not name: return
        profiles = self.cfg.get("profiles") or {}
        if name in profiles:
            profiles.pop(name)
            if self.cfg.get("last_profile") == name: self.cfg["last_profile"] = None
            AppConfig.save(self.cfg)
            self._refresh_profile_list()

    def _on_profile_changed(self, _txt: str):
        name = (self.cmb_profile.currentText() or "").strip()
        if name and name in (self.cfg.get("profiles") or {}):
            self.cfg["last_profile"] = name
            AppConfig.save(self.cfg)

    def _snapshot_profile(self) -> dict:
        mode, params = self._gather_click_pos_params()
        return {
            "button": self._current_button(),
            "delay_ms": int(self.spin_delay.value()),
            "burst1_enabled": bool(self.chk_b1.isChecked()),
            "burst1_sec": int(self.spin_b1_sec.value()),
            "burst1_ms":  int(self.spin_b1_ms.value()),
            "burst2_enabled": bool(self.chk_b2.isChecked()),
            "burst2_sec": int(self.spin_b2_sec.value()),
            "burst2_ms":  int(self.spin_b2_ms.value()),
            "normal_sec": int(self.spin_norm_sec.value()),
            "click_mode": mode,
            "click_params": params,
            "key_to_repeat": (self.ed_key_repeat.text().strip() or None),
            "key_sequence": [t.strip() for t in (self.ed_key_sequence.text().split(",") if self.ed_key_sequence else []) if t.strip()],
            "recorded_points": list(self._record_points)
        }

    def _auto_save_current(self, snapshot_only: bool=False):
        """値変更のたびに現在プロファイルへ上書き＆履歴追加（最大10件）"""
        name = (self.cmb_profile.currentText() or "").strip() or "NewProfile"
        p = self._snapshot_profile()
        self.cfg.setdefault("profiles", {})[name] = p
        self.cfg["last_profile"] = name
        self.cfg = AppConfig.push_history(self.cfg, name, p)
        if not snapshot_only:
            AppConfig.save(self.cfg)
        else:
            # 履歴だけでも保存しておく
            AppConfig.save(self.cfg)

    def _load_profile(self, p: dict):
        btn = p.get("button","left")
        self.rb_left.setChecked(btn=="left"); self.rb_right.setChecked(btn=="right"); self.rb_key.setChecked(btn=="key")
        self.spin_delay.setValue(int(p.get("delay_ms",100)))
        self.chk_b1.setChecked(bool(p.get("burst1_enabled", False)))
        self.spin_b1_sec.setValue(int(p.get("burst1_sec",0))); self.spin_b1_ms.setValue(int(p.get("burst1_ms",50)))
        self.chk_b2.setChecked(bool(p.get("burst2_enabled", False)))
        self.spin_b2_sec.setValue(int(p.get("burst2_sec",0))); self.spin_b2_ms.setValue(int(p.get("burst2_ms",20)))
        self.spin_norm_sec.setValue(int(p.get("normal_sec",0)))
        # 座標
        mode = p.get("click_mode","follow"); cp = p.get("click_params",{})
        if mode=="fixed":
            self.rb_pos_fixed.setChecked(True); self.spin_fx.setValue(int(cp.get("x",0))); self.spin_fy.setValue(int(cp.get("y",0)))
        elif mode=="random_rect":
            self.rb_pos_rand.setChecked(True)
            self.spin_rx1.setValue(int(cp.get("x1",0))); self.spin_rx2.setValue(int(cp.get("x2",100)))
            self.spin_ry1.setValue(int(cp.get("y1",0))); self.spin_ry2.setValue(int(cp.get("y2",100)))
        elif mode=="recorded":
            self.rb_pos_rec.setChecked(True)
        else:
            self.rb_pos_follow.setChecked(True)
        # キー/キー列
        if self.ed_key_repeat is not None:
            self.ed_key_repeat.setText(p.get("key_to_repeat") or "")
        if self.ed_key_sequence is not None:
            self.ed_key_sequence.setText(",".join(p.get("key_sequence", [])))
        # 記録点
        self._record_points = [(int(x),int(y)) for (x,y) in p.get("recorded_points", [])]
        if self.lbl_rec_count:
            self.lbl_rec_count.setText(f"記録済み: {len(self._record_points)}件")
        self._push_params()

    def _refresh_profile_list(self, select: str|None=None):
        self.cmb_profile.blockSignals(True); self.cmb_profile.clear()
        names = sorted((self.cfg.get("profiles") or {}).keys()); self.cmb_profile.addItems(names)
        candidate = select or self.cfg.get("last_profile")
        if candidate and candidate in names: self.cmb_profile.setCurrentText(candidate)
        elif names: self.cmb_profile.setCurrentText(names[0])
        else: self.cmb_profile.setEditText("")
        self.cmb_profile.blockSignals(False)

    # ===== 値変更ハンドラ =====
    def _on_ui_changed(self, *_):
        self._push_params()
        self._auto_save_current()

    # ===== 状態/テーマ =====
    def _on_engine_state(self, running: bool):
        self.lbl_status.setText("動作中" if running else "停止中")
        self._apply_status_style(running)
        self._apply_theme(running)

    def _apply_status_style(self, running: bool):
        bg = (COLORS_RUN if running else COLORS_STOP)["STATUS_BG"]
        self.lbl_status.setStyleSheet(f"QLabel{{background:{bg};color:#fff;padding:10px 12px;border-radius:8px;font-size:11pt;}}")

    def _apply_theme(self, running: bool):
        theme = COLORS_RUN if running else COLORS_STOP
        self.setStyleSheet(build_qss(self.isMaximized(), theme))
        if hasattr(self, "shadow"): self.shadow.setEnabled(not self.isMaximized())

    def _refresh_status_style(self):
        self._apply_status_style(self.engine.is_running())

    # ===== ウィンドウ制御 =====
    def _toggle_max_restore(self): self.showNormal() if self.isMaximized() else self.showMaximized()
    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            self._apply_theme(self.engine.is_running())
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "overlay"): self.overlay.setGeometry(0,0,self.width(),self.height())
        if hasattr(self, "menuPanel"):
            geo = self.menuPanel.geometry(); self.menuPanel.setGeometry(geo.x(), 0, MENU_WIDTH, self.height())

    # ===== ドラッグ/リサイズ実処理 =====
    def _edge_at(self, pos):
        m = RESIZE_MARGIN; r = self.bg.rect(); e = ""
        if pos.y() <= m: e += "T"
        if pos.y() >= r.height()-m: e += "B"
        if pos.x() <= m: e += "L"
        if pos.x() >= r.width()-m: e += "R"
        return e
    def _resize_to(self, gpos):
        dx = gpos.x()-self._start_mouse.x(); dy = gpos.y()-self._start_mouse.y()
        x,y,w,h = self._start_geo.x(), self._start_geo.y(), self._start_geo.width(), self._start_geo.height()
        minw, minh = self.minimumSize().width(), self.minimumSize().height()
        if "L" in self._resize_edges: new_w = max(minw, w-dx); x += (w-new_w); w = new_w
        if "R" in self._resize_edges: w = max(minw, w+dx)
        if "T" in self._resize_edges: new_h = max(minh, h-dy); y += (h-new_h); h = new_h
        if "B" in self._resize_edges: h = max(minh, h+dy)
        self.setGeometry(x,y,w,h)

    def _open_readme(self): ReadmeDialog(self).exec()

    # ===== 設定 =====
    def _load_from_config(self):
        profiles = self.cfg.get("profiles")
        if not isinstance(profiles, dict) or not profiles:
            self.cfg["profiles"] = {
                "デフォルト(左100ms)": {
                    "button":"left","delay_ms":100,
                    "burst1_enabled": False, "burst1_sec":0, "burst1_ms":50,
                    "burst2_enabled": False, "burst2_sec":0, "burst2_ms":20,
                    "normal_sec":0,
                    "click_mode":"follow","click_params":{},
                    "key_to_repeat":None, "key_sequence":[],
                    "recorded_points":[]
                }
            }
            self.cfg["last_profile"] = "デフォルト(左100ms)"
            AppConfig.save(self.cfg)
            profiles = self.cfg["profiles"]

        self._refresh_profile_list(select=self.cfg.get("last_profile"))
        sel = self.cmb_profile.currentText().strip()
        self._load_profile(profiles.get(sel, next(iter(profiles.values()))))

        spec = self.cfg.get("hotkey", "Ctrl+Alt")
        self.ed_hotkey.setText(spec)
        hk = HotkeySpec.from_string(spec)
        if hk: self.engine.update_hotkey(hk)
        self.chk_start_min.setChecked(bool(self.cfg.get("start_minimized", False)))
        self._push_params()

    def _save_to_config(self):
        self.cfg["hotkey"] = self.ed_hotkey.text().strip() or "Ctrl+Alt"
        self.cfg["start_minimized"] = bool(self.chk_start_min.isChecked())
        cur = (self.cmb_profile.currentText() or "").strip()
        if cur: self.cfg["last_profile"] = cur
        AppConfig.save(self.cfg)

    def closeEvent(self, e):
        try:
            self._save_to_config(); self.engine.shutdown()
        finally:
            super().closeEvent(e)
