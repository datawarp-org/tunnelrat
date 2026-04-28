"""
tile_pane.py — drag-aware tab widget for TunnelRAT tiling system.

DRAG: grabMouse() — bypasses X11/XDND which is consumed by Chromium's
      native X11 window. All mouse events come directly to the tab bar.

DROP ZONES: top-level _DropOverlay window floats above WebEngine.

DOUBLE-CLICK tab → detach to floating window.
RIGHT-CLICK tab → context menu: split right, split down, move to window.

ACTIVE PANE: visual indicator — bright tab bar border on active pane,
             dimmed on inactive panes.
"""
from __future__ import annotations
import logging
import uuid

from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPolygon
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMenu, QTabBar, QTabWidget, QWidget
)

log = logging.getLogger(__name__)

_DRAG_PAYLOAD: dict[str, dict] = {}

TAB_STYLE_ACTIVE = """
QTabWidget::pane{border:none;background:#0d1117;}
QTabBar{background:#161b22;border-bottom:2px solid #58a6ff;}
QTabBar::tab{background:#161b22;color:#8b949e;padding:6px 14px;
    border:none;border-right:1px solid #21262d;min-width:110px;font-size:12px;}
QTabBar::tab:selected{background:#0d1117;color:#58a6ff;border-bottom:2px solid #58a6ff;}
QTabBar::tab:hover{background:#1c2128;color:#c9d1d9;}
"""
TAB_STYLE_INACTIVE = """
QTabWidget::pane{border:none;background:#0d1117;}
QTabBar{background:#0d1117;border-bottom:1px solid #21262d;}
QTabBar::tab{background:#0d1117;color:#6e7681;padding:6px 14px;
    border:none;border-right:1px solid #161b22;min-width:110px;font-size:12px;}
QTabBar::tab:selected{background:#161b22;color:#8b949e;border-bottom:1px solid #30363d;}
QTabBar::tab:hover{background:#161b22;color:#c9d1d9;}
"""


# ── Drop overlay ──────────────────────────────────────────────────────────────

class _DropOverlay(QWidget):
    def __init__(self):
        super().__init__(None,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._zone: str | None = None
        self.hide()

    def show_over(self, widget: QWidget, zone: str | None):
        gp = widget.mapToGlobal(QPoint(0, 0))
        self.setGeometry(gp.x(), gp.y(), widget.width(), widget.height())
        if zone != self._zone:
            self._zone = zone
            self.update()
        if zone:
            self.show(); self.raise_()
        else:
            self.hide()

    def zone_for_global(self, gp: QPoint, widget: QWidget) -> str | None:
        local = widget.mapFromGlobal(gp)
        w, h  = widget.width(), widget.height()
        x, y  = local.x(), local.y()
        if not (0 <= x <= w and 0 <= y <= h):
            return None
        if w * 0.3 <= x <= w * 0.7 and h * 0.3 <= y <= h * 0.7:
            return "center"
        cx, cy = w / 2, h / 2
        if abs(x - cx) > abs(y - cy):
            return "east" if x > cx else "west"
        return "south" if y > cy else "north"

    def _zone_rect(self, zone: str) -> QRect:
        w, h = self.width(), self.height()
        if zone == "center": return QRect(int(w*.2), int(h*.2), int(w*.6), int(h*.6))
        if zone == "north":  return QRect(0, 0, w, h//2)
        if zone == "south":  return QRect(0, h//2, w, h - h//2)
        if zone == "west":   return QRect(0, 0, w//2, h)
        if zone == "east":   return QRect(w//2, 0, w - w//2, h)
        return QRect()

    def paintEvent(self, _):
        if not self._zone:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for z in ("center","north","south","east","west"):
            r = self._zone_rect(z)
            if z == self._zone:
                p.fillRect(r, QColor(31,111,235,70))
                p.setPen(QColor(88,166,255,220))
                p.drawRect(r.adjusted(1,1,-2,-2))
                self._arrow(p, r, z)
            else:
                p.fillRect(r, QColor(31,111,235,14))
                p.setPen(QColor(88,166,255,45))
                p.drawRect(r.adjusted(1,1,-2,-2))
        p.end()

    def _arrow(self, p, rect, zone):
        if zone == "center": return
        cx, cy, s = rect.center().x(), rect.center().y(), 12
        p.setBrush(QColor(88,166,255,200)); p.setPen(Qt.PenStyle.NoPen)
        if zone == "north":  pts = [QPoint(cx,cy-s),QPoint(cx+s,cy+s),QPoint(cx-s,cy+s)]
        elif zone == "south":pts = [QPoint(cx,cy+s),QPoint(cx+s,cy-s),QPoint(cx-s,cy-s)]
        elif zone == "west": pts = [QPoint(cx-s,cy),QPoint(cx+s,cy-s),QPoint(cx+s,cy+s)]
        else:                pts = [QPoint(cx+s,cy),QPoint(cx-s,cy-s),QPoint(cx-s,cy+s)]
        p.drawPolygon(QPolygon([QPoint(pt.x(),pt.y()) for pt in pts]))


_overlay = None
def _get_overlay() -> _DropOverlay:
    global _overlay
    if _overlay is None:
        _overlay = _DropOverlay()
    return _overlay


# ── Draggable tab bar ─────────────────────────────────────────────────────────

class _DraggableTabBar(QTabBar):
    detach_requested  = pyqtSignal(int)
    split_requested   = pyqtSignal(int, str)   # idx, direction
    drop_on_pane      = pyqtSignal(object, str, str)

    def __init__(self, pane_locator, parent=None):
        super().__init__(parent)
        self._pane_locator = pane_locator
        self._press_pt:  QPoint | None = None
        self._press_idx: int = -1
        self._dragging   = False
        self._drag_id:   str | None = None
        self._ghost:     QLabel | None = None

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            idx = self.tabAt(ev.position().toPoint())
            if idx >= 0:
                self.detach_requested.emit(idx); return
        super().mouseDoubleClickEvent(ev)

    def contextMenuEvent(self, ev):
        idx = self.tabAt(ev.pos())
        if idx < 0:
            super().contextMenuEvent(ev); return
        pane = self.parent()   # _DraggableTabBar.parent() is TilePane
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
            pass
        menu.addAction("⬛ Split Right",   lambda: self.split_requested.emit(idx, "east"))
        menu.addAction("⬛ Split Down",    lambda: self.split_requested.emit(idx, "south"))
        menu.addAction("⬛ Split Left",    lambda: self.split_requested.emit(idx, "west"))
        menu.addAction("⬛ Split Up",      lambda: self.split_requested.emit(idx, "north"))
        menu.addSeparator()
        menu.addAction("↗ Move to Window",  lambda: self.detach_requested.emit(idx))
        menu.addSeparator()
        a_rename = menu.addAction("✎  Rename Tab")
        a_rename.triggered.connect(lambda: pane._rename_tab(idx))
        menu.addSeparator()
        menu.addAction("✕  Close Tab",            lambda: pane._close_tab(idx))
        menu.addAction("✕  Close Others",         lambda: pane.close_others_requested.emit(pane, idx))
        menu.addAction("✕  Close Tabs to Right",  lambda: pane.close_right_requested.emit(pane, idx))
        menu.addAction("✕  Close All in Pane",    lambda: pane.close_all_requested.emit(pane))
        menu.exec(ev.globalPos())

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._press_pt  = ev.position().toPoint()
            self._press_idx = self.tabAt(self._press_pt)
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if (not self._dragging
                and ev.buttons() & Qt.MouseButton.LeftButton
                and self._press_pt and self._press_idx >= 0
                and (ev.position().toPoint() - self._press_pt).manhattanLength()
                    >= QApplication.startDragDistance()):
            self._start_drag(self._press_idx)
        if self._dragging:
            gp = ev.globalPosition().toPoint()
            if self._ghost: self._ghost.move(gp.x()+14, gp.y()+8)
            tgt = self._pane_at(gp)
            ov  = _get_overlay()
            if tgt:
                ov.show_over(tgt, ov.zone_for_global(gp, tgt))
            else:
                ov.show_over(self, None)
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._dragging:
            gp  = ev.globalPosition().toPoint()
            tgt = self._pane_at(gp)
            ov  = _get_overlay()
            zone = ov.zone_for_global(gp, tgt) if tgt else None
            ov.show_over(self, None)
            self.releaseMouse()
            self._dragging = False
            if self._ghost:
                self._ghost.close(); self._ghost = None
            did = self._drag_id; self._drag_id = None
            self._press_pt = None; self._press_idx = -1
            if tgt and did and did in _DRAG_PAYLOAD:
                self.drop_on_pane.emit(tgt, did, zone or "center")
            else:
                _DRAG_PAYLOAD.pop(did, None)
        else:
            self._press_pt = None; self._press_idx = -1
            super().mouseReleaseEvent(ev)

    def _start_drag(self, idx: int):
        pane = self.parent()
        if not isinstance(pane, TilePane) or idx < 0 or idx >= pane.count():
            return
        did = str(uuid.uuid4())
        _DRAG_PAYLOAD[did] = {"source": pane, "widget": pane.widget(idx),
                               "text":   pane.tabText(idx)}
        self._drag_id  = did
        self._dragging = True
        label = QLabel(pane.tabText(idx).lstrip("🟡🟢🔴 "), None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint)
        label.setStyleSheet(
            "background:#1f6feb;color:white;padding:5px 12px;"
            "border-radius:4px;font-size:12px;")
        label.show(); self._ghost = label
        self.grabMouse()

    def _pane_at(self, gp: QPoint) -> "TilePane | None":
        for pane in self._pane_locator():
            if pane.rect().contains(pane.mapFromGlobal(gp)):
                return pane
        return None


# ── TilePane ──────────────────────────────────────────────────────────────────

class TilePane(QTabWidget):
    tab_count_changed    = pyqtSignal()
    tab_closed           = pyqtSignal(QWidget)
    detach_requested     = pyqtSignal(object, int)
    split_requested      = pyqtSignal(object, int, str)
    drop_received        = pyqtSignal(object, str, str)
    close_tab_requested  = pyqtSignal(object, int)        # pane, idx
    close_others_requested = pyqtSignal(object, int)      # close all except idx
    close_right_requested  = pyqtSignal(object, int)      # close tabs to right
    close_all_requested    = pyqtSignal(object)           # close all in pane

    def __init__(self, pane_locator, parent=None):
        super().__init__(parent)
        bar = _DraggableTabBar(pane_locator, self)
        bar.detach_requested.connect(lambda i: self.detach_requested.emit(self, i))
        bar.split_requested.connect(lambda i, d: self.split_requested.emit(self, i, d))
        bar.drop_on_pane.connect(lambda tgt, did, z: self.drop_received.emit(tgt, did, z))
        self.setTabBar(bar)
        self.setTabsClosable(True)
        self.setMovable(False)
        self.setAcceptDrops(False)
        self._is_active = True
        # Apply theme from saved prefs instead of hardcoded style
        self.setStyleSheet(self._current_tab_style(active=True))
        self.tabCloseRequested.connect(self._close_tab)
        self.currentChanged.connect(self._on_current_changed)

    @staticmethod
    def _current_tab_style(active: bool) -> str:
        """Build tab style from saved prefs — called on init and set_active."""
        try:
            from preferences_dialog import load_prefs, build_tab_style
            return build_tab_style(load_prefs(), active)
        except Exception:
            return TAB_STYLE_ACTIVE if active else TAB_STYLE_INACTIVE

    def set_active(self, active: bool):
        """Visual indicator — bright border when active, dimmed when not."""
        self._is_active = active
        self.setStyleSheet(self._current_tab_style(active))

    def apply_tab_style(self, active_style: str, inactive_style: str):
        """Re-apply tab styles (called when app theme changes)."""
        self.setStyleSheet(active_style if self._is_active else inactive_style)

    def _on_current_changed(self, idx: int):
        w = self.widget(idx)
        if w:
            QTimer.singleShot(50, w.setFocus)

    def _rename_tab(self, idx: int):
        from PyQt6.QtWidgets import QInputDialog
        current = self.tabText(idx)
        name, ok = QInputDialog.getText(
            self, "Rename Tab", "Tab name:", text=current)
        if ok and name.strip():
            self.setTabText(idx, name.strip())

    def _close_tab(self, idx: int):
        w = self.widget(idx)
        if w is None:
            return
        self.removeTab(idx)
        self.tab_closed.emit(w)
        if hasattr(w, "terminate"):
            w.terminate()
        w.deleteLater()
        self.tab_count_changed.emit()

    def repaint_terminals(self):
        """Force all terminals in this pane to re-fit after drag/reparent."""
        from PyQt6.QtCore import QTimer
        for i in range(self.count()):
            w = self.widget(i)
            if w and hasattr(w, '_view'):
                QTimer.singleShot(100, lambda v=w._view: v.page().runJavaScript(
                    "if(typeof doFit==='function')doFit();"))
