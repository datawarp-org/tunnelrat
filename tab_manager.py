import logging
from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QSplitter, QVBoxLayout, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from session_model import Session
from terminal_tab import TerminalWidget

log = logging.getLogger(__name__)

# Status dot colours embedded in tab label
STATUS_CONNECTING  = "🟡"
STATUS_CONNECTED   = "🟢"
STATUS_DISCONNECTED= "🔴"


class TabManager(QWidget):
    tab_count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions: dict[str, TerminalWidget] = {}  # id → widget
        self._mode = "tabbed"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.tabCloseRequested.connect(self._close_tab_by_index)
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; background: #0d1117; }
            QTabBar::tab {
                background: #161b22; color: #8b949e;
                padding: 6px 14px; border: none;
                border-right: 1px solid #21262d;
                min-width: 110px; font-size: 12px;
            }
            QTabBar::tab:selected { background: #0d1117; color: #58a6ff; border-bottom: 2px solid #58a6ff; }
            QTabBar::tab:hover { background: #1c2128; color: #c9d1d9; }
        """)

        self._splitter = QSplitter()
        self._splitter.setChildrenCollapsible(False)

        self._stack.addWidget(self._tab_widget)   # 0 = tabbed
        self._stack.addWidget(self._splitter)      # 1 = tiled
        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #
    def open_session(self, session: Session):
        if session.id in self._sessions:
            self._focus_session(session.id)
            return
        widget = TerminalWidget(session)
        widget.terminal_closed.connect(lambda sid=session.id: self._on_terminal_closed(sid))
        widget.status_changed.connect(lambda st, sid=session.id: self._update_tab_status(sid, st))
        self._sessions[session.id] = widget

        label = f"{STATUS_CONNECTING} {session.display_name()}"
        if self._mode == "tabbed":
            idx = self._tab_widget.addTab(widget, label)
            self._tab_widget.setCurrentIndex(idx)
        else:
            self._splitter.addWidget(widget)

        self.tab_count_changed.emit(len(self._sessions))
        log.debug("Opened session %s", session.display_name())

    def close_current(self):
        if self._mode == "tabbed":
            idx = self._tab_widget.currentIndex()
            if idx >= 0:
                self._close_tab_by_index(idx)
        else:
            count = self._splitter.count()
            if count > 0:
                w = self._splitter.widget(count - 1)
                self._remove_widget(w)

    def cycle_next(self):
        if self._mode == "tabbed" and self._tab_widget.count() > 1:
            i = (self._tab_widget.currentIndex() + 1) % self._tab_widget.count()
            self._tab_widget.setCurrentIndex(i)

    def cycle_prev(self):
        if self._mode == "tabbed" and self._tab_widget.count() > 1:
            i = (self._tab_widget.currentIndex() - 1) % self._tab_widget.count()
            self._tab_widget.setCurrentIndex(i)

    def all_terminals(self) -> list[TerminalWidget]:
        return list(self._sessions.values())

    def get_open_sessions(self) -> list[Session]:
        return [w.session for w in self._sessions.values()]

    def to_tabbed(self):
        if self._mode == "tabbed":
            return
        self._mode = "tabbed"
        widgets = []
        while self._splitter.count():
            w = self._splitter.widget(0)
            w.setParent(None)
            widgets.append(w)
        for w in widgets:
            label = f"{STATUS_CONNECTED} {w.session.display_name()}"
            idx = self._tab_widget.addTab(w, label)
        if self._tab_widget.count():
            self._tab_widget.setCurrentIndex(self._tab_widget.count() - 1)
        self._stack.setCurrentIndex(0)

    def tile(self, orientation: Qt.Orientation):
        self._mode = "tiled"
        self._splitter.setOrientation(orientation)
        widgets = []
        while self._tab_widget.count():
            w = self._tab_widget.widget(0)
            self._tab_widget.removeTab(0)
            widgets.append(w)
        for w in widgets:
            w.setParent(self._splitter)
            self._splitter.addWidget(w)
        total = self._splitter.count()
        if total:
            sz = (self._splitter.width() if orientation == Qt.Orientation.Horizontal
                  else self._splitter.height())
            self._splitter.setSizes([sz // total] * total)
        self._stack.setCurrentIndex(1)

    # ------------------------------------------------------------------ #
    def _update_tab_status(self, session_id: str, status: str):
        w = self._sessions.get(session_id)
        if not w or self._mode != "tabbed":
            return
        for i in range(self._tab_widget.count()):
            if self._tab_widget.widget(i) is w:
                dot = {
                    "connecting":   STATUS_CONNECTING,
                    "connected":    STATUS_CONNECTED,
                    "disconnected": STATUS_DISCONNECTED,
                }.get(status, STATUS_CONNECTING)
                self._tab_widget.setTabText(i, f"{dot} {w.session.display_name()}")
                break

    def _close_tab_by_index(self, index: int):
        w = self._tab_widget.widget(index)
        if w:
            self._remove_widget(w)
            self._tab_widget.removeTab(index)

    def _remove_widget(self, w: QWidget):
        sid = next((k for k, v in self._sessions.items() if v is w), None)
        if sid:
            self._sessions.pop(sid)
        if isinstance(w, TerminalWidget):
            w.terminate()
        w.deleteLater()
        self.tab_count_changed.emit(len(self._sessions))

    def _on_terminal_closed(self, session_id: str):
        w = self._sessions.pop(session_id, None)
        if not w:
            return
        self._update_tab_status(session_id, "disconnected")
        # Re-insert so it stays in the tab with red dot, not removed
        # (user can close it manually or reconnect)
        self._sessions[session_id] = w
        self.tab_count_changed.emit(len(self._sessions))

    def _focus_session(self, session_id: str):
        w = self._sessions.get(session_id)
        if w and self._mode == "tabbed":
            for i in range(self._tab_widget.count()):
                if self._tab_widget.widget(i) is w:
                    self._tab_widget.setCurrentIndex(i)
                    return
