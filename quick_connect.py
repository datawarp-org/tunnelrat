"""Quick Connect dialog — connect to a host without saving a session."""
import uuid
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel,
    QGroupBox, QFileDialog, QWidget, QComboBox
)
from PyQt6.QtCore import Qt
from session_model import Session

STYLE = """
QDialog { background: #161b22; color: #c9d1d9; }
QLabel  { color: #8b949e; font-size: 12px; }
QLineEdit, QSpinBox, QComboBox {
    background: #0d1117; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    padding: 5px 8px; font-size: 13px;
}
QLineEdit:focus, QSpinBox:focus { border-color: #58a6ff; }
QGroupBox {
    color: #8b949e; border: 1px solid #30363d;
    border-radius: 6px; margin-top: 12px; padding-top: 12px;
    font-size: 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton {
    background: #21262d; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    padding: 5px 14px; font-size: 12px;
}
QPushButton:hover { background: #30363d; }
QPushButton#connect_btn { background: #238636; color: white; border-color: #238636; }
QPushButton#connect_btn:hover { background: #2ea043; }
"""


class QuickConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from preferences_dialog import build_dialog_stylesheet, load_prefs
        self.setStyleSheet(build_dialog_stylesheet(load_prefs()))
        self.setWindowTitle("Quick Connect")
        self.setMinimumWidth(420)
        self.setStyleSheet(STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(12, 12, 12, 12)

        box = QGroupBox("Connection")
        self._form = QFormLayout(box)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form.setSpacing(8)
        self._form.setContentsMargins(10, 10, 10, 10)

        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("192.168.1.10  or  user@hostname")
        self._form.addRow("Host:", self._host_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(22)
        self._form.addRow("Port:", self._port_spin)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("root")
        self._form.addRow("Username:", self._user_edit)

        # Key row
        key_w = QWidget()
        key_row = QHBoxLayout(key_w)
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(4)
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("~/.ssh/id_rsa  (blank = ssh-agent)")
        browse_btn = QPushButton("Browse…")
        browse_btn.setMaximumWidth(80)
        browse_btn.clicked.connect(self._browse_key)
        key_row.addWidget(self._key_edit)
        key_row.addWidget(browse_btn)
        self._form.addRow("Key File:", key_w)

        root.addWidget(box)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        connect_btn = QPushButton("⚡  Connect")
        connect_btn.setObjectName("connect_btn")
        connect_btn.setDefault(True)
        connect_btn.clicked.connect(self._on_connect)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(connect_btn)
        root.addLayout(btn_row)

        self._host_edit.setFocus()

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Key", str(Path.home() / ".ssh"), "All Files (*)"
        )
        if path:
            self._key_edit.setText(path)

    def _on_connect(self):
        host_raw = self._host_edit.text().strip()
        if not host_raw:
            self._host_edit.setStyleSheet("border:1px solid #f85149;")
            return
        self.accept()

    def get_session(self) -> Session:
        host_raw = self._host_edit.text().strip()
        username = self._user_edit.text().strip()
        # Allow  user@host  shorthand
        if "@" in host_raw and not username:
            username, host_raw = host_raw.rsplit("@", 1)
        return Session(
            id        = str(uuid.uuid4()),
            name      = f"{username}@{host_raw}" if username else host_raw,
            host      = host_raw,
            port      = self._port_spin.value(),
            username  = username,
            auth_type = "key",
            key_file  = self._key_edit.text().strip(),
            group     = "Quick Connect",
        )
