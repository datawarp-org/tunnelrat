"""
terminal_tab.py — QWebEngineView terminal widget for TunnelRAT.

Keyboard: xterm.js handles all keyboard input natively (disableStdin NOT set).
          The page is served from a real http:// URL which gives it a proper
          origin — this is what makes QWebEngineView keyboard focus work.

No Qt keyPressEvent intercept needed or wanted: X11 WM gives keyboard focus
to Chromium's native X11 window when clicked, not to the Qt parent widget.
Trying to intercept in Qt is fighting the X11 WM and will always lose.

Detach/redock: accepts optional session_id so a fresh widget in a new window
can reuse an existing held SSH channel (bridge replays buffered output).
"""
from __future__ import annotations
import logging
import uuid

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

from session_model import Session
from ssh_bridge import SSHBridge

log = logging.getLogger(__name__)


class TerminalWidget(QWidget):
    status_changed  = pyqtSignal(str)
    terminal_closed = pyqtSignal()

    def __init__(self, session: Session,
                 session_id: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.session     = session
        self._session_id = session_id or str(uuid.uuid4())
        self._terminated = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = QWebEngineView(self)
        s = self._view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled,               True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,    True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled,           False)

        # Do NOT intercept drops — TilePane needs them via grabMouse
        self._view.setAcceptDrops(False)
        self.setAcceptDrops(False)

        layout.addWidget(self._view)

        bridge = SSHBridge.instance()
        bridge.register(self._session_id, session)
        bridge.session_status.connect(self._on_bridge_status)
        bridge.tab_title_changed.connect(self._on_tab_title)

        self._load_page()
        self.status_changed.emit("connecting")
        log.debug("TerminalWidget: %s  sid=%s", session.host, self._session_id[:8])

    def _on_tab_title(self, sid: str, title: str):
        """Update tab label when remote shell sends OSC title sequence."""
        if sid != self._session_id:
            return
        # Walk up to find the containing TilePane and update the tab label
        parent = self.parent()
        while parent:
            from tile_pane import TilePane
            if isinstance(parent, TilePane):
                idx = parent.indexOf(self)
                if idx >= 0:
                    parent.setTabText(idx, title)
                break
            parent = parent.parent()

    def _load_page(self):
        b = SSHBridge.instance()
        url = (f"http://127.0.0.1:{b.http_port}/"
               f"?sid={self._session_id}&port={b.port}")
        self._view.setUrl(QUrl(url))

    def apply_prefs(self, prefs: dict):
        """Hot-reload terminal colors/font without reconnecting."""
        import json
        from ssh_bridge import _build_xterm_theme_dict
        fallback = "JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace"
        font_fam = prefs.get("font_family", fallback)
        if "," not in font_fam:
            font_fam = font_fam + "," + fallback
        p = {
            "theme":      _build_xterm_theme_dict(prefs),
            "fontFamily": font_fam,
            "fontSize":   int(prefs.get("font_size", 13)),
            "lineHeight": round(float(prefs.get("line_height", 1.2)), 2),
        }
        pj = json.dumps(p)
        self._view.page().runJavaScript(f"""
            if(typeof term !== 'undefined') {{
                var p = {pj};
                term.options.theme      = p.theme;
                term.options.fontFamily = p.fontFamily;
                term.options.fontSize   = p.fontSize;
                term.options.lineHeight = p.lineHeight;
            }}
        """)

    def _on_bridge_status(self, sid: str, status: str):
        if sid != self._session_id:
            return
        if status == "connected":
            self.status_changed.emit("connected")
        elif status in ("failed", "closed"):
            self.status_changed.emit("disconnected")
            self.terminal_closed.emit()

    def prepare_for_detach(self):
        SSHBridge.instance().hold_session(self._session_id)

    def send_command(self, command: str):
        if not self._terminated:
            SSHBridge.instance().send_data(self._session_id, command + "\n")

    def reconnect(self):
        if self._terminated:
            return
        b = SSHBridge.instance()
        b.unregister(self._session_id)
        self._session_id = str(uuid.uuid4())
        b.register(self._session_id, self.session)
        b.session_status.connect(self._on_bridge_status)
        self._load_page()
        self.status_changed.emit("connecting")

    def terminate(self):
        if self._terminated:
            return
        self._terminated = True
        SSHBridge.instance().unregister(self._session_id)

    def closeEvent(self, event):
        self.terminate()
        super().closeEvent(event)
