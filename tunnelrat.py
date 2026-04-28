#!/usr/bin/env python3
"""
SSH Manager — tabbed SSH session manager for Linux
"""
import argparse
import logging
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _parse_args():
    p = argparse.ArgumentParser(description="SSH Manager")
    p.add_argument("--debug", action="store_true",
                   help="Enable debug logging to stderr")
    p.add_argument("--log-file", metavar="PATH",
                   help="Write debug log to FILE instead of stderr")
    return p.parse_args()

def _setup_logging(debug: bool, log_file: str | None):
    level = logging.DEBUG if debug else logging.INFO
    handlers = []
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    else:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=level, handlers=handlers, format=fmt)

def main():
    args = _parse_args()
    _setup_logging(args.debug, args.log_file)

    # Save terminal state now and restore it on exit.
    # Prevents terminal going no-echo if something (e.g. puttygen, paramiko)
    # corrupts tty settings and the app exits without restoring them.
    import atexit
    try:
        import termios
        _orig_tty = termios.tcgetattr(sys.stdin.fileno())
        atexit.register(
            lambda: termios.tcsetattr(
                sys.stdin.fileno(), termios.TCSADRAIN, _orig_tty)
        )
    except Exception:
        pass  # Not a tty (piped/redirected) — skip

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("TunnelRAT")
    app.setOrganizationName("tunnelrat")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
