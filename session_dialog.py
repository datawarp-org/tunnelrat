import logging
import shutil
import subprocess
import uuid
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QComboBox, QPushButton,
    QLabel, QFileDialog, QGroupBox, QStackedWidget,
    QWidget, QTextEdit, QMessageBox, QCheckBox, QInputDialog
)
from PyQt6.QtCore import Qt
from session_model import Session

log = logging.getLogger(__name__)

DIALOG_STYLE = """
QDialog { background: #161b22; color: #c9d1d9; }
QLabel  { color: #8b949e; font-size: 12px; }
QLineEdit, QSpinBox, QComboBox {
    background: #0d1117; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    padding: 5px 8px; font-size: 13px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #58a6ff; }
QTextEdit {
    background: #0d1117; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px;
    font-size: 12px; padding: 4px;
}
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
QPushButton#ok_btn { background: #1f6feb; color: white; border-color: #1f6feb; }
QPushButton#ok_btn:hover { background: #388bfd; }
QCheckBox { color: #8b949e; font-size: 12px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #30363d; border-radius: 3px; background: #0d1117; }
QCheckBox::indicator:checked { background: #1f6feb; border-color: #1f6feb; }
"""

PPK_HINT_STYLE = ("color:#e3b341;font-size:11px;padding:4px 6px;"
                  "background:#1c1400;border-radius:3px;border:1px solid #5a4000;")
BLUE_HINT_STYLE = ("color:#58a6ff;font-size:11px;padding:4px 6px;"
                   "background:#0d2137;border-radius:3px;border:1px solid #1f3a5f;")


def _browse_row(placeholder: str) -> tuple[QWidget, QLineEdit, QPushButton]:
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    btn = QPushButton("Browse…")
    btn.setMaximumWidth(80)
    row.addWidget(edit)
    row.addWidget(btn)
    return w, edit, btn


class SessionDialog(QDialog):
    def __init__(self, session: Session | None = None, parent=None):
        super().__init__(parent)
        from preferences_dialog import build_dialog_stylesheet, load_prefs
        self.setStyleSheet(build_dialog_stylesheet(load_prefs()))
        self._edit_session = session
        self.setWindowTitle("Edit Session" if session else "New Session")
        self.setMinimumWidth(530)
        self._build_ui()
        if session:
            self._populate(session)

    def set_group(self, group: str):
        self._group_edit.setText(group)

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setSpacing(4)
        self._root.setContentsMargins(12, 12, 12, 12)

        # ── Connection ──────────────────────────────────────────────────
        conn_box = QGroupBox("Connection")
        self._conn_form = QFormLayout(conn_box)
        self._conn_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._conn_form.setSpacing(8)
        self._conn_form.setContentsMargins(10, 10, 10, 10)

        self._name_edit = QLineEdit(); self._name_edit.setPlaceholderText("web-prod-01")
        self._conn_form.addRow("Name:", self._name_edit)

        self._host_edit = QLineEdit(); self._host_edit.setPlaceholderText("192.168.1.10 or hostname.example.com")
        self._conn_form.addRow("Host:", self._host_edit)

        self._port_spin = QSpinBox(); self._port_spin.setRange(1, 65535); self._port_spin.setValue(22)
        self._conn_form.addRow("Port:", self._port_spin)

        self._user_edit = QLineEdit(); self._user_edit.setPlaceholderText("root")
        self._conn_form.addRow("Username:", self._user_edit)

        self._group_edit = QLineEdit(); self._group_edit.setText("Default")
        self._conn_form.addRow("Group:", self._group_edit)

        self._root.addWidget(conn_box)

        # ── Authentication ───────────────────────────────────────────────
        auth_box = QGroupBox("Authentication")
        self._auth_vbox = QVBoxLayout(auth_box)
        self._auth_vbox.setSpacing(8)
        self._auth_vbox.setContentsMargins(10, 10, 10, 10)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Method:"))
        self._auth_combo = QComboBox()
        self._auth_combo.addItems(["SSH Key / Certificate", "Password"])
        type_row.addWidget(self._auth_combo)
        type_row.addStretch()
        self._auth_vbox.addLayout(type_row)

        self._auth_stack = QStackedWidget()

        # Page 0: Key/Cert
        self._key_page = QWidget()
        self._key_form = QFormLayout(self._key_page)
        self._key_form.setSpacing(8)
        self._key_form.setContentsMargins(0, 4, 0, 0)

        key_w, self._key_edit, key_btn = _browse_row("~/.ssh/id_rsa  (blank = ssh-agent)")
        key_btn.clicked.connect(self._browse_key)
        self._conn_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._key_form.addRow("Private Key:", key_w)

        cert_w, self._cert_edit, cert_btn = _browse_row("~/.ssh/id_rsa-cert.pub  (optional)")
        cert_btn.clicked.connect(self._browse_cert)
        self._key_form.addRow("Cert File:", cert_w)

        self._key_hint = QLabel(
            "Select your private key. If a matching -cert.pub sits alongside it, "
            "SSH finds it automatically — only set Cert File if names differ."
        )
        self._key_hint.setStyleSheet(BLUE_HINT_STYLE)
        self._key_hint.setWordWrap(True)
        self._key_form.addRow("", self._key_hint)

        self._ppk_warn = QLabel(
            "⚠  .ppk detected (PuTTY format). Click Convert to create an OpenSSH key."
        )
        self._ppk_warn.setStyleSheet(PPK_HINT_STYLE)
        self._ppk_warn.setWordWrap(True)
        self._ppk_warn.hide()

        ppk_row = QHBoxLayout()
        ppk_row.addWidget(self._ppk_warn)
        self._ppk_convert_btn = QPushButton("Convert…")
        self._ppk_convert_btn.setMaximumWidth(90)
        self._ppk_convert_btn.hide()
        self._ppk_convert_btn.clicked.connect(self._convert_ppk)
        ppk_row.addWidget(self._ppk_convert_btn)
        self._key_form.addRow("", ppk_row)  # type: ignore[arg-type]
        self._key_edit.textChanged.connect(self._on_key_path_changed)
        self._auth_stack.addWidget(self._key_page)

        # Page 1: Password
        self._pw_page = QWidget()
        self._pw_form = QFormLayout(self._pw_page)
        self._pw_form.setSpacing(8)
        self._pw_form.setContentsMargins(0, 4, 0, 0)
        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText("Leave blank to prompt each connection")
        self._pw_form.addRow("Password:", self._pw_edit)
        self._pw_warn = QLabel("🔒  Password is encrypted before being stored.")
        self._pw_warn.setStyleSheet(
            "color:#3fb950;font-size:11px;padding:4px 6px;"
            "background:#0d2a0d;border-radius:3px;border:1px solid #1a4a1a;")
        self._pw_warn.setWordWrap(True)
        self._pw_form.addRow("", self._pw_warn)
        self._auth_stack.addWidget(self._pw_page)

        self._auth_vbox.addWidget(self._auth_stack)
        self._auth_combo.currentIndexChanged.connect(self._on_auth_changed)
        self._root.addWidget(auth_box)

        # ── Advanced ─────────────────────────────────────────────────────
        adv_box = QGroupBox("Advanced (optional)")
        self._adv_form = QFormLayout(adv_box)
        self._adv_form.setSpacing(8)
        self._adv_form.setContentsMargins(10, 10, 10, 10)

        self._jump_edit = QLineEdit()
        self._jump_edit.setPlaceholderText("user@bastion.example.com  or  user@host:port")
        self._adv_form.addRow("Jump Host:", self._jump_edit)

        self._keepalive_spin = QSpinBox()
        self._keepalive_spin.setRange(0, 3600)
        self._keepalive_spin.setValue(60)
        self._keepalive_spin.setSuffix("  sec  (0 = off)")
        self._adv_form.addRow("Keepalive:", self._keepalive_spin)

        self._extra_edit = QLineEdit()
        self._extra_edit.setPlaceholderText("-o StrictHostKeyChecking=no   -L 8080:localhost:80")
        self._adv_form.addRow("Extra SSH Args:", self._extra_edit)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Optional notes about this server…")
        self._notes_edit.setMaximumHeight(60)
        self._adv_form.addRow("Notes:", self._notes_edit)

        self._root.addWidget(adv_box)

        # ── Buttons ───────────────────────────────────────────────────────
        self._btn_row = QHBoxLayout()
        self._btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton("Save Session")
        self._ok_btn.setObjectName("ok_btn")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_accept)
        self._btn_row.addWidget(cancel_btn)
        self._btn_row.addWidget(self._ok_btn)
        self._root.addLayout(self._btn_row)

    # ------------------------------------------------------------------ #
    def _on_auth_changed(self, index: int):
        self._auth_stack.setCurrentIndex(index)

    def _on_key_path_changed(self, text: str):
        is_ppk = text.lower().endswith(".ppk")
        self._ppk_warn.setVisible(is_ppk)
        self._ppk_convert_btn.setVisible(is_ppk)

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Private Key", str(Path.home() / ".ssh"), "All Files (*)"
        )
        if path:
            self._key_edit.setText(path)
            if not self._cert_edit.text():
                guess = path + "-cert.pub"
                if Path(guess).exists():
                    self._cert_edit.setText(guess)

    def _browse_cert(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Certificate", str(Path.home() / ".ssh"),
            "Cert Files (*-cert.pub);;All Files (*)"
        )
        if path:
            self._cert_edit.setText(path)

    def _convert_ppk(self):
        """Convert a .ppk file to OpenSSH format using puttygen."""
        ppk_path = self._key_edit.text().strip()
        if not ppk_path:
            return
        puttygen = shutil.which("puttygen")
        if not puttygen:
            QMessageBox.warning(
                self, "puttygen not found",
                "Install PuTTY tools first:\n\n  sudo dnf install putty\n\n"
                "Then try again."
            )
            return
        out_path = ppk_path.replace(".ppk", "")
        if Path(out_path).exists():
            r = QMessageBox.question(
                self, "File exists",
                f"{out_path} already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r != QMessageBox.StandardButton.Yes:
                return

        # Detect passphrase protection by reading the PPK file header —
        # never run puttygen blindly as it may interact with /dev/tty
        # directly and corrupt the terminal's echo state.
        passphrase = ""
        needs_passphrase = self._ppk_is_encrypted(ppk_path)

        if needs_passphrase:
            pw, ok = QInputDialog.getText(
                self,
                "PPK Passphrase",
                f"The key file is passphrase-protected.\n"
                f"Enter the passphrase for:\n{ppk_path}",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return
            passphrase = pw

        import tempfile, os
        try:
            cmd = [puttygen, ppk_path, "-O", "private-openssh-new", "-o", out_path]
            tmp_file = None
            if passphrase:
                # puttygen --old-passphrase expects a FILE, not a string
                tmp_fd, tmp_path = tempfile.mkstemp(prefix='tr_ppk_', suffix='.tmp')
                try:
                    os.write(tmp_fd, passphrase.encode())
                finally:
                    os.close(tmp_fd)
                tmp_file = tmp_path
                cmd += ["--old-passphrase", tmp_path]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            if tmp_file:
                try: os.unlink(tmp_file)
                except Exception: pass
            if result.returncode == 0 and Path(out_path).exists():
                Path(out_path).chmod(0o600)
                self._key_edit.setText(out_path)
                QMessageBox.information(
                    self, "Conversion successful",
                    f"OpenSSH key saved to:\n{out_path}"
                )
                log.debug("PPK converted: %s → %s", ppk_path, out_path)
            else:
                err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                QMessageBox.critical(
                    self, "Conversion failed",
                    f"puttygen error:\n{err}\n\n"
                    "If the passphrase was wrong, try again."
                )
        except subprocess.TimeoutExpired:
            QMessageBox.critical(
                self, "Conversion failed",
                "puttygen timed out. The passphrase may be incorrect."
            )
        except Exception as e:
            QMessageBox.critical(self, "Conversion failed", str(e))

    @staticmethod
    def _ppk_is_encrypted(ppk_path: str) -> bool:
        """Read PPK file header to check for encryption without running puttygen."""
        try:
            with open(ppk_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('Encryption:'):
                        return 'none' not in line.lower()
                    # Only check first 20 lines
                    if f.tell() > 2048:
                        break
            return False
        except Exception:
            return True  # Assume encrypted if unreadable

    def _on_accept(self):
        if not self._host_edit.text().strip():
            self._host_edit.setStyleSheet("border: 1px solid #f85149;")
            self._host_edit.setFocus()
            return
        self.accept()

    def _populate(self, s: Session):
        self._name_edit.setText(s.name)
        self._host_edit.setText(s.host)
        self._port_spin.setValue(s.port)
        self._user_edit.setText(s.username)
        self._group_edit.setText(s.group)
        self._jump_edit.setText(s.jump_host)
        self._keepalive_spin.setValue(s.keepalive)
        self._extra_edit.setText(s.extra_args)
        self._notes_edit.setPlainText(s.notes)
        if s.auth_type == "password":
            self._auth_combo.setCurrentIndex(1)
            self._pw_edit.setText(s.password)
        else:
            self._auth_combo.setCurrentIndex(0)
            self._key_edit.setText(s.key_file)
            self._cert_edit.setText(s.cert_file)

    def get_session(self) -> Session:
        auth_idx = self._auth_combo.currentIndex()
        sid = self._edit_session.id if self._edit_session else str(uuid.uuid4())
        return Session(
            id           = sid,
            name         = self._name_edit.text().strip() or self._host_edit.text().strip(),
            host         = self._host_edit.text().strip(),
            port         = self._port_spin.value(),
            username     = self._user_edit.text().strip(),
            group        = self._group_edit.text().strip() or "Default",
            auth_type    = "key" if auth_idx == 0 else "password",
            key_file     = self._key_edit.text().strip() if auth_idx == 0 else "",
            cert_file    = self._cert_edit.text().strip() if auth_idx == 0 else "",
            password     = self._pw_edit.text() if auth_idx == 1 else "",
            jump_host    = self._jump_edit.text().strip(),
            keepalive    = self._keepalive_spin.value(),
            extra_args   = self._extra_edit.text().strip(),
            notes        = self._notes_edit.toPlainText().strip(),
            last_connected = self._edit_session.last_connected if self._edit_session else "",
        )
