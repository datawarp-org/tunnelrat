"""
detached_window.py — floating terminal window (double-click a tab).

Creates a FRESH TerminalWidget with the SAME session_id so the bridge
finds the held channel and replays buffered output immediately.
No reparenting of QWebEngineView — create fresh, reuse SSH channel.
"""
from __future__ import annotations
import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QToolBar, QWidget, QVBoxLayout

from session_model import Session

log = logging.getLogger(__name__)


class DetachedWindow(QMainWindow):
    closing          = pyqtSignal()
    redock_requested = pyqtSignal(object, str)   # Session, session_id

    def __init__(self, session: Session, session_id: str, parent=None):
        super().__init__(parent)
        from terminal_tab import TerminalWidget
        from ssh_bridge import SSHBridge

        self._session    = session
        self._session_id = session_id
        self._redocking  = False

        self.setWindowTitle(f"TunnelRAT — {session.display_name()}")
        self.resize(1060, 680)
        self.setStyleSheet("""
            QMainWindow,QWidget{background:#0d1117;}
            QToolBar{background:#161b22;border-bottom:1px solid #21262d;
                     spacing:4px;padding:3px 6px;}
            QToolButton{background:transparent;color:#8b949e;
                border:1px solid transparent;border-radius:4px;
                padding:3px 10px;font-size:12px;}
            QToolButton:hover{background:#21262d;color:#c9d1d9;border-color:#30363d;}
        """)

        tb = QToolBar("Controls", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        act = QAction("↩  Re-dock as tab", self)
        act.setToolTip("Return this terminal to the main window")
        act.triggered.connect(self._on_redock)
        tb.addAction(act)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Fresh widget, same session_id → bridge finds held channel, replays output
        self._terminal = TerminalWidget(session, session_id=session_id)
        layout.addWidget(self._terminal)
        log.debug("DetachedWindow: %s  sid=%s", session.display_name(), session_id[:8])

    def _on_redock(self):
        self._redocking = True
        sid = self._terminal._session_id
        # Hold channel so it survives between this window closing and main window opening
        from ssh_bridge import SSHBridge
        SSHBridge.instance().hold_session(sid)
        self._terminal._terminated = True   # prevent bridge unregister
        self._terminal.deleteLater()
        self.redock_requested.emit(self._session, sid)
        self.closing.emit()
        self.close()

    def closeEvent(self, event):
        if not self._redocking:
            self._terminal.terminate()
            self._terminal.deleteLater()
        self.closing.emit()
        super().closeEvent(event)
