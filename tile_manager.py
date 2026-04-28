"""
tile_manager.py — manages the recursive splitter tree of TilePanes.

Drop handling:
  center      → move tab into target pane's tab group
  east/west   → split target pane vertically, new pane gets the tab
  north/south → split target pane horizontally

After every drop, _sweep_empty_panes() removes any pane that ended up
empty — including the edge case where source_pane == target_pane.
"""
from __future__ import annotations
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSplitter, QWidget, QVBoxLayout

from session_model import Session
from terminal_tab import TerminalWidget
from tile_pane import TilePane, _DRAG_PAYLOAD

log = logging.getLogger(__name__)

STATUS_CONNECTING   = "🟡"
STATUS_CONNECTED    = "🟢"
STATUS_DISCONNECTED = "🔴"

SPLITTER_STYLE = """
QSplitter::handle           { background: #21262d; }
QSplitter::handle:horizontal{ width:  5px; }
QSplitter::handle:vertical  { height: 5px; }
QSplitter::handle:hover     { background: #58a6ff; }
"""


class TileManager(QWidget):
    tab_count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._sessions: dict[str, tuple[TerminalWidget, TilePane | None]] = {}
        self._floating_windows: list = []

        self._root_pane = TilePane(self._all_panes, parent=self)
        self._active_pane: TilePane = self._root_pane
        self._connect_pane(self._root_pane)
        self._layout.addWidget(self._root_pane)

    # ── Public API ────────────────────────────────────────────────────────────

    def open_session(self, session: Session):
        # Always create a new terminal — multiple instances of the same
        # configured session are fully supported (e.g. two root shells on
        # the same host).  We key _sessions by bridge session_id (UUID),
        # NOT by the configured session's ID.
        widget = TerminalWidget(session)
        inst_sid = widget._session_id   # unique per terminal instance

        widget.terminal_closed.connect(
            lambda sid=inst_sid: self._on_terminal_closed(sid))
        widget.status_changed.connect(
            lambda st, sid=inst_sid: self._on_status_changed(sid, st))

        label = f"{STATUS_CONNECTING} {session.display_name()}"
        pane = self._active_pane
        idx  = pane.addTab(widget, label)
        pane.setCurrentIndex(idx)
        self._sessions[inst_sid] = (widget, pane)
        self.tab_count_changed.emit(len(self._sessions))

    def close_current(self):
        idx = self._active_pane.currentIndex()
        if idx >= 0:
            self._active_pane.tabCloseRequested.emit(idx)

    def cycle_next(self):
        p = self._active_pane
        if p.count() > 1:
            p.setCurrentIndex((p.currentIndex() + 1) % p.count())

    def cycle_prev(self):
        p = self._active_pane
        if p.count() > 1:
            p.setCurrentIndex((p.currentIndex() - 1) % p.count())

    def cycle_pane_next(self):
        """Move keyboard focus to the next pane (in layout order)."""
        panes = self._all_panes()
        if len(panes) < 2:
            return
        try:
            i = panes.index(self._active_pane)
        except ValueError:
            i = 0
        self._active_pane = panes[(i + 1) % len(panes)]
        self._active_pane.setFocus()
        w = self._active_pane.currentWidget()
        if w:
            w.setFocus()

    def all_terminals(self) -> list[TerminalWidget]:
        return [w for w, _ in self._sessions.values()]

    def get_open_sessions(self) -> list[Session]:
        return [w.session for w, _ in self._sessions.values()]

    def get_open_terminals(self) -> list[TerminalWidget]:
        return [w for w, _ in self._sessions.values()]

    # ── Pane wiring ───────────────────────────────────────────────────────────

    def _connect_pane(self, pane: TilePane):
        pane.tab_count_changed.connect(self._on_any_pane_changed)
        pane.tab_closed.connect(self._on_tab_closed)
        pane.detach_requested.connect(self._on_detach_requested)
        pane.drop_received.connect(self._on_drop)
        pane.currentChanged.connect(lambda _i, p=pane: self._set_active(p))
        pane.split_requested.connect(self._on_split_requested)
        pane.close_others_requested.connect(self._on_close_others)
        pane.close_right_requested.connect(self._on_close_right)
        pane.close_all_requested.connect(self._on_close_all)

    def _set_active(self, pane: TilePane):
        self._active_pane = pane
        # Highlight active pane tab bar, dim others
        for p in self._all_panes():
            p.set_active(p is pane)

    def _focus(self, widget: QWidget, pane: TilePane):
        idx = pane.indexOf(widget)
        if idx >= 0:
            pane.setCurrentIndex(idx)
        self._set_active(pane)

    # ── Tree helpers ──────────────────────────────────────────────────────────

    def _root_widget(self) -> QWidget | None:
        item = self._layout.itemAt(0)
        return item.widget() if item else None

    def _set_root_widget(self, widget: QWidget):
        old = self._root_widget()
        if old:
            old.setParent(None)
        self._layout.addWidget(widget)

    def _find_parent(self, widget: QWidget) -> tuple[QWidget | None, int]:
        parent = widget.parent()
        if parent is self:
            return (self, 0)
        if isinstance(parent, QSplitter):
            return (parent, parent.indexOf(widget))
        return (None, -1)

    def _all_panes(self) -> list[TilePane]:
        result: list[TilePane] = []
        self._collect_panes(self._root_widget(), result)
        return result

    def _collect_panes(self, widget: QWidget | None, out: list):
        if widget is None:
            return
        if isinstance(widget, TilePane):
            out.append(widget)
        elif isinstance(widget, QSplitter):
            for i in range(widget.count()):
                self._collect_panes(widget.widget(i), out)

    # ── Split ─────────────────────────────────────────────────────────────────

    def _make_splitter(self, orientation: Qt.Orientation) -> QSplitter:
        s = QSplitter(orientation)
        s.setChildrenCollapsible(False)
        s.setHandleWidth(5)
        s.setStyleSheet(SPLITTER_STYLE)
        return s

    def _split(self, target: TilePane, widget: QWidget,
               text: str, direction: str) -> TilePane:
        new_pane = TilePane(self._all_panes)
        self._connect_pane(new_pane)
        new_pane.addTab(widget, text)

        horizontal = direction in ("east", "west")
        orientation = (Qt.Orientation.Horizontal if horizontal
                       else Qt.Orientation.Vertical)
        splitter = self._make_splitter(orientation)

        parent, idx = self._find_parent(target)
        parent_sizes = parent.sizes() if isinstance(parent, QSplitter) else None

        target.setParent(None)

        if direction in ("east", "south"):
            splitter.addWidget(target)
            splitter.addWidget(new_pane)
        else:
            splitter.addWidget(new_pane)
            splitter.addWidget(target)

        dim = self.width() if horizontal else self.height()
        half = max(dim // 2, 80)
        splitter.setSizes([half, half])

        if isinstance(parent, QSplitter):
            parent.insertWidget(idx, splitter)
            if parent_sizes:
                parent.setSizes(parent_sizes)
        else:
            self._set_root_widget(splitter)

        return new_pane

    # ── Empty pane cleanup ────────────────────────────────────────────────────

    def _sweep_empty_panes(self):
        """
        Remove all empty panes (except the root pane).
        Called after every drop operation to handle all edge cases — including
        the case where source_pane == target_pane in a zone-based split.
        """
        changed = True
        while changed:
            changed = False
            for pane in self._all_panes():
                if pane.count() == 0 and self._root_widget() is not pane:
                    self._remove_empty_pane(pane)
                    changed = True
                    break   # restart scan — tree may have restructured

        # Repair active pane reference
        if not self._active_pane or not self._active_pane.isVisible():
            panes = self._all_panes()
            self._active_pane = panes[0] if panes else self._root_pane

    def _remove_empty_pane(self, pane: TilePane):
        if self._root_widget() is pane:
            return

        parent, idx = self._find_parent(pane)
        if not isinstance(parent, QSplitter):
            return

        pane.setParent(None)
        pane.deleteLater()

        if parent.count() == 1:
            remaining = parent.widget(0)
            grandparent, gidx = self._find_parent(parent)
            remaining.setParent(None)
            parent.setParent(None)
            parent.deleteLater()
            if isinstance(grandparent, QSplitter):
                grandparent.insertWidget(gidx, remaining)
            else:
                self._set_root_widget(remaining)

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _on_any_pane_changed(self):
        self._sweep_empty_panes()
        self.tab_count_changed.emit(len(self._sessions))

    def _on_tab_closed(self, widget: QWidget):
        sid = next((k for k, (w, _) in self._sessions.items() if w is widget), None)
        if sid:
            del self._sessions[sid]
        self._sweep_empty_panes()
        self.tab_count_changed.emit(len(self._sessions))

    def _on_status_changed(self, session_id: str, status: str):
        if session_id not in self._sessions:
            return
        widget, pane = self._sessions[session_id]
        if pane is None:
            return
        idx = pane.indexOf(widget)
        if idx < 0:
            return
        dot = {"connecting": STATUS_CONNECTING,
               "connected":  STATUS_CONNECTED,
               "disconnected": STATUS_DISCONNECTED}.get(status, STATUS_CONNECTING)
        pane.setTabText(idx, f"{dot} {widget.session.display_name()}")

    def _on_terminal_closed(self, session_id: str):
        self._on_status_changed(session_id, "disconnected")
        self.tab_count_changed.emit(len(self._sessions))

    def _on_detach_requested(self, pane: TilePane, idx: int):
        from detached_window import DetachedWindow

        widget = pane.widget(idx)
        if widget is None:
            return

        session = widget.session
        old_sid = widget._session_id
        sid     = next((k for k, (w, _) in self._sessions.items() if w is widget), None)

        widget.prepare_for_detach()
        pane.removeTab(idx)
        widget._terminated = True
        widget.deleteLater()
        if sid:
            del self._sessions[sid]

        self._sweep_empty_panes()

        win = DetachedWindow(session, old_sid)
        self._floating_windows.append(win)
        win.closing.connect(lambda w=win: self._on_floating_closed(w))
        win.redock_requested.connect(self._on_redock)
        win.show()

        self.tab_count_changed.emit(len(self._sessions))

    def _on_redock(self, session, existing_sid: str):
        from terminal_tab import TerminalWidget

        widget = TerminalWidget(session, session_id=existing_sid)
        pane   = self._active_pane
        idx    = pane.addTab(widget, f"🟡 {session.display_name()}")
        pane.setCurrentIndex(idx)
        self._sessions[existing_sid] = (widget, pane)
        widget.status_changed.connect(
            lambda st, sid=existing_sid: self._on_status_changed(sid, st))
        widget.terminal_closed.connect(
            lambda sid=existing_sid: self._on_terminal_closed(sid))
        self.tab_count_changed.emit(len(self._sessions))

    def _on_floating_closed(self, win):
        if win in self._floating_windows:
            self._floating_windows.remove(win)

    def _on_split_requested(self, pane: TilePane, idx: int, direction: str):
        """Right-click context menu split from a tab."""
        widget = pane.widget(idx)
        if widget is None:
            return
        text = pane.tabText(idx)
        sid  = next((k for k, (w, _) in self._sessions.items() if w is widget), None)

        pane.removeTab(idx)
        dest_pane = self._split(pane, widget, text, direction)

        if sid:
            self._sessions[sid] = (widget, dest_pane)
        self._set_active(dest_pane)
        self._sweep_empty_panes()
        self.tab_count_changed.emit(len(self._sessions))

    def _on_close_others(self, pane: TilePane, keep_idx: int):
        """Close all tabs in pane except keep_idx."""
        for i in range(pane.count() - 1, -1, -1):
            if i != keep_idx:
                pane.tabCloseRequested.emit(i)

    def _on_close_right(self, pane: TilePane, idx: int):
        """Close all tabs to the right of idx."""
        for i in range(pane.count() - 1, idx, -1):
            pane.tabCloseRequested.emit(i)

    def _on_close_all(self, pane: TilePane):
        """Close all tabs in pane."""
        for i in range(pane.count() - 1, -1, -1):
            pane.tabCloseRequested.emit(i)

    def _on_drop(self, target_pane: TilePane, drag_id: str, zone: str):
        payload = _DRAG_PAYLOAD.pop(drag_id, None)
        if not payload:
            log.warning("Drop with no payload: %s", drag_id[:8])
            return

        source_pane: TilePane = payload["source"]
        widget: QWidget       = payload["widget"]
        text:   str           = payload["text"]
        sid = next((k for k, (w, _) in self._sessions.items() if w is widget), None)

        # Same pane, center — just focus the tab
        if source_pane is target_pane and zone == "center":
            idx = target_pane.indexOf(widget)
            if idx >= 0:
                target_pane.setCurrentIndex(idx)
            return

        # Remove from source pane
        src_idx = source_pane.indexOf(widget)
        if src_idx >= 0:
            source_pane.removeTab(src_idx)

        # Place in destination
        if zone == "center":
            new_idx = target_pane.addTab(widget, text)
            target_pane.setCurrentIndex(new_idx)
            dest_pane = target_pane
        else:
            dest_pane = self._split(target_pane, widget, text, zone)

        if sid:
            self._sessions[sid] = (widget, dest_pane)
        self._set_active(dest_pane)

        # Sweep up any empty panes — handles source_pane == target_pane edge case
        self._sweep_empty_panes()
        self.tab_count_changed.emit(len(self._sessions))
        # Force terminal repaint after reparent (QWebEngineView goes black otherwise)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(150, lambda: dest_pane.repaint_terminals())
