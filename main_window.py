import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout,
    QToolBar, QStatusBar, QMessageBox, QFileDialog, QLabel
)
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QSize


def _set_app_icon():
    """Load the TunnelRAT icon and apply it to QApplication + all windows."""
    import os
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    base = os.path.dirname(os.path.abspath(__file__))
    # Try multi-size icon first, then fallbacks
    candidates = [
        os.path.join(base, "icons", "tunnelrat_256.png"),
        os.path.join(base, "tunnelrat.png"),
        os.path.join(base, "icons", "tunnelrat_128.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            # Build a proper multi-resolution icon
            icon = QIcon()
            sizes = [
                ("tunnelrat_256.png", 256),
                ("tunnelrat_128.png", 128),
                ("tunnelrat_64.png",  64),
                ("tunnelrat_48.png",  48),
                ("tunnelrat_32.png",  32),
                ("tunnelrat_16.png",  16),
            ]
            for fname, sz in sizes:
                p = os.path.join(base, "icons", fname)
                if os.path.exists(p):
                    from PyQt6.QtGui import QPixmap
                    icon.addPixmap(QPixmap(p))
            if icon.isNull():
                icon = QIcon(path)
            # Apply to the application so taskbar, alt-tab, dialogs all show it
            QApplication.instance().setWindowIcon(icon)
            return


from session_tree import SessionTree, ROLE_IS_GROUP, ROLE_SESSION_ID
from tile_manager import TileManager
from broadcast_panel import BroadcastPanel
from session_manager import SessionManager
from xml_importer import import_superputty_xml
from session_dialog import SessionDialog
from quick_connect import QuickConnectDialog
from session_model import Session

log = logging.getLogger(__name__)

MAIN_STYLE = """
QMainWindow, QWidget { background: #0d1117; color: #c9d1d9; }
QMenuBar {
    background: #161b22; color: #c9d1d9;
    border-bottom: 1px solid #21262d; padding: 2px; font-size: 13px;
}
QMenuBar::item:selected { background: #21262d; border-radius: 3px; }
QMenu {
    background: #161b22; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px; padding: 4px;
}
QMenu::item { padding: 5px 20px; border-radius: 3px; }
QMenu::item:selected { background: #21262d; color: #58a6ff; }
QMenu::separator { height: 1px; background: #30363d; margin: 4px 8px; }
QToolBar {
    background: #161b22; border-bottom: 1px solid #21262d;
    spacing: 4px; padding: 4px 6px;
}
QToolBar::separator { width: 1px; background: #30363d; margin: 2px 4px; }
QToolButton {
    background: transparent; color: #8b949e;
    border: 1px solid transparent; border-radius: 4px;
    padding: 4px 10px; font-size: 12px;
}
QToolButton:hover { background: #21262d; color: #c9d1d9; border-color: #30363d; }
QToolButton:pressed { background: #30363d; }
QStatusBar {
    background: #161b22; color: #8b949e;
    border-top: 1px solid #21262d; font-size: 11px; padding: 2px 8px;
}
QSplitter::handle { background: #21262d; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session_manager = SessionManager()
        self.setWindowTitle("TunnelRAT")
        _set_app_icon()
        self.setMinimumSize(1100, 650)
        self.resize(1400, 900)
        self.setStyleSheet(MAIN_STYLE)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._connect_signals()
        self._setup_shortcuts()

        self.session_manager.load()
        self.session_tree.refresh(self.session_manager.sessions)
        self._update_status()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.session_tree = SessionTree()
        self.session_tree.setMinimumWidth(150)
        self.session_tree.setMaximumWidth(500)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.tab_manager = TileManager()
        self.broadcast_panel = BroadcastPanel()

        right_layout.addWidget(self.tab_manager, stretch=1)
        right_layout.addWidget(self.broadcast_panel)

        self.main_splitter.addWidget(self.session_tree)
        self.main_splitter.addWidget(right)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setCollapsible(0, True)
        self.main_splitter.setSizes([240, 1160])

        layout.addWidget(self.main_splitter)
        self.setStatusBar(QStatusBar())

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_m = mb.addMenu("&File")
        self._act(file_m, "&New Session…",      self.new_session,   "Ctrl+N")
        self._act(file_m, "⚡ &Quick Connect…", self.quick_connect, "Ctrl+Shift+Q")
        file_m.addSeparator()
        self._act(file_m, "&Import Sessions…",  self.import_xml)
        self._act(file_m, "E&xport Sessions…",  self.export_sessions)
        file_m.addSeparator()
        self._act(file_m, "⚙  &Preferences…",   self.open_preferences, "Ctrl+,")
        file_m.addSeparator()
        self._act(file_m, "&Quit", self.close, "Ctrl+Q")

        # Session
        sess_m = mb.addMenu("&Session")
        self._act(sess_m, "&Connect Selected",       self.connect_selected,            "Ctrl+Return")
        self._act(sess_m, "Connect All in &Group",   self.connect_all_in_selected_group)
        sess_m.addSeparator()
        self._act(sess_m, "&Disconnect Current Tab", self.disconnect_current, "Ctrl+W")
        self._act(sess_m, "Disconnect &All",         self.disconnect_all)

        # View
        view_m = mb.addMenu("&View")
        self._act(view_m, "Next Tab",              self.tab_manager.cycle_next, "Ctrl+Tab")
        self._act(view_m, "Previous Tab",          self.tab_manager.cycle_prev, "Ctrl+Shift+Tab")
        view_m.addSeparator()
        self._act(view_m, "Toggle Session &Panel", self._toggle_tree_panel,     "Ctrl+\\")
        self._act(view_m, "Collapse All Groups",   self.session_tree.collapse_all)
        view_m.addSeparator()
        self._fullscreen_act = view_m.addAction("⛶  &Fullscreen    F11")
        self._fullscreen_act.setCheckable(True)
        # Shortcut managed by _setup_shortcuts so it works even when
        # focus is inside QWebEngineView
        self._fullscreen_act.triggered.connect(self._toggle_fullscreen)
        self._ontop_act = view_m.addAction("📌  Always on &Top")
        self._ontop_act.setCheckable(True)
        self._ontop_act.triggered.connect(self._toggle_always_on_top)

        # Layouts menu
        layouts_m = mb.addMenu("&Layouts")
        self._act(layouts_m, "💾  Save Layout…",   self._save_layout,   "Ctrl+S")
        self._act(layouts_m, "📂  Load Layout…",   self._load_layout)
        self._act(layouts_m, "🗑  Delete Layout…", self._delete_layout)
        self._act(view_m, "Expand All Groups",     self.session_tree.expand_all)
        view_m.addSeparator()
        self._act(view_m, "Move Panel to Right",   self._panel_to_right)
        self._act(view_m, "Move Panel to Left",    self._panel_to_left)

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))

        def btn(label, slot, tip=""):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)

        btn("＋ New Session",   self.new_session,        "New session (Ctrl+N)")
        btn("⚡ Quick Connect", self.quick_connect,      "Connect without saving (Ctrl+Shift+Q)")
        tb.addSeparator()
        btn("▶ Connect",        self.connect_selected,   "Connect selected")
        btn("✕ Disconnect",     self.disconnect_current, "Disconnect current tab (Ctrl+W)")
        tb.addSeparator()
        btn("📥 Import",        self.import_xml,         "Import sessions")

    def _act(self, menu, label, slot, shortcut=None):
        a = QAction(label, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        menu.addAction(a)
        return a

    # ── Hotkey actions map ───────────────────────────────────────────────────
    def _hotkey_action_map(self) -> dict:
        """Map hotkey keys to callables."""
        return {
            "next_tab":           self.tab_manager.cycle_next,
            "prev_tab":           self.tab_manager.cycle_prev,
            "close_tab":          self.tab_manager.close_current,
            "fullscreen":         lambda: self._fullscreen_act.trigger(),
            "new_session":        self.new_session,
            "quick_connect":      self.quick_connect,
            "connect_selected":   self.connect_selected,
            "disconnect_current": self.disconnect_current,
            "focus_broadcast":    lambda: self.broadcast_panel._cmd.setFocus(),
            "rename_tab":         self._rename_current_tab,
            "command_mask":       self.broadcast_panel.toggle_mask_hotkey,
            "always_on_top":      lambda: self._ontop_act.trigger(),
            "save_layout":        self._save_layout,
        }

    def _rename_current_tab(self):
        pane = self.tab_manager._active_pane
        if pane:
            pane._rename_tab(pane.currentIndex())

    def _setup_shortcuts(self):
        """Build QShortcut objects from saved preferences."""
        from preferences_dialog import load_prefs
        prefs = load_prefs()
        hotkeys = prefs.get("hotkeys", {})
        actions = self._hotkey_action_map()
        self._shortcuts: dict[str, QShortcut] = {}
        for key, fn in actions.items():
            ks_str = hotkeys.get(key, "")
            if ks_str:
                sc = QShortcut(QKeySequence(ks_str), self)
                sc.activated.connect(fn)
                self._shortcuts[key] = sc

    def _rebuild_shortcuts(self):
        """Re-apply shortcuts after preferences change."""
        for sc in getattr(self, "_shortcuts", {}).values():
            sc.setParent(None)
        self._shortcuts = {}
        self._setup_shortcuts()

    # ------------------------------------------------------------------ #
    def _connect_signals(self):
        self.session_tree.session_double_clicked.connect(self.open_session)
        self.session_tree.connect_requested.connect(self.open_session)
        self.session_tree.edit_requested.connect(self.edit_session)
        self.session_tree.delete_requested.connect(self.delete_session)
        self.session_tree.duplicate_requested.connect(self.duplicate_session)
        self.session_tree.group_rename_requested.connect(self._rename_group)
        self.session_tree.group_color_changed.connect(self._group_color_changed)
        self.session_tree.group_create_requested.connect(self._create_group)
        self.session_tree.group_delete_all_requested.connect(self._delete_sessions_bulk)
        self.session_tree.new_session_requested.connect(self.new_session)
        self.session_tree.export_requested.connect(self.export_sessions)

        self.tab_manager.tab_count_changed.connect(self._update_status)
        self.tab_manager.tab_count_changed.connect(self._sync_broadcast_sessions)

        # Apply saved app theme (including tab styles) at startup
        from preferences_dialog import load_prefs, build_app_stylesheet, build_tab_style
        _p = load_prefs()
        self.setStyleSheet(build_app_stylesheet(_p))
        _act = build_tab_style(_p, active=True)
        _ina = build_tab_style(_p, active=False)
        try:
            for _pane in self.tab_manager._all_panes():
                _pane.apply_tab_style(_act, _ina)
        except Exception:
            pass


    # ------------------------------------------------------------------ #
    #  Session CRUD
    # ------------------------------------------------------------------ #
    def new_session(self, group: str | None = None):
        dlg = SessionDialog(parent=self)
        if isinstance(group, str) and group not in ("", "Default"):
            dlg.set_group(group)
        if dlg.exec():
            s = dlg.get_session()
            self.session_manager.add(s)
            self.session_tree.refresh(self.session_manager.sessions)
            self.statusBar().showMessage(f"Session '{s.name}' added", 3000)

    def quick_connect(self):
        dlg = QuickConnectDialog(parent=self)
        if dlg.exec():
            s = dlg.get_session()
            # Open without persisting
            self.tab_manager.open_session(s)
            self.statusBar().showMessage(f"Quick connecting → {s.host}…", 4000)

    def edit_session(self, session_id: str):
        s = self.session_manager.get(session_id)
        if not s:
            return
        dlg = SessionDialog(session=s, parent=self)
        if dlg.exec():
            updated = dlg.get_session()
            self.session_manager.update(updated)
            self.session_tree.refresh(self.session_manager.sessions)

    def duplicate_session(self, session_id: str):
        s = self.session_manager.get(session_id)
        if not s:
            return
        import uuid as _uuid
        from dataclasses import replace
        dup = Session(**{**s.to_dict(),
                         "id": str(_uuid.uuid4()),
                         "name": s.name + " (copy)",
                         "last_connected": ""})
        self.session_manager.add(dup)
        self.session_tree.refresh(self.session_manager.sessions)
        self.statusBar().showMessage(f"Duplicated '{s.name}'", 3000)

    def delete_session(self, session_id: str):
        s = self.session_manager.get(session_id)
        if not s:
            return
        reply = QMessageBox.question(
            self, "Delete Session",
            f"Delete session '{s.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.session_manager.delete(session_id)
            self.session_tree.refresh(self.session_manager.sessions)

    # ── Group management ──────────────────────────────────────────────────────

    def _create_group(self, name: str):
        """Create a new group by opening New Session dialog with group pre-filled."""
        # Groups are implicit — they only exist when sessions belong to them.
        # Jump straight to the New Session dialog with the group name pre-filled.
        self.new_session_requested.emit(name)

    def _rename_group(self, old_name: str, new_name: str):
        """Rename a group by updating all sessions in it."""
        if new_name == "__DELETE_EMPTY__":
            # Empty group — nothing to do, just refresh
            self.session_tree.refresh(self.session_manager.sessions)
            return
        changed = 0
        for s in self.session_manager.sessions.values():
            if s.group == old_name:
                s.group = new_name
                changed += 1
        if changed:
            self.session_manager.save()
            self.session_tree.refresh(self.session_manager.sessions)
            self.statusBar().showMessage(
                f"Group '{old_name}' renamed to '{new_name}' ({changed} sessions)", 3000)

    def _delete_group(self, group_name: str):
        """Delete all sessions in a group."""
        sids = [sid for sid, s in self.session_manager.sessions.items()
                if s.group == group_name]
        for sid in sids:
            self.session_manager.delete(sid)
        self.session_tree.refresh(self.session_manager.sessions)
        self.statusBar().showMessage(
            f"Deleted group '{group_name}' and {len(sids)} session(s)", 3000)

    def _group_color_changed(self, group_name: str, color: str):
        """Persist custom group color."""
        self.session_tree._group_color_map[group_name] = color
        self.statusBar().showMessage(
            f"Group '{group_name}' color updated", 2000)

    def _delete_sessions_bulk(self, sids: list):
        """Delete multiple sessions without individual confirmation dialogs."""
        for sid in sids:
            self.session_manager.delete(sid)
        self.session_manager.save()
        self.session_tree.refresh(self.session_manager.sessions)
        self.statusBar().showMessage(f"Deleted {len(sids)} session(s)", 3000)

    def open_session(self, session_id: str):
        s = self.session_manager.get(session_id)
        if not s:
            return
        self.tab_manager.open_session(s)
        # Persist last_connected after tab opens
        QTimer_oneshot = __import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer
        QTimer_oneshot.singleShot(
            500, lambda: self._persist_last_connected(session_id)
        )
        self.statusBar().showMessage(f"Connecting → {s.username}@{s.host}…", 4000)

    def _persist_last_connected(self, session_id: str):
        s = self.session_manager.get(session_id)
        if s:
            s.last_connected = datetime.now(timezone.utc).isoformat()
            self.session_manager.update(s)

    def connect_selected(self):
        for sid in self.session_tree.selected_sessions():
            self.open_session(sid)

    def connect_all_in_selected_group(self):
        for item in self.session_tree.selectedItems():
            if item.data(0, ROLE_IS_GROUP):
                group = item.data(0, ROLE_SESSION_ID)
                for s in self.session_manager.sessions_in_group(group):
                    self.tab_manager.open_session(s)

    def disconnect_current(self):
        self.tab_manager.close_current()

    def disconnect_all(self):
        reply = QMessageBox.question(
            self, "Disconnect All", "Close all open SSH sessions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for t in self.tab_manager.all_terminals():
                t.terminate()
            self.tab_manager.to_tabbed()

    # ------------------------------------------------------------------ #
    #  Import / Export
    # ------------------------------------------------------------------ #
    def import_xml(self):
        from preferences_dialog import build_dialog_stylesheet, load_prefs
        dlg = QFileDialog(self, "Import Sessions", "",
                          "All Supported (*.xml *.json);;"
                          "TunnelRAT JSON (*.json);;"
                          "SuperPutty XML (*.xml);;"
                          "All Files (*)")
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setStyleSheet(build_dialog_stylesheet(load_prefs()))
        if not dlg.exec():
            return
        paths = dlg.selectedFiles()
        path = paths[0] if paths else ""
        if not path:
            return

        try:
            if path.lower().endswith(".json"):
                # Native TunnelRAT JSON format
                sessions = self._import_json(path)
            else:
                # SuperPutty XML format
                sessions = import_superputty_xml(path)

            added = 0
            for s in sessions:
                if not self.session_manager.get_by_name_host(s.name, s.host):
                    self.session_manager.add(s)
                    added += 1
            self.session_manager.save()
            self.session_tree.refresh(self.session_manager.sessions)
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {added} new session(s).\n"
                f"({len(sessions) - added} skipped — already exist)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error",
                f"Failed to import sessions:\n{e}")

    def _import_json(self, path: str):
        """Import sessions from TunnelRAT native JSON export format."""
        from session_model import Session
        with open(path, "r") as f:
            data = json.load(f)
        sessions = []
        for item in data:
            try:
                s = Session(
                    name       = item.get("name", ""),
                    host       = item.get("host", ""),
                    port       = int(item.get("port", 22)),
                    username   = item.get("username", ""),
                    auth_type  = item.get("auth_type", "password"),
                    key_file   = item.get("key_file", ""),
                    cert_file  = item.get("cert_file", ""),
                    password   = item.get("password", ""),
                    jump_host  = item.get("jump_host", ""),
                    keepalive  = int(item.get("keepalive", 60)),
                    extra_args = item.get("extra_args", ""),
                    group      = item.get("group", "Default"),
                    notes      = item.get("notes", ""),
                )
                sessions.append(s)
            except Exception as e:
                log.warning("Skipping session entry: %s", e)
        return sessions

    def export_sessions(self):
        from preferences_dialog import build_dialog_stylesheet, load_prefs
        dlg = QFileDialog(self, "Export Sessions",
                          str(Path.home() / "sessions_export.json"),
                          "JSON Files (*.json);;All Files (*)")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setStyleSheet(build_dialog_stylesheet(load_prefs()))
        if not dlg.exec():
            return
        paths = dlg.selectedFiles()
        path = paths[0] if paths else ""
        if not path:
            return
        _ = None  # unused
        if not path:
            return
        try:
            data = [s.to_dict() for s in self.session_manager.sessions.values()]
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self.statusBar().showMessage(
                f"Exported {len(data)} session(s) to {path}", 5000
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ------------------------------------------------------------------ #
    #  Broadcast
    # ------------------------------------------------------------------ #
    def _sync_broadcast_sessions(self, _count: int = 0):
        self.broadcast_panel.update_open_sessions(self.tab_manager.get_open_terminals())



    # ------------------------------------------------------------------ #
    def open_preferences(self):
        from preferences_dialog import PreferencesDialog
        dlg = PreferencesDialog(self)
        dlg.prefs_changed.connect(self._apply_prefs)
        dlg.exec()

    def _apply_prefs(self, prefs: dict):
        """Apply changed preferences to all open terminals and app theme."""
        from preferences_dialog import build_app_stylesheet, build_tab_style
        self.setStyleSheet(build_app_stylesheet(prefs))
        # Re-apply tab bar styles to all panes from app theme
        active_style   = build_tab_style(prefs, active=True)
        inactive_style = build_tab_style(prefs, active=False)
        try:
            for pane in self.tab_manager._all_panes():
                pane.apply_tab_style(active_style, inactive_style)
        except Exception:
            pass
        for w in self.tab_manager.all_terminals():
            try:
                w.apply_prefs(prefs)
            except Exception:
                pass
        self._rebuild_shortcuts()

    # ── Fullscreen / Always on Top ───────────────────────────────────────────

    def _toggle_fullscreen(self, checked: bool):
        """Toggle fullscreen — fills the screen removing OS chrome (taskbar,
        window decorations) while keeping all app UI fully accessible."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def _toggle_always_on_top(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    # ── Layouts ──────────────────────────────────────────────────────────────

    def _save_layout(self):
        from PyQt6.QtWidgets import QInputDialog
        from layout_manager import save_layout, list_layouts
        existing = list_layouts()
        name, ok = QInputDialog.getText(self, "Save Layout", "Layout name:",
                                         text="default")
        if not ok or not name.strip():
            return
        path = save_layout(name.strip(), self.tab_manager, self)
        self.statusBar().showMessage(f"Layout '{name}' saved", 3000)

    def _load_layout(self):
        from PyQt6.QtWidgets import QInputDialog
        from layout_manager import list_layouts, restore_layout
        layouts = list_layouts()
        if not layouts:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Layouts", "No saved layouts found.")
            return
        name, ok = QInputDialog.getItem(self, "Load Layout", "Select layout:",
                                         layouts, 0, False)
        if not ok:
            return
        restore_layout(name, self.tab_manager, self, self.session_manager)
        self.statusBar().showMessage(f"Layout '{name}' restored", 3000)

    def _delete_layout(self):
        from PyQt6.QtWidgets import QInputDialog
        from layout_manager import list_layouts, delete_layout
        layouts = list_layouts()
        if not layouts:
            return
        name, ok = QInputDialog.getItem(self, "Delete Layout", "Select layout:",
                                         layouts, 0, False)
        if not ok:
            return
        delete_layout(name)
        self.statusBar().showMessage(f"Layout '{name}' deleted", 3000)

    def _toggle_tree_panel(self):
        self.session_tree.setVisible(not self.session_tree.isVisible())

    def _panel_to_right(self):
        """Move session panel to the right side."""
        tree = self.main_splitter.widget(0)
        right = self.main_splitter.widget(1)
        if tree is self.session_tree:
            self.main_splitter.addWidget(right)
            self.main_splitter.addWidget(tree)
            self.main_splitter.setStretchFactor(0, 1)
            self.main_splitter.setStretchFactor(1, 0)

    def _panel_to_left(self):
        """Move session panel to the left side."""
        w0 = self.main_splitter.widget(0)
        w1 = self.main_splitter.widget(1)
        if w0 is not self.session_tree:
            self.main_splitter.addWidget(w1)
            self.main_splitter.addWidget(w0)
            self.main_splitter.setStretchFactor(0, 1)
            self.main_splitter.setStretchFactor(1, 0)

    def _update_status(self, count: int = 0):
        total = len(self.session_manager.sessions)
        open_tabs = count or len(self.tab_manager.all_terminals())
        self.statusBar().showMessage(
            f"  {total} session(s) configured  │  {open_tabs} open"
        )
