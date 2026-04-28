"""
broadcast_panel.py — slim single-row broadcast toolbar.

Layout:
  [🎯 Targets (N)] [command input ......................] [▶ Run] [📄 Script…]

Target selection is in a floating popup dialog so it doesn't eat vertical space.
Commands are sent directly to existing open SSH channels via SSHBridge — no new
connections, output appears in each terminal tab.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from session_model import Session

# Layout only — no background/text colors.
# Colors come from the app theme stylesheet on QMainWindow.
TOOLBAR_STYLE = """
QFrame#broadcast_bar {
    min-height: 44px;
    max-height: 44px;
}
QLineEdit#cmd_input {
    border: 1px solid #30363d; border-radius: 4px;
    padding: 5px 10px; font-family: Monospace; font-size: 13px;
}
QPushButton#targets_btn {
    border: 1px solid #30363d; border-radius: 4px;
    padding: 5px 12px; font-size: 12px; min-width: 90px;
}
QPushButton#run_btn {
    background: #238636; color: white;
    border: none; border-radius: 4px;
    padding: 5px 18px; font-size: 12px;
}
QPushButton#run_btn:hover { background: #2ea043; }
QPushButton#run_btn:disabled { background: #1a3326; color: #4a7a5a; }
QPushButton#script_btn {
    background: #1f6feb; color: white;
    border: none; border-radius: 4px;
    padding: 5px 14px; font-size: 12px;
}
QPushButton#script_btn:hover { background: #388bfd; }
QPushButton#script_btn:disabled { background: #0d2347; color: #3a5a8a; }
"""

POPUP_STYLE = """
QDialog {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
}
QLabel { color: #8b949e; font-size: 11px; font-weight: bold; letter-spacing: 1px; }
QListWidget {
    background: #0d1117; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    font-size: 12px; outline: none;
}
QListWidget::item { padding: 4px 8px; border-radius: 3px; }
QListWidget::item:hover { background: #21262d; }
QPushButton {
    background: #21262d; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    padding: 3px 10px; font-size: 11px;
}
QPushButton:hover { background: #30363d; }
"""


class _TargetsPopup(QDialog):
    """
    Small frameless popup showing session checkboxes.
    Positioned below the Targets button, closes on focus loss.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent,
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(POPUP_STYLE)
        self.setMinimumWidth(240)
        self.setMaximumHeight(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("TARGET SESSIONS"))
        hdr.addStretch()
        ab = QPushButton("All");  ab.setMaximumWidth(38)
        nb = QPushButton("None"); nb.setMaximumWidth(44)
        ab.clicked.connect(self._select_all)
        nb.clicked.connect(self._select_none)
        hdr.addWidget(ab); hdr.addWidget(nb)
        layout.addLayout(hdr)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._list)

    # ── Population ────────────────────────────────────────────────────────────

    def populate(self, terminals: list, checked_ids: set[str]):
        from collections import Counter
        name_count = Counter(w.session.display_name() for w in terminals)
        name_seen: Counter = Counter()

        self._list.blockSignals(True)
        self._list.clear()
        for w in terminals:
            name = w.session.display_name()
            if name_count[name] > 1:
                name_seen[name] += 1
                label = f"  {name} ({name_seen[name]})"
            else:
                label = f"  {name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, w._session_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = (Qt.CheckState.Checked
                     if (not checked_ids or w._session_id in checked_ids)
                     else Qt.CheckState.Unchecked)
            item.setCheckState(state)
            self._list.addItem(item)

        # Auto-size height to content
        row_h = self._list.sizeHintForRow(0) if self._list.count() else 22
        h = min(row_h * self._list.count() + 16, 260)
        self._list.setFixedHeight(max(h, 40))
        self.adjustSize()
        self._list.blockSignals(False)

    def checked_ids(self) -> set[str]:
        ids = set()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.add(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def _select_all(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Unchecked)


# ── Main panel ────────────────────────────────────────────────────────────────

class _BroadcastInput(QLineEdit):
    """Broadcast command input — intercepts Ctrl+C/Z/D/backslash to send
    POSIX signal bytes to all targeted sessions immediately."""
    signal_key_pressed = pyqtSignal(str)  # raw byte string e.g. '\x03'

    def keyPressEvent(self, ev):
        from PyQt6.QtCore import Qt as _Qt
        if ev.modifiers() == _Qt.KeyboardModifier.ControlModifier:
            mapping = {
                _Qt.Key.Key_C: '\x03',   # SIGINT
                _Qt.Key.Key_Z: '\x1a',   # SIGTSTP
                _Qt.Key.Key_D: '\x04',   # EOF
                _Qt.Key.Key_Backslash: '\x1c',  # SIGQUIT (Ctrl+\\)
                _Qt.Key.Key_L: '\x0c',   # clear
                _Qt.Key.Key_U: '\x15',   # kill line
            }
            byte = mapping.get(ev.key())
            if byte:
                self.signal_key_pressed.emit(byte)
                return   # don't pass to QLineEdit (would copy/etc)
        super().keyPressEvent(ev)


class BroadcastPanel(QFrame):
    """Single-row broadcast toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("broadcast_bar")
        self.setFixedHeight(44)

        self._terminals: list = []          # TerminalWidget list
        self._checked_ids: set[str] = set() # persists across popup opens
        self._popup: _TargetsPopup | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # Targets button
        self._targets_btn = QPushButton("🎯  Targets (0)")
        self._targets_btn.setObjectName("targets_btn")
        self._targets_btn.clicked.connect(self._open_targets)
        layout.addWidget(self._targets_btn)

        # Command input
        self._cmd = _BroadcastInput()
        self._cmd.setObjectName("cmd_input")
        self._cmd.setPlaceholderText("Command to broadcast to selected sessions…")
        self._cmd.returnPressed.connect(self._on_run)
        self._cmd.signal_key_pressed.connect(self._on_signal_key)
        layout.addWidget(self._cmd, stretch=1)

        # Run
        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setObjectName("run_btn")
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        layout.addWidget(self._run_btn)

        # Script
        self._script_btn = QPushButton("📄  Script…")
        self._script_btn.setObjectName("script_btn")
        self._script_btn.setEnabled(False)
        self._script_btn.clicked.connect(self._on_script)
        layout.addWidget(self._script_btn)

        self._paste_btn = QPushButton("📋  Paste…")
        self._paste_btn.setObjectName("script_btn")  # reuse style
        self._paste_btn.setEnabled(False)
        self._paste_btn.setToolTip("Paste or type a script to run on selected sessions")
        self._paste_btn.clicked.connect(self._on_paste_script)
        layout.addWidget(self._paste_btn)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_open_sessions(self, terminals: list):
        """Called by main_window whenever open tabs change."""
        self._terminals = terminals
        open_ids = {w._session_id for w in terminals}
        # Remove ids for sessions that closed
        self._checked_ids &= open_ids
        # Auto-check any brand new sessions
        new_ids = open_ids - self._checked_ids
        # If we had nothing checked or this is first load, check all
        if not self._checked_ids and terminals:
            self._checked_ids = set(open_ids)
        else:
            # New terminals added → check them by default
            self._checked_ids |= new_ids
        self._refresh_button()

    def checked_sessions_ids(self) -> list[str]:
        return list(self._checked_ids)

    # ── Targets popup ─────────────────────────────────────────────────────────

    def _open_targets(self):
        if not self._terminals:
            return

        popup = _TargetsPopup(self)
        popup.populate(self._terminals, self._checked_ids)

        # Position popup above the Targets button
        btn_global = self._targets_btn.mapToGlobal(QPoint(0, 0))
        popup.move(btn_global.x(),
                   btn_global.y() - popup.sizeHint().height() - 4)
        popup.exec()

        # Persist checked state after popup closes
        self._checked_ids = popup.checked_ids()
        self._refresh_button()

    def _refresh_button(self):
        count = len(self._checked_ids)
        total = len(self._terminals)
        has   = count > 0
        self._targets_btn.setText(f"🎯  Targets ({count}/{total})")
        self._run_btn.setEnabled(has)
        self._script_btn.setEnabled(has)
        self._paste_btn.setEnabled(has)

    # ── Execution ─────────────────────────────────────────────────────────────

    def _on_signal_key(self, byte: str):
        """Send a signal byte (Ctrl+C/Z/D etc.) to all targeted sessions.
        This fires immediately on keypress — no Enter needed — so you can
        mass-SIGINT a runaway command across all sessions instantly."""
        from ssh_bridge import SSHBridge
        bridge = SSHBridge.instance()
        for sid in self._checked_ids:
            try:
                bridge.send_data(sid, byte)
            except Exception:
                pass

    def _toggle_mask(self, checked: bool):
        """Mask broadcast input with * (like sudo password entry)."""
        from PyQt6.QtWidgets import QLineEdit as _QLE
        mode = _QLE.EchoMode.Password if checked else _QLE.EchoMode.Normal
        self._cmd.setEchoMode(mode)
        self._mask_btn.setText("🔒" if checked else "👁")
        self._mask_btn.setToolTip(
            "Command mask ON — input hidden (Ctrl+Shift+8)" if checked
            else "Toggle command mask (Ctrl+Shift+8)")

    def toggle_mask_hotkey(self):
        """Called by Ctrl+Shift+8 hotkey."""
        self._mask_btn.setChecked(not self._mask_btn.isChecked())
        self._toggle_mask(self._mask_btn.isChecked())

    def _on_run(self):
        cmd = self._cmd.text()  # don't strip — spaces/newlines are valid commands
        if cmd == "":
            return
        self._send(cmd)
        self._cmd.clear()

    def _on_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Script", "", "Shell Scripts (*.sh);;All Files (*)")
        if not path:
            return
        try:
            with open(path) as f:
                lines = [ln.rstrip() for ln in f if ln.strip()]
        except Exception as e:
            QMessageBox.critical(self, "Script Error", f"Cannot read file:\n{e}")
            return
        for ln in lines:
            self._send(ln)

    def _on_paste_script(self):
        """Open a dialog to paste/type a script and run on selected sessions."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Paste Script")
        dlg.setMinimumSize(600, 400)
        dlg.setStyleSheet("""
            QDialog { background: #0d1117; }
            QLabel { color: #8b949e; font-size: 11px; }
            QPlainTextEdit {
                background: #161b22; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px;
                font-family: Monospace; font-size: 12px;
                padding: 6px;
            }
            QPushButton {
                background: #238636; color: white;
                border: none; border-radius: 4px;
                padding: 6px 18px; font-size: 12px;
            }
            QPushButton:hover { background: #2ea043; }
            QPushButton[flat="true"] {
                background: #21262d; color: #c9d1d9;
                border: 1px solid #30363d;
            }
            QPushButton[flat="true"]:hover { background: #30363d; }
        """)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "Paste or type your script below. Each line will be sent to selected sessions."))

        editor = QPlainTextEdit()
        editor.setPlaceholderText("#!/bin/bash\n# paste your script here…")
        layout.addWidget(editor)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("flat", True)
        cancel_btn.clicked.connect(dlg.reject)
        run_btn = QPushButton("▶  Run on Selected")
        run_btn.clicked.connect(dlg.accept)
        btns.addWidget(cancel_btn)
        btns.addWidget(run_btn)
        layout.addLayout(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        script = editor.toPlainText()
        lines = [ln.rstrip() for ln in script.splitlines() if ln.strip()]
        if not lines:
            return
        for ln in lines:
            self._send(ln)

    def _send(self, command: str):
        from ssh_bridge import SSHBridge
        bridge = SSHBridge.instance()
        for sid in self._checked_ids:
            bridge.send_data(sid, command + "\n")
