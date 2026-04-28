import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QMenu, QAbstractItemView,
    QInputDialog, QMessageBox, QColorDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QColor, QBrush

log = logging.getLogger(__name__)

ROLE_SESSION_ID = Qt.ItemDataRole.UserRole.value
ROLE_IS_GROUP   = Qt.ItemDataRole.UserRole.value + 1

# One accent colour per group (cycles)
GROUP_COLORS = [
    "#58a6ff", "#3fb950", "#e3b341", "#f78166",
    "#d2a8ff", "#79c0ff", "#56d364", "#ffa657",
]

# Minimal hardcoded style - just layout, no colors.
# Colors come from the app theme stylesheet applied to QMainWindow.
TREE_STYLE = """
QTreeWidget {
    border: none; font-size: 13px; outline: none;
}
QTreeWidget::item { padding: 3px 4px; border-radius: 3px; }
QLineEdit#search {
    border: 1px solid #30363d; border-radius: 4px;
    padding: 4px 8px; font-size: 12px;
}
"""

MENU_STYLE = """
QMenu {
    border: 1px solid #30363d; border-radius: 4px; padding: 4px;
}
QMenu::item { padding: 5px 20px; border-radius: 3px; }
QMenu::separator { height: 1px; background: #30363d; margin: 4px 8px; }
"""


class SessionTree(QWidget):
    session_double_clicked = pyqtSignal(str)
    connect_requested      = pyqtSignal(str)
    edit_requested         = pyqtSignal(str)
    delete_requested       = pyqtSignal(str)
    duplicate_requested    = pyqtSignal(str)
    new_session_requested  = pyqtSignal(str)   # group name
    export_requested       = pyqtSignal()
    # Group management signals — handled by main_window
    group_rename_requested = pyqtSignal(str, str)   # old_name, new_name
    group_delete_all_requested = pyqtSignal(list)    # list of sids to delete in bulk
    group_color_changed    = pyqtSignal(str, str)    # group_name, color
    group_create_requested = pyqtSignal(str)         # new group name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_sessions: dict = {}
        self._group_color_map: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._search = QLineEdit()
        self._search.setObjectName("search")
        self._search.setPlaceholderText("🔍  Filter sessions…")
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("SESSIONS")
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.setAnimated(True)
        self._tree.setIndentation(14)
        layout.addWidget(self._tree)


    # ------------------------------------------------------------------ #
    def refresh(self, sessions: dict):
        self._all_sessions = sessions
        self._apply_filter(self._search.text())

    def _apply_filter(self, text: str):
        query = text.strip().lower()
        self._tree.clear()

        groups: dict[str, list] = {}
        for s in self._all_sessions.values():
            if query and query not in s.display_name().lower() \
                    and query not in s.host.lower() \
                    and query not in s.group.lower():
                continue
            groups.setdefault(s.group, []).append(s)

        group_font = QFont()
        group_font.setBold(True)
        group_font.setPointSize(10)

        for idx, group_name in enumerate(
                sorted(groups.keys(), key=lambda g: (g != "Default", g.lower()))):
            color = self._group_color_map.setdefault(
                group_name, GROUP_COLORS[idx % len(GROUP_COLORS)]
            )
            group_item = QTreeWidgetItem([f"  {group_name}"])
            group_item.setFont(0, group_font)
            group_item.setForeground(0, QBrush(QColor(color)))
            group_item.setData(0, ROLE_IS_GROUP, True)
            group_item.setData(0, ROLE_SESSION_ID, group_name)
            self._tree.addTopLevelItem(group_item)

            for s in sorted(groups[group_name], key=lambda x: x.name.lower()):
                child = QTreeWidgetItem([f"  {s.display_name()}"])
                child.setData(0, ROLE_SESSION_ID, s.id)
                child.setData(0, ROLE_IS_GROUP, False)
                # Set text color from app theme so it follows theme changes
                try:
                    from preferences_dialog import load_prefs
                    _tx = load_prefs().get("app_text", "#c9d1d9")
                    child.setForeground(0, QBrush(QColor(_tx)))
                except Exception:
                    pass
                tip = f"{s.username}@{s.host}:{s.port}"
                if s.last_connected:
                    tip += f"\nLast: {s.last_connected[:16].replace('T', ' ')}"
                if s.notes:
                    tip += f"\n{s.notes}"
                child.setToolTip(0, tip)
                group_item.addChild(child)

            group_item.setExpanded(True)

    def selected_sessions(self) -> list[str]:
        return [
            item.data(0, ROLE_SESSION_ID)
            for item in self._tree.selectedItems()
            if not item.data(0, ROLE_IS_GROUP)
        ]

    def selectedItems(self):
        return self._tree.selectedItems()

    def collapse_all(self):
        self._tree.collapseAll()

    def expand_all(self):
        self._tree.expandAll()

    def _on_double_click(self, item: QTreeWidgetItem, _col: int):
        if not item.data(0, ROLE_IS_GROUP):
            self.session_double_clicked.emit(item.data(0, ROLE_SESSION_ID))

    def _context_menu(self, pos):
        item = self._tree.itemAt(pos)
        menu = QMenu(self)
        try:
            from preferences_dialog import load_prefs
            p = load_prefs()
            bg = p.get("app_surface","#161b22"); bd = p.get("app_border","#30363d")
            tx = p.get("app_text","#c9d1d9"); hv = p.get("app_hover","#21262d")
            ac = p.get("app_accent","#58a6ff")
            menu.setStyleSheet(f"""
                QMenu{{background:{bg};color:{tx};border:1px solid {bd};
                      border-radius:4px;padding:4px;}}
                QMenu::item{{padding:5px 20px;border-radius:3px;}}
                QMenu::item:selected{{background:{hv};color:{ac};}}
                QMenu::separator{{height:1px;background:{bd};margin:3px 8px;}}
            """)
        except Exception:
            menu.setStyleSheet(MENU_STYLE)

        def act(label, slot, sep_before=False):
            if sep_before:
                menu.addSeparator()
            a = QAction(label, self)
            a.triggered.connect(slot)
            menu.addAction(a)

        if item is None:
            # Blank area — create group or session
            act("➕  New Session…",    lambda: self.new_session_requested.emit("Default"))
            act("📁  New Group…",      self._create_group, sep_before=True)
            act("📤  Export Sessions…", self.export_requested.emit, sep_before=True)

        elif item.data(0, ROLE_IS_GROUP):
            group = item.data(0, ROLE_SESSION_ID)
            act(f"➕  New Session in '{group}'…", lambda: self.new_session_requested.emit(group))
            act("🔌  Connect All in Group",    lambda: self._connect_group(item), sep_before=True)
            act("✎   Rename Group…",           lambda: self._rename_group(group), sep_before=True)
            act("🎨  Change Group Color…",     lambda: self._change_group_color(group))
            act("🗑  Delete Group…",           lambda: self._delete_group(group, item), sep_before=True)
            act("🗑  Delete All Sessions in Group…",
                lambda: self._delete_all_in_group(group, item))
            act("─   Collapse All Groups",     self.collapse_all,  sep_before=True)
            act("─   Expand All Groups",       self.expand_all)
            act("📤  Export Sessions…",        self.export_requested.emit, sep_before=True)

        else:
            sid = item.data(0, ROLE_SESSION_ID)
            act("🔌  Connect",    lambda: self.connect_requested.emit(sid))
            act("✎   Edit…",     lambda: self.edit_requested.emit(sid),    sep_before=True)
            act("⧉   Duplicate", lambda: self.duplicate_requested.emit(sid))
            act("🗑  Delete",    lambda: self.delete_requested.emit(sid),  sep_before=True)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ── Group management ──────────────────────────────────────────────────────

    def _create_group(self):
        name, ok = QInputDialog.getText(self, "New Group", "Group name:")
        if ok and name.strip():
            self.group_create_requested.emit(name.strip())

    def _rename_group(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self, "Rename Group", "New group name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            self.group_rename_requested.emit(old_name, new_name.strip())

    def _change_group_color(self, group: str):
        current = self._group_color_map.get(group, "#58a6ff")
        try:
            from preferences_dialog import build_dialog_stylesheet, load_prefs
            dlg = QColorDialog(QColor(current), self)
            dlg.setWindowTitle(f"Color for '{group}'")
            dlg.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
            dlg.setStyleSheet(build_dialog_stylesheet(load_prefs()))
            if not dlg.exec():
                return
            color = dlg.selectedColor()
        except Exception:
            color = QColorDialog.getColor(QColor(current), self, f"Color for '{group}'")
            if not color.isValid():
                return
        if not color.isValid():
            return
        self._group_color_map[group] = color.name()
        # Apply immediately to the group item without full rebuild
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, ROLE_IS_GROUP) and item.data(0, ROLE_SESSION_ID) == group:
                item.setForeground(0, QBrush(QColor(color.name())))
                break
        self.group_color_changed.emit(group, color.name())

    def _delete_group(self, group: str, item: QTreeWidgetItem):
        """Delete the group header only — move sessions to Default."""
        count = item.childCount()
        if count == 0:
            # Empty group — just remove it visually (no sessions to move)
            self.group_rename_requested.emit(group, "__DELETE_EMPTY__")
            return
        reply = QMessageBox.question(
            self, "Delete Group",
            f"Move all {count} session(s) from '{group}' to Default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            self.group_rename_requested.emit(group, "Default")

    def _delete_all_in_group(self, group: str, item: QTreeWidgetItem):
        """Delete all sessions inside the group — one confirmation, no per-session dialogs."""
        count = item.childCount()
        if count == 0:
            return
        reply = QMessageBox.question(
            self, "Delete All Sessions",
            f"Permanently delete all {count} session(s) in '{group}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if reply != QMessageBox.StandardButton.Yes:
            return
        sids = []
        for i in range(count):
            sid = item.child(i).data(0, ROLE_SESSION_ID)
            if sid:
                sids.append(sid)
        # Emit bulk signal — bypasses per-session confirmation dialogs
        self.group_delete_all_requested.emit(sids)

    def _connect_group(self, group_item: QTreeWidgetItem):
        for i in range(group_item.childCount()):
            child = group_item.child(i)
            sid = child.data(0, ROLE_SESSION_ID)
            if sid:
                self.connect_requested.emit(sid)
