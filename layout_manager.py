"""
layout_manager.py — Save and restore TunnelRAT window layouts.

A layout captures:
  - The splitter tree structure (orientation, sizes, nesting)
  - Which session is in each tab slot, and which tab is active
  - Main window geometry

Layouts are saved to ~/.config/tunnelrat/layouts/<name>.json
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

from PyQt6.QtCore import QByteArray
from PyQt6.QtWidgets import QSplitter, QWidget

log = logging.getLogger(__name__)

LAYOUTS_DIR = Path.home() / ".config" / "tunnelrat" / "layouts"


# ── Serialise ─────────────────────────────────────────────────────────────────

def _serialise_widget(widget: QWidget) -> dict | None:
    """Recursively serialise a TilePane or QSplitter node."""
    from tile_pane import TilePane
    if isinstance(widget, TilePane):
        tabs = []
        for i in range(widget.count()):
            w = widget.widget(i)
            sid = getattr(w, "_session_id", None)
            name = widget.tabText(i)
            tabs.append({"sid": sid, "name": name})
        return {
            "type": "pane",
            "active": widget.currentIndex(),
            "tabs": tabs,
        }
    elif isinstance(widget, QSplitter):
        children = []
        for i in range(widget.count()):
            child = _serialise_widget(widget.widget(i))
            if child:
                children.append(child)
        return {
            "type":        "splitter",
            "orientation": "horizontal" if widget.orientation().name == "Horizontal" else "vertical",
            "sizes":       widget.sizes(),
            "children":    children,
        }
    return None


def save_layout(name: str, tile_manager, main_window) -> Path:
    """Save current layout to ~/.config/tunnelrat/layouts/<name>.json"""
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)

    root_widget = tile_manager._root_widget()
    tree = _serialise_widget(root_widget) if root_widget else None

    geom = main_window.saveGeometry().toBase64().data().decode()

    layout = {
        "name":     name,
        "geometry": geom,
        "tree":     tree,
    }
    path = LAYOUTS_DIR / f"{name}.json"
    path.write_text(json.dumps(layout, indent=2))
    log.debug("Layout saved: %s", path)
    return path


# ── Deserialise ───────────────────────────────────────────────────────────────

def restore_layout(name: str, tile_manager, main_window, session_manager) -> bool:
    """Restore a saved layout. Returns True on success."""
    path = LAYOUTS_DIR / f"{name}.json"
    if not path.exists():
        log.warning("Layout not found: %s", path)
        return False
    try:
        layout = json.loads(path.read_text())
    except Exception as e:
        log.error("Failed to read layout %s: %s", path, e)
        return False

    # Restore geometry
    if layout.get("geometry"):
        try:
            geom = QByteArray.fromBase64(layout["geometry"].encode())
            main_window.restoreGeometry(geom)
        except Exception:
            pass

    # Open sessions from tree
    tree = layout.get("tree")
    if tree:
        _open_sessions_from_tree(tree, tile_manager, session_manager)

    return True


def _open_sessions_from_tree(node: dict, tile_manager, session_manager):
    """Walk the saved tree and open sessions into panes."""
    if node["type"] == "pane":
        for tab in node.get("tabs", []):
            sid = tab.get("sid")
            if not sid:
                continue
            # Find session by matching the session_id prefix or name
            session = _find_session(session_manager, tab.get("name", ""), sid)
            if session:
                try:
                    tile_manager.open_session(session)
                except Exception as e:
                    log.debug("Could not restore session %s: %s", tab.get("name"), e)
    elif node["type"] == "splitter":
        for child in node.get("children", []):
            _open_sessions_from_tree(child, tile_manager, session_manager)


def _find_session(session_manager, name: str, sid: str):
    """Find a session by name (layouts store session name, not live sid)."""
    sessions = session_manager.sessions
    # Try exact name match first
    for s in sessions.values():
        if s.display_name() == name or s.name == name:
            return s
    # Fallback: partial name match
    name_lower = name.lower()
    for s in sessions.values():
        if name_lower in s.display_name().lower():
            return s
    return None


# ── List available layouts ────────────────────────────────────────────────────

def list_layouts() -> list[str]:
    """Return names of all saved layouts."""
    if not LAYOUTS_DIR.exists():
        return []
    return sorted(p.stem for p in LAYOUTS_DIR.glob("*.json"))


def delete_layout(name: str) -> bool:
    path = LAYOUTS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False
