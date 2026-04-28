"""
preferences_dialog.py — TunnelRAT Preferences

Covers:
  - Theme: Dark (default) / Light / Custom
  - Terminal colors: background, foreground, cursor, selection
  - Font: family, size, line height
  - Behavior: keepalive default, reconnect on close

Settings are saved to ~/.config/tunnelrat/preferences.json
and applied live without restart.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

log = logging.getLogger(__name__)

PREFS_PATH = Path.home() / ".config" / "tunnelrat" / "preferences.json"

# ── Built-in themes ───────────────────────────────────────────────────────────
THEMES = {
    # ── Dark themes ──────────────────────────────────────────────────────────
    "Dark (Default)": {
        "background":  "#0d1117", "foreground":  "#c9d1d9",
        "cursor":      "#58a6ff", "selection":   "rgba(88,166,255,0.28)",
        "black":"#484f58","bright_black":"#6e7681","red":"#ff7b72","bright_red":"#ffa198",
        "green":"#3fb950","bright_green":"#56d364","yellow":"#d29922","bright_yellow":"#e3b341",
        "blue":"#58a6ff","bright_blue":"#79c0ff","magenta":"#bc8cff","bright_magenta":"#d2a8ff",
        "cyan":"#39c5cf","bright_cyan":"#56d4dd","white":"#b1bac4","bright_white":"#f0f6fc",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Dracula": {
        "background":  "#282a36", "foreground":  "#f8f8f2",
        "cursor":      "#ff79c6", "selection":   "rgba(68,71,90,0.7)",
        "black":"#21222c","bright_black":"#6272a4","red":"#ff5555","bright_red":"#ff6e6e",
        "green":"#50fa7b","bright_green":"#69ff94","yellow":"#f1fa8c","bright_yellow":"#ffffa5",
        "blue":"#bd93f9","bright_blue":"#d6acff","magenta":"#ff79c6","bright_magenta":"#ff92df",
        "cyan":"#8be9fd","bright_cyan":"#a4ffff","white":"#f8f8f2","bright_white":"#ffffff",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Monokai": {
        "background":  "#272822", "foreground":  "#f8f8f2",
        "cursor":      "#a6e22e", "selection":   "rgba(73,72,62,0.6)",
        "black":"#272822","bright_black":"#75715e","red":"#f92672","bright_red":"#f92672",
        "green":"#a6e22e","bright_green":"#a6e22e","yellow":"#f4bf75","bright_yellow":"#f4bf75",
        "blue":"#66d9e8","bright_blue":"#66d9e8","magenta":"#ae81ff","bright_magenta":"#ae81ff",
        "cyan":"#a1efe4","bright_cyan":"#a1efe4","white":"#f8f8f2","bright_white":"#f9f8f5",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "One Dark": {
        "background":  "#282c34", "foreground":  "#abb2bf",
        "cursor":      "#61afef", "selection":   "rgba(62,68,82,0.7)",
        "black":"#3f4451","bright_black":"#4f5666","red":"#e06c75","bright_red":"#be5046",
        "green":"#98c379","bright_green":"#98c379","yellow":"#e5c07b","bright_yellow":"#d19a66",
        "blue":"#61afef","bright_blue":"#61afef","magenta":"#c678dd","bright_magenta":"#c678dd",
        "cyan":"#56b6c2","bright_cyan":"#56b6c2","white":"#abb2bf","bright_white":"#ffffff",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Tokyo Night": {
        "background":  "#1a1b26", "foreground":  "#a9b1d6",
        "cursor":      "#7aa2f7", "selection":   "rgba(36,40,59,0.8)",
        "black":"#15161e","bright_black":"#414868","red":"#f7768e","bright_red":"#ff9e64",
        "green":"#9ece6a","bright_green":"#73daca","yellow":"#e0af68","bright_yellow":"#ff9e64",
        "blue":"#7aa2f7","bright_blue":"#2ac3de","magenta":"#bb9af7","bright_magenta":"#9d7cd8",
        "cyan":"#7dcfff","bright_cyan":"#2ac3de","white":"#a9b1d6","bright_white":"#c0caf5",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Catppuccin Mocha": {
        "background":  "#1e1e2e", "foreground":  "#cdd6f4",
        "cursor":      "#cba6f7", "selection":   "rgba(88,91,112,0.5)",
        "black":"#45475a","bright_black":"#585b70","red":"#f38ba8","bright_red":"#f38ba8",
        "green":"#a6e3a1","bright_green":"#a6e3a1","yellow":"#f9e2af","bright_yellow":"#f9e2af",
        "blue":"#89b4fa","bright_blue":"#89b4fa","magenta":"#cba6f7","bright_magenta":"#cba6f7",
        "cyan":"#89dceb","bright_cyan":"#94e2d5","white":"#bac2de","bright_white":"#a6adc8",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Gruvbox Dark": {
        "background":  "#1d2021", "foreground":  "#ebdbb2",
        "cursor":      "#fabd2f", "selection":   "rgba(80,73,69,0.7)",
        "black":"#282828","bright_black":"#928374","red":"#cc241d","bright_red":"#fb4934",
        "green":"#98971a","bright_green":"#b8bb26","yellow":"#d79921","bright_yellow":"#fabd2f",
        "blue":"#458588","bright_blue":"#83a598","magenta":"#b16286","bright_magenta":"#d3869b",
        "cyan":"#689d6a","bright_cyan":"#8ec07c","white":"#a89984","bright_white":"#ebdbb2",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Nord": {
        "background":  "#2e3440", "foreground":  "#eceff4",
        "cursor":      "#88c0d0", "selection":   "rgba(67,76,94,0.7)",
        "black":"#3b4252","bright_black":"#4c566a","red":"#bf616a","bright_red":"#bf616a",
        "green":"#a3be8c","bright_green":"#a3be8c","yellow":"#ebcb8b","bright_yellow":"#ebcb8b",
        "blue":"#81a1c1","bright_blue":"#81a1c1","magenta":"#b48ead","bright_magenta":"#b48ead",
        "cyan":"#88c0d0","bright_cyan":"#8fbcbb","white":"#e5e9f0","bright_white":"#eceff4",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    # ── Light themes ─────────────────────────────────────────────────────────
    "Light": {
        "background":  "#ffffff", "foreground":  "#24292f",
        "cursor":      "#0969da", "selection":   "rgba(9,105,218,0.18)",
        "black":"#24292f","bright_black":"#57606a","red":"#cf222e","bright_red":"#a40e26",
        "green":"#116329","bright_green":"#1a7f37","yellow":"#4d2d00","bright_yellow":"#633c01",
        "blue":"#0969da","bright_blue":"#218bff","magenta":"#8250df","bright_magenta":"#a475f9",
        "cyan":"#1b7c83","bright_cyan":"#3192aa","white":"#6e7781","bright_white":"#8c959f",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Solarized Light": {
        "background":  "#fdf6e3", "foreground":  "#657b83",
        "cursor":      "#268bd2", "selection":   "rgba(38,139,210,0.2)",
        "black":"#073642","bright_black":"#002b36","red":"#dc322f","bright_red":"#cb4b16",
        "green":"#859900","bright_green":"#586e75","yellow":"#b58900","bright_yellow":"#657b83",
        "blue":"#268bd2","bright_blue":"#839496","magenta":"#d33682","bright_magenta":"#6c71c4",
        "cyan":"#2aa198","bright_cyan":"#93a1a1","white":"#eee8d5","bright_white":"#fdf6e3",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Solarized Dark": {
        "background":  "#002b36", "foreground":  "#839496",
        "cursor":      "#268bd2", "selection":   "rgba(38,139,210,0.3)",
        "black":"#073642","bright_black":"#586e75","red":"#dc322f","bright_red":"#cb4b16",
        "green":"#859900","bright_green":"#586e75","yellow":"#b58900","bright_yellow":"#657b83",
        "blue":"#268bd2","bright_blue":"#839496","magenta":"#d33682","bright_magenta":"#6c71c4",
        "cyan":"#2aa198","bright_cyan":"#93a1a1","white":"#eee8d5","bright_white":"#fdf6e3",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Catppuccin Latte": {
        "background":  "#eff1f5", "foreground":  "#4c4f69",
        "cursor":      "#8839ef", "selection":   "rgba(172,176,190,0.4)",
        "black":"#5c5f77","bright_black":"#6c6f85","red":"#d20f39","bright_red":"#d20f39",
        "green":"#40a02b","bright_green":"#40a02b","yellow":"#df8e1d","bright_yellow":"#df8e1d",
        "blue":"#1e66f5","bright_blue":"#1e66f5","magenta":"#8839ef","bright_magenta":"#8839ef",
        "cyan":"#04a5e5","bright_cyan":"#179299","white":"#acb0be","bright_white":"#bcc0cc",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    # ── High contrast ─────────────────────────────────────────────────────────
    "Midnight": {
        "background":  "#000000", "foreground":  "#00ff41",
        "cursor":      "#00ff41", "selection":   "rgba(0,255,65,0.25)",
        "black":"#000000","bright_black":"#003b00","red":"#ff0000","bright_red":"#ff4444",
        "green":"#00ff41","bright_green":"#44ff77","yellow":"#ffff00","bright_yellow":"#ffff66",
        "blue":"#0080ff","bright_blue":"#44aaff","magenta":"#ff00ff","bright_magenta":"#ff66ff",
        "cyan":"#00ffff","bright_cyan":"#66ffff","white":"#cccccc","bright_white":"#ffffff",
        "font_family":"JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace",
        "font_size":13,"line_height":1.2,
    },
    "Custom": {},
}


def load_prefs() -> dict:
    """Load preferences, falling back to defaults.
    Always includes both terminal AND app theme defaults so that
    app_* keys are never missing (which would cause grey #333333 fallbacks
    in the preferences dialog color buttons on first run)."""
    defaults = dict(THEMES["Dark (Default)"])
    defaults["theme"] = "Dark (Default)"
    defaults["default_keepalive"] = 60
    # Always seed app theme defaults — prevents grey app on first run
    defaults.update(APP_THEMES["Dark (Default)"])
    defaults["app_theme"] = "Dark (Default)"
    defaults.setdefault("hotkeys", {
        "next_tab":          "Ctrl+Tab",
        "prev_tab":          "Ctrl+Shift+Tab",
        "close_tab":         "Ctrl+W",
        "fullscreen":        "F11",
        "new_session":       "Ctrl+N",
        "quick_connect":     "Ctrl+Shift+Q",
        "connect_selected":  "Ctrl+Return",
        "disconnect_current":"Ctrl+W",
        "focus_broadcast":   "Ctrl+Shift+B",
        "rename_tab":        "F2",
        "command_mask":      "Ctrl+Shift+8",
        "always_on_top":     "",
        "save_layout":       "Ctrl+S",
    })
    try:
        if PREFS_PATH.exists():
            saved = json.loads(PREFS_PATH.read_text())
            defaults.update(saved)
    except Exception as e:
        log.warning("Could not load preferences: %s", e)
    return defaults


def save_prefs(prefs: dict):
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2))


def build_xterm_theme(prefs: dict) -> str:
    """Build the xterm.js theme object JS string from preferences."""
    return f"""{{
    background:'{prefs.get("background","#0d1117")}',
    foreground:'{prefs.get("foreground","#c9d1d9")}',
    cursor:'{prefs.get("cursor","#58a6ff")}',
    cursorAccent:'{prefs.get("background","#0d1117")}',
    selectionBackground:'{prefs.get("selection","rgba(88,166,255,0.28)")}',
    black:'{prefs.get("black","#484f58")}',
    red:'{prefs.get("red","#ff7b72")}',
    green:'{prefs.get("green","#3fb950")}',
    yellow:'{prefs.get("yellow","#d29922")}',
    blue:'{prefs.get("blue","#58a6ff")}',
    magenta:'{prefs.get("magenta","#bc8cff")}',
    cyan:'{prefs.get("cyan","#39c5cf")}',
    white:'{prefs.get("white","#b1bac4")}',
    brightBlack:'{prefs.get("bright_black","#6e7681")}',
    brightRed:'{prefs.get("bright_red","#ffa198")}',
    brightGreen:'{prefs.get("bright_green","#56d364")}',
    brightYellow:'{prefs.get("bright_yellow","#e3b341")}',
    brightBlue:'{prefs.get("bright_blue","#79c0ff")}',
    brightMagenta:'{prefs.get("bright_magenta","#d2a8ff")}',
    brightCyan:'{prefs.get("bright_cyan","#56d4dd")}',
    brightWhite:'{prefs.get("bright_white","#f0f6fc")}',
}}"""


# ── Color swatch button ───────────────────────────────────────────────────────

class _ColorBtn(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 22)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: str):
        self._color = color
        self.setStyleSheet(
            f"background:{color};border:1px solid #30363d;border-radius:3px;")

    def color(self) -> str:
        return self._color

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self,
                                  options=QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            self.set_color(c.name())
            self.color_changed.emit(self._color)


# ── Main dialog ───────────────────────────────────────────────────────────────

class PreferencesDialog(QDialog):
    prefs_changed = pyqtSignal(dict)   # emitted when Apply/OK pressed

    APPLY_STYLE_DEFAULT = ""
    APPLY_STYLE_PENDING = "background: #238636; color: white; border: none; font-weight: bold;"

    DIALOG_STYLE = """
    QDialog { background: #0d1117; color: #c9d1d9; }
    QTabWidget::pane { border: 1px solid #21262d; background: #0d1117; }
    QTabBar::tab { background: #161b22; color: #8b949e; padding: 6px 16px;
                   border: none; }
    QTabBar::tab:selected { background: #0d1117; color: #58a6ff;
                            border-bottom: 2px solid #58a6ff; }
    QGroupBox { color: #8b949e; border: 1px solid #21262d; border-radius: 4px;
                margin-top: 8px; padding-top: 8px; font-size: 11px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; }
    QLabel { color: #c9d1d9; }
    QComboBox, QSpinBox, QDoubleSpinBox {
        background: #161b22; color: #c9d1d9;
        border: 1px solid #30363d; border-radius: 4px; padding: 4px 8px; }
    QComboBox:focus, QSpinBox:focus { border-color: #58a6ff; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background: #161b22; color: #c9d1d9;
        border: 1px solid #30363d; selection-background-color: #21262d; }
    QPushButton { background: #21262d; color: #c9d1d9;
        border: 1px solid #30363d; border-radius: 4px; padding: 5px 14px; }
    QPushButton:hover { background: #30363d; }
    QPushButton#ok_btn { background: #238636; color: white; border: none; }
    QPushButton#ok_btn:hover { background: #2ea043; }
    QFontComboBox { background: #161b22; color: #c9d1d9;
        border: 1px solid #30363d; border-radius: 4px; padding: 4px 8px; }
    QSlider::groove:horizontal { height: 4px; background: #30363d;
        border-radius: 2px; }
    QSlider::handle:horizontal { background: #58a6ff; width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px; }
    QSlider::sub-page:horizontal { background: #58a6ff; border-radius: 2px; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TunnelRAT — Preferences")
        self.setMinimumSize(560, 480)
        from preferences_dialog import build_dialog_stylesheet, load_prefs
        self.setStyleSheet(build_dialog_stylesheet(load_prefs()))

        self._prefs = load_prefs()
        self._color_btns: dict[str, _ColorBtn] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        tabs = QTabWidget()
        tabs.addTab(self._build_appearance(), "Terminal Theme")
        tabs.addTab(self._build_terminal(),   "Font")
        tabs.addTab(self._build_app_theme(),  "App Theme")
        tabs.addTab(self._build_behavior(),   "Behavior")
        tabs.addTab(self._build_hotkeys(),    "Hotkeys")
        # Scope tab styling to this dialog only — doesn't affect TilePane
        tabs.setObjectName("prefs_tabs")
        layout.addWidget(tabs)

        # Button row with export/import
        btn_row = QHBoxLayout()
        save_btn   = QPushButton("💾 Save Theme…")
        export_btn = QPushButton("📤 Export Theme…")
        import_btn = QPushButton("📥 Import Theme…")
        for b in (save_btn, export_btn, import_btn):
            b.setStyleSheet("padding: 5px 10px;")
        save_btn.clicked.connect(self._on_save_theme)
        export_btn.clicked.connect(self._on_export_theme)
        import_btn.clicked.connect(self._on_import_theme)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(import_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Cancel)
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("ok_btn")
        self._btns.accepted.connect(self._on_ok)
        self._btns.rejected.connect(self.reject)
        self._btns.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply)
        layout.addWidget(self._btns)

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _build_appearance(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)

        # Theme selector
        theme_box = QGroupBox("Theme")
        tf = QFormLayout(theme_box)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(THEMES.keys()))
        cur = self._prefs.get("theme", "Dark (Default)")
        self._theme_combo.setCurrentText(cur if cur in THEMES else "Dark (Default)")
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self._theme_combo.currentTextChanged.connect(lambda _: self._mark_dirty())
        tf.addRow("Preset:", self._theme_combo)
        lay.addWidget(theme_box)

        # Color swatches
        color_box = QGroupBox("Colors  (click to change)")
        grid = QFormLayout(color_box)
        colors = [
            ("background",  "Background"),
            ("foreground",  "Foreground (text)"),
            ("cursor",      "Cursor"),
            ("black",       "Black"),    ("bright_black",   "Bright Black"),
            ("red",         "Red"),      ("bright_red",     "Bright Red"),
            ("green",       "Green"),    ("bright_green",   "Bright Green"),
            ("yellow",      "Yellow"),   ("bright_yellow",  "Bright Yellow"),
            ("blue",        "Blue"),     ("bright_blue",    "Bright Blue"),
            ("magenta",     "Magenta"),  ("bright_magenta", "Bright Magenta"),
            ("cyan",        "Cyan"),     ("bright_cyan",    "Bright Cyan"),
            ("white",       "White"),    ("bright_white",   "Bright White"),
        ]
        for key, label in colors:
            btn = _ColorBtn(self._prefs.get(key, "#888888"))
            btn.color_changed.connect(
                lambda c, k=key: self._on_color_changed(k, c))
            self._color_btns[key] = btn
            row = QHBoxLayout()
            row.addWidget(btn)
            row.addStretch()
            grid.addRow(label + ":", row)

        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(color_box)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        lay.addWidget(scroll)
        return w

    def _build_terminal(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)

        font_box = QGroupBox("Font")
        ff = QFormLayout(font_box)

        self._font_combo = QFontComboBox()
        self._font_combo.setFontFilters(
            QFontComboBox.FontFilter.MonospacedFonts)
        fam = self._prefs.get("font_family", "JetBrains Mono").split(",")[0]
        self._font_combo.setCurrentFont(QFont(fam))
        ff.addRow("Family:", self._font_combo)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 32)
        self._font_size_spin.setValue(int(self._prefs.get("font_size", 13)))
        self._font_size_spin.setSuffix(" px")
        self._font_size_spin.valueChanged.connect(lambda _: self._mark_dirty())
        ff.addRow("Size:", self._font_size_spin)

        self._line_height_spin = QDoubleSpinBox()
        self._line_height_spin.setRange(1.0, 2.0)
        self._line_height_spin.setSingleStep(0.05)
        self._line_height_spin.setDecimals(2)
        self._line_height_spin.setValue(float(self._prefs.get("line_height", 1.2)))
        self._line_height_spin.valueChanged.connect(lambda _: self._mark_dirty())
        ff.addRow("Line Height:", self._line_height_spin)

        lay.addWidget(font_box)
        lay.addStretch()
        return w

    def _build_behavior(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)

        conn_box = QGroupBox("Connection")
        cf = QFormLayout(conn_box)

        self._keepalive_spin = QSpinBox()
        self._keepalive_spin.setRange(0, 3600)
        self._keepalive_spin.setValue(int(self._prefs.get("default_keepalive", 60)))
        self._keepalive_spin.setSuffix("  sec  (0 = off)")
        self._keepalive_spin.valueChanged.connect(lambda _: self._mark_dirty())
        cf.addRow("Default Keepalive:", self._keepalive_spin)

        lay.addWidget(conn_box)
        lay.addStretch()
        return w

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_theme_changed(self, name: str):
        if name == "Custom":
            return
        theme = THEMES.get(name, {})
        for key, btn in self._color_btns.items():
            if key in theme:
                btn.set_color(theme[key])
        if "font_size" in theme:
            self._font_size_spin.setValue(int(theme["font_size"]))
        if "line_height" in theme:
            self._line_height_spin.setValue(float(theme["line_height"]))

    def _on_color_changed(self, key: str, color: str):
        self._prefs[key] = color
        self._theme_combo.setCurrentText("Custom")
        self._mark_dirty()

    def _build_app_theme(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)

        box = QGroupBox("Application Theme")
        bf = QFormLayout(box)
        self._app_theme_combo = QComboBox()
        self._app_theme_combo.addItems(list(APP_THEMES.keys()) + ["Custom"])
        cur = self._prefs.get("app_theme", "Dark (Default)")
        self._app_theme_combo.setCurrentText(
            cur if cur in APP_THEMES or cur == "Custom" else "Dark (Default)")
        self._app_theme_combo.currentTextChanged.connect(self._on_app_theme_changed)
        self._app_theme_combo.currentTextChanged.connect(lambda _: self._mark_dirty())
        bf.addRow("Preset:", self._app_theme_combo)

        app_colors = [
            ("app_bg",      "Background"),
            ("app_surface", "Surface / panels"),
            ("app_border",  "Borders"),
            ("app_text",    "Text"),
            ("app_dim",     "Dim text"),
            ("app_accent",  "Accent / highlight"),
            ("app_hover",   "Hover"),
        ]
        for key, label in app_colors:
            btn = _ColorBtn(self._prefs.get(key, "#333333"))
            btn.color_changed.connect(
                lambda c, k=key: self._on_app_color_changed(k, c))
            self._color_btns[key] = btn
            row = QHBoxLayout(); row.addWidget(btn); row.addStretch()
            bf.addRow(label + ":", row)

        lay.addWidget(box)
        note = QLabel("Changes apply after clicking Apply or OK.")
        note.setStyleSheet("color:#484f58; font-size:10px;")
        lay.addWidget(note)
        lay.addStretch()
        return w

    def _on_app_theme_changed(self, name: str):
        if name == "Custom":
            return
        theme = APP_THEMES.get(name, {})
        for key, val in theme.items():
            if key in self._color_btns:
                self._color_btns[key].set_color(val)

    def _on_app_color_changed(self, key: str, color: str):
        self._prefs[key] = color
        if hasattr(self, "_app_theme_combo"):
            self._app_theme_combo.setCurrentText("Custom")
        self._mark_dirty()

    def _on_save_theme(self):
        """Save current colors as a named custom theme entry."""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Theme",
                                        "Theme name:")
        if not ok or not name.strip():
            return
        p = self._collect()
        themes_dir = Path.home() / ".config" / "tunnelrat" / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        path = themes_dir / f"{name.strip()}.json"
        path.write_text(json.dumps(p, indent=2))
        QMessageBox.information(self, "Saved",
            f"Theme saved to:\n{path}")

    def _on_export_theme(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Theme", str(Path.home() / "tunnelrat-theme.json"),
            "JSON Files (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self._collect(), indent=2))
            QMessageBox.information(self, "Exported", f"Theme exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _on_import_theme(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Theme", str(Path.home()),
            "JSON Files (*.json)")
        if not path:
            return
        try:
            imported = json.loads(Path(path).read_text())
            # Apply imported values to color buttons
            for key, btn in self._color_btns.items():
                if key in imported:
                    btn.set_color(imported[key])
            if "font_size" in imported:
                self._font_size_spin.setValue(int(imported["font_size"]))
            if "line_height" in imported:
                self._line_height_spin.setValue(float(imported["line_height"]))
            if hasattr(self, "_app_theme_combo"):
                self._app_theme_combo.setCurrentText("Custom")
            if hasattr(self, "_theme_combo"):
                self._theme_combo.setCurrentText("Custom")
            QMessageBox.information(self, "Imported",
                "Theme imported. Click Apply to use it.")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    # ── Hotkey action labels ─────────────────────────────────────────────────
    HOTKEY_ACTIONS = [
        ("next_tab",           "Next Tab"),
        ("prev_tab",           "Previous Tab"),
        ("close_tab",          "Close Tab"),
        ("fullscreen",         "Toggle Fullscreen"),
        ("new_session",        "New Session"),
        ("quick_connect",      "Quick Connect"),
        ("connect_selected",   "Connect Selected"),
        ("disconnect_current", "Disconnect Current"),
        ("focus_broadcast",    "Focus Broadcast Bar"),
        ("rename_tab",         "Rename Tab"),
        ("command_mask",       "Toggle Command Mask"),
        ("always_on_top",      "Toggle Always on Top"),
        ("save_layout",        "Save Layout"),
    ]

    def _build_hotkeys(self) -> QWidget:
        from PyQt6.QtWidgets import QKeySequenceEdit, QTableWidget, QTableWidgetItem
        from PyQt6.QtCore import Qt as _Qt
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Keyboard Shortcuts")
        bf = QVBoxLayout(box)

        note = QLabel("Click a shortcut to edit it. Leave blank to disable.")
        note.setStyleSheet("color:#484f58; font-size:10px;")
        bf.addWidget(note)

        hotkeys = self._prefs.get("hotkeys", {})
        self._hotkey_edits: dict = {}

        from PyQt6.QtWidgets import QFormLayout
        fl = QFormLayout()
        fl.setSpacing(6)
        for key, label in self.HOTKEY_ACTIONS:
            from PyQt6.QtGui import QKeySequence
            edit = QKeySequenceEdit()
            current = hotkeys.get(key, "")
            if current:
                edit.setKeySequence(QKeySequence(current))
            edit.keySequenceChanged.connect(lambda _ks, k=key: self._mark_dirty())
            self._hotkey_edits[key] = edit
            fl.addRow(label + ":", edit)
        bf.addLayout(fl)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_hotkeys)
        bf.addWidget(reset_btn)

        lay.addWidget(box)
        lay.addStretch()
        return w

    def _reset_hotkeys(self):
        from PyQt6.QtGui import QKeySequence
        defaults = {
            "next_tab": "Ctrl+Tab", "prev_tab": "Ctrl+Shift+Tab",
            "close_tab": "Ctrl+W", "fullscreen": "F11",
            "new_session": "Ctrl+N", "quick_connect": "Ctrl+Shift+Q",
            "connect_selected": "Ctrl+Return", "disconnect_current": "Ctrl+W",
            "focus_broadcast": "Ctrl+Shift+B", "rename_tab": "F2",
            "command_mask": "Ctrl+Shift+8", "always_on_top": "",
            "save_layout": "Ctrl+S",
        }
        for key, edit in self._hotkey_edits.items():
            edit.setKeySequence(QKeySequence(defaults.get(key, "")))
        self._mark_dirty()

    def _collect(self) -> dict:
        p = dict(self._prefs)
        p["theme"] = self._theme_combo.currentText()
        if hasattr(self, "_app_theme_combo"):
            p["app_theme"] = self._app_theme_combo.currentText()
        for key, btn in self._color_btns.items():
            p[key] = btn.color()
        # Preserve full fallback stack — just update the primary font
        primary = self._font_combo.currentFont().family()
        fallback = "Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace"
        existing = p.get("font_family", "")
        # Replace only the first entry, keep the rest
        parts = [f.strip() for f in existing.split(",") if f.strip()]
        if parts:
            parts[0] = primary
        else:
            parts = [primary] + fallback.split(",")
        p["font_family"] = ",".join(parts)
        p["font_size"]   = self._font_size_spin.value()
        p["line_height"] = self._line_height_spin.value()
        p["default_keepalive"] = self._keepalive_spin.value()
        if hasattr(self, "_hotkey_edits"):
            hotkeys = {}
            for key, edit in self._hotkey_edits.items():
                ks = edit.keySequence().toString()
                hotkeys[key] = ks
            p["hotkeys"] = hotkeys
        return p

    def _mark_dirty(self):
        """Highlight Apply button to indicate pending unsaved changes."""
        from PyQt6.QtWidgets import QDialogButtonBox
        btn = self._btns.button(QDialogButtonBox.StandardButton.Apply)
        if btn:
            btn.setStyleSheet(self.APPLY_STYLE_PENDING)

    def _clear_dirty(self):
        from PyQt6.QtWidgets import QDialogButtonBox
        btn = self._btns.button(QDialogButtonBox.StandardButton.Apply)
        if btn:
            btn.setStyleSheet(self.APPLY_STYLE_DEFAULT)

    def _on_apply(self):
        self._prefs = self._collect()
        save_prefs(self._prefs)
        self.prefs_changed.emit(self._prefs)
        self._clear_dirty()
        # Re-apply dialog stylesheet live so Preferences itself updates
        self.setStyleSheet(build_dialog_stylesheet(self._prefs))

    def _on_ok(self):
        self._on_apply()
        self.accept()


def build_dialog_stylesheet(prefs: dict) -> str:
    """
    Stylesheet for dialog windows — applied directly to each QDialog.
    Covers inputs, buttons, groupboxes, checkboxes, comboboxes.
    """
    bg     = prefs.get("app_bg",      "#0d1117")
    surf   = prefs.get("app_surface", "#161b22")
    border = prefs.get("app_border",  "#21262d")
    text   = prefs.get("app_text",    "#c9d1d9")
    dim    = prefs.get("app_dim",     "#8b949e")
    accent = prefs.get("app_accent",  "#58a6ff")
    hover  = prefs.get("app_hover",   "#1c2128")
    return f"""
QDialog {{ background: {surf}; color: {text}; }}
QLabel {{ color: {dim}; font-size: 12px; }}
QGroupBox {{
    color: {dim}; border: 1px solid {border}; border-radius: 6px;
    margin-top: 12px; padding-top: 12px; font-size: 12px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {dim}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {bg}; color: {text};
    border: 1px solid {border}; border-radius: 4px;
    padding: 4px 8px; font-size: 13px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTextEdit:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {surf}; color: {text}; border: 1px solid {border};
    selection-background-color: {hover};
}}
QFontComboBox {{ background: {bg}; color: {text}; border: 1px solid {border}; border-radius: 4px; padding: 4px 8px; }}
QPushButton {{
    background: {hover}; color: {text};
    border: 1px solid {border}; border-radius: 4px;
    padding: 5px 14px; font-size: 12px;
}}
QPushButton:hover {{ background: {surf}; border-color: {accent}; color: {accent}; }}
QPushButton:disabled {{ color: {dim}; }}
QPushButton#ok_btn {{ background: {accent}; color: white; border-color: {accent}; }}
QPushButton#ok_btn:hover {{ background: {accent}; }}
QCheckBox {{ color: {text}; font-size: 12px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {border}; border-radius: 3px; background: {bg};
}}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QScrollArea {{ background: {surf}; border: none; }}
QScrollArea > QWidget > QWidget {{ background: {surf}; }}
QTabWidget#prefs_tabs::pane {{ border: 1px solid {border}; background: {surf}; border-radius: 4px; }}
QTabWidget#prefs_tabs > QTabBar::tab {{
    background: {hover}; color: {dim}; padding: 6px 16px; border: none;
    border-bottom: 2px solid transparent; min-width: 80px;
}}
QTabWidget#prefs_tabs > QTabBar::tab:selected {{
    background: {surf}; color: {accent}; border-bottom: 2px solid {accent};
}}
QTabWidget#prefs_tabs > QTabBar::tab:hover {{ background: {surf}; color: {text}; }}
QScrollBar:vertical {{ background: {bg}; width: 8px; border: none; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {dim}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
/* ── QFileDialog internal widgets ───────────────────────────────────── */
QFileDialog QSplitter {{ background: {surf}; }}
QFileDialog QSplitter::handle {{ background: {border}; width: 1px; }}
QFileDialog QListView, QFileDialog QTreeView {{
    background: {surf}; color: {text}; border: none;
}}
QFileDialog QListView::item, QFileDialog QTreeView::item {{
    color: {text}; padding: 3px;
}}
QFileDialog QListView::item:selected, QFileDialog QTreeView::item:selected {{
    background: {hover}; color: {accent};
}}
QFileDialog QListView::item:hover, QFileDialog QTreeView::item:hover {{
    background: {hover};
}}
QFileDialog QSideBar, QFileDialog QAbstractItemView {{
    background: {surf}; color: {text}; border: none;
}}
QFileDialog QFrame {{ background: {surf}; }}
QFileDialog QLabel {{ color: {text}; }}
QFileDialog QToolBar {{ background: {surf}; border: none; }}
QFileDialog QToolButton {{ background: transparent; color: {text}; border: none; }}
QFileDialog QComboBox {{
    background: {bg}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 3px 8px;
}}
"""


def build_tab_style(prefs: dict, active: bool) -> str:
    """Build TilePane tab bar stylesheet from app theme prefs."""
    bg     = prefs.get("app_bg",      "#0d1117")
    surf   = prefs.get("app_surface", "#161b22")
    border = prefs.get("app_border",  "#21262d")
    dim    = prefs.get("app_dim",     "#8b949e")
    accent = prefs.get("app_accent",  "#58a6ff")
    hover  = prefs.get("app_hover",   "#1c2128")
    text   = prefs.get("app_text",    "#c9d1d9")

    if active:
        return f"""
QTabWidget::pane{{border:none;background:{bg};}}
QTabBar{{background:{surf};border-bottom:2px solid {accent};}}
QTabBar::tab{{background:{surf};color:{dim};padding:6px 14px;
    border:none;border-right:1px solid {border};min-width:110px;font-size:12px;}}
QTabBar::tab:selected{{background:{bg};color:{accent};border-bottom:2px solid {accent};}}
QTabBar::tab:hover{{background:{hover};color:{text};}}
"""
    else:
        return f"""
QTabWidget::pane{{border:none;background:{bg};}}
QTabBar{{background:{bg};border-bottom:1px solid {border};}}
QTabBar::tab{{background:{bg};color:{dim};padding:6px 14px;
    border:none;border-right:1px solid {surf};min-width:110px;font-size:12px;}}
QTabBar::tab:selected{{background:{surf};color:{dim};border-bottom:1px solid {border};}}
QTabBar::tab:hover{{background:{surf};color:{text};}}
"""



# ── App-level stylesheet themes ───────────────────────────────────────────────

APP_THEMES = {
    "Dark (Default)": {
        "app_bg":"#0d1117","app_surface":"#161b22","app_border":"#21262d",
        "app_text":"#c9d1d9","app_dim":"#8b949e","app_accent":"#58a6ff","app_hover":"#1c2128",
    },
    "Dracula": {
        "app_bg":"#282a36","app_surface":"#343746","app_border":"#44475a",
        "app_text":"#f8f8f2","app_dim":"#6272a4","app_accent":"#bd93f9","app_hover":"#44475a",
    },
    "Monokai": {
        "app_bg":"#272822","app_surface":"#3e3d32","app_border":"#49483e",
        "app_text":"#f8f8f2","app_dim":"#75715e","app_accent":"#a6e22e","app_hover":"#49483e",
    },
    "One Dark": {
        "app_bg":"#282c34","app_surface":"#21252b","app_border":"#181a1f",
        "app_text":"#abb2bf","app_dim":"#5c6370","app_accent":"#61afef","app_hover":"#2c313a",
    },
    "Tokyo Night": {
        "app_bg":"#1a1b26","app_surface":"#24283b","app_border":"#292e42",
        "app_text":"#c0caf5","app_dim":"#565f89","app_accent":"#7aa2f7","app_hover":"#2f3549",
    },
    "Catppuccin Mocha": {
        "app_bg":"#1e1e2e","app_surface":"#313244","app_border":"#45475a",
        "app_text":"#cdd6f4","app_dim":"#6c7086","app_accent":"#cba6f7","app_hover":"#45475a",
    },
    "Gruvbox Dark": {
        "app_bg":"#1d2021","app_surface":"#282828","app_border":"#3c3836",
        "app_text":"#ebdbb2","app_dim":"#928374","app_accent":"#fabd2f","app_hover":"#3c3836",
    },
    "Nord": {
        "app_bg":"#2e3440","app_surface":"#3b4252","app_border":"#434c5e",
        "app_text":"#eceff4","app_dim":"#d8dee9","app_accent":"#88c0d0","app_hover":"#434c5e",
    },
    "Solarized Dark": {
        "app_bg":"#002b36","app_surface":"#073642","app_border":"#0d3d4d",
        "app_text":"#839496","app_dim":"#586e75","app_accent":"#268bd2","app_hover":"#0d3d4d",
    },
    "Midnight": {
        "app_bg":"#000000","app_surface":"#0a0a0a","app_border":"#003b00",
        "app_text":"#00ff41","app_dim":"#007a1f","app_accent":"#00ff41","app_hover":"#001a00",
    },
    "Light": {
        "app_bg":"#f6f8fa","app_surface":"#eaeef2","app_border":"#d0d7de",
        "app_text":"#1f2328","app_dim":"#57606a","app_accent":"#0969da","app_hover":"#d8dee4",
    },
    "Solarized Light": {
        "app_bg":"#fdf6e3","app_surface":"#eee8d5","app_border":"#d8d0c0",
        "app_text":"#657b83","app_dim":"#93a1a1","app_accent":"#268bd2","app_hover":"#e8dfc8",
    },
    "Catppuccin Latte": {
        "app_bg":"#eff1f5","app_surface":"#e6e9ef","app_border":"#ccd0da",
        "app_text":"#4c4f69","app_dim":"#8c8fa1","app_accent":"#8839ef","app_hover":"#dce0e8",
    },
}


def build_app_stylesheet(prefs: dict) -> str:
    """
    App chrome stylesheet — applied to QMainWindow only.
    Scoped to named widgets to avoid breaking dialogs or TilePane.
    Terminal color keys (background/foreground/etc.) are never used here.
    """
    bg     = prefs.get("app_bg",      "#0d1117")
    surf   = prefs.get("app_surface", "#161b22")
    border = prefs.get("app_border",  "#21262d")
    text   = prefs.get("app_text",    "#c9d1d9")
    dim    = prefs.get("app_dim",     "#8b949e")
    accent = prefs.get("app_accent",  "#58a6ff")
    hover  = prefs.get("app_hover",   "#1c2128")
    return f"""
QMainWindow {{ background: {bg}; color: {text}; }}
QMenuBar {{ background: {surf}; color: {text}; border-bottom: 1px solid {border}; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; color: {text}; }}
QMenuBar::item:selected {{ background: {hover}; color: {accent}; }}
QMenu {{ background: {surf}; color: {text}; border: 1px solid {border};
         border-radius: 4px; padding: 4px; }}
QMenu::item {{ padding: 5px 20px; border-radius: 3px; color: {text}; }}
QMenu::item:selected {{ background: {hover}; color: {accent}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 3px 8px; }}
QToolBar {{ background: {surf}; border-bottom: 1px solid {border};
            spacing: 4px; padding: 3px 6px; }}
QToolBar QToolButton {{ background: transparent; color: {text};
               border: 1px solid transparent; border-radius: 4px; padding: 3px 10px; }}
QToolBar QToolButton:hover {{ background: {hover}; color: {accent}; border-color: {border}; }}
QStatusBar {{ background: {surf}; color: {dim}; border-top: 1px solid {border}; }}
QStatusBar QLabel {{ color: {dim}; background: transparent; }}
QTreeView, QTreeWidget {{ background: {bg}; color: {text}; border: none;
                          alternate-background-color: {bg}; }}
QTreeView::item, QTreeWidget::item {{ padding: 3px 4px; border-radius: 3px; }}
QTreeView::item:selected, QTreeWidget::item:selected {{
    background: {hover}; color: {accent}; }}
QTreeView::item:hover:!selected, QTreeWidget::item:hover:!selected {{ background: {hover}; }}
QTreeView::branch, QTreeWidget::branch {{ background: {bg}; }}
QHeaderView {{ background: {surf}; border: none; }}
QHeaderView::section {{ background: {surf}; color: {accent};
    border: none; border-bottom: 1px solid {border};
    padding: 4px 8px; font-weight: bold; font-size: 11px; letter-spacing: 1px; }}
QFrame#broadcast_bar {{ background: {surf}; border-top: 1px solid {border}; }}
QLineEdit#cmd_input {{
    background: {bg}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 5px 10px; font-size: 13px; font-family: Monospace;
}}
QLineEdit#cmd_input:focus {{ border-color: {accent}; }}
QPushButton#targets_btn {{
    background: {hover}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 5px 12px;
}}
QPushButton#targets_btn:hover {{ background: {surf}; }}
QLineEdit#search {{
    background: {surf}; color: {text}; border: 1px solid {border};
    border-radius: 4px; padding: 4px 8px; font-size: 12px;
}}
QLineEdit#search:focus {{ border-color: {accent}; }}
QSplitter::handle {{ background: {border}; }}
/* ── Broadcast bar buttons ───────────────────────────────────────────── */
QPushButton#run_btn {{
    background: #238636; color: white; border: none;
    border-radius: 4px; padding: 5px 18px; font-size: 12px;
}}
QPushButton#run_btn:hover {{ background: #2ea043; }}
QPushButton#run_btn:disabled {{ background: #1a3326; color: #4a7a5a; }}
QPushButton#script_btn {{
    background: {accent}; color: white; border: none;
    border-radius: 4px; padding: 5px 14px; font-size: 12px;
}}
QPushButton#script_btn:hover {{ background: {hover}; color: {accent}; border: 1px solid {accent}; }}
QPushButton#script_btn:disabled {{ background: {hover}; color: {dim}; }}
QScrollBar:vertical {{ background: {bg}; width: 8px; border: none; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {dim}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {bg}; height: 8px; border: none; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 4px; min-width: 20px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


