# 🐀 TunnelRAT

**A thousand servers. One rat.**

![TunnelRAT](icons/tunnelrat_256.png)

---

## The Story

I've been running Linux since Red Hat 6 — the original, from 1998. Not a hobbyist. A lifelong Linux user who has spent decades in the trenches as a systems administrator.

Today I manage over 1,000 Unix servers. For years, the tool that made that manageable on Windows was SuperPutty — tabbed sessions, tiled panes, broadcast commands to hundreds of servers at once. It was indispensable.

When I made the full switch to Linux on my workstation, I went looking for the equivalent. I was genuinely shocked to find it didn't exist. SuperPutty wouldn't run properly under Wine. Everything else was either a basic terminal emulator with tabs or a paid product that didn't come close. There was simply no native Linux SSH session manager worthy of the name.

So I built one.

TunnelRAT is SuperPutty for Linux — fully compatible with SuperPutty session exports, built around the real OpenSSH binary, with every feature a serious sysadmin needs. It was built out of necessity, tested in production managing real infrastructure, and released to the Linux community that gave me a 25+ year career.

— *Evan (unixsmith)*

---

## Why TunnelRAT?

If you've ever tried to use SuperPutty on Linux you know the pain — Wine, broken rendering on HiDPI displays, missing features, crashes. Nothing else comes close to what SuperPutty offered Windows users: tabbed sessions, tiled panes, and most importantly, **broadcast commands to multiple servers simultaneously**.

TunnelRAT fills that gap natively:

- Wraps the **real OpenSSH binary** — sudo, su, tmux, screen, vim, key auth, certificates, ProxyJump, `~/.ssh/config` — all just work
- **SuperPutty Sessions.XML import** — migrate your existing sessions in one click
- **Broadcast commands** to multiple sessions at once — mass login, mass sudo, mass anything
- **Mass Ctrl+C** — send SIGINT to all targeted sessions simultaneously from the broadcast bar
- **Drag-to-tile** pane splitting — split right, down, left, up, detach to floating window
- Full **theme system** — 13 terminal themes, 13 app themes, custom colors, save/export/import
- Configurable **hotkeys** for everything
- **Layouts** — save and restore your session arrangements

---

## Screenshots

<!-- Add screenshots here -->

---

## Features

### Session Management
- Tabbed SSH sessions with live connection status indicators
- Session groups with custom color coding
- Search/filter session tree
- Quick Connect — connect without saving
- Import from SuperPutty XML or TunnelRAT JSON — export to JSON
- Passwords encrypted at rest (Fernet/AES-128)
- SSH key, certificate, and PPK support (auto-converts via puttygen)
- Jump host / ProxyJump support
- Per-session keepalive, extra SSH args, and notes
- Group management — rename, recolor, delete groups

### Tiling & Windows
- Drag tabs to split panes (Right / Down / Left / Up)
- Detach tabs to floating windows, re-dock back
- Active pane visual indicator
- Rename tabs manually or dynamically via remote shell title sequences
- Close Tab / Close Others / Close to Right / Close All in Pane
- Fullscreen mode (F11) — fills screen, all UI stays visible
- Always on Top

### Broadcast
- Send commands to any subset of open sessions simultaneously
- **Mass Ctrl+C** — press Ctrl+C in the broadcast bar to send SIGINT to all targeted sessions instantly, no Enter required
- Mass login — open sessions, type password once in broadcast bar, all sessions authenticate
- Mass sudo — broadcast sudo password to all targeted sessions
- Paste Script — paste or type a multi-line script, run on all targets
- Load Script — pick a script file, broadcast it line by line
- Command mask — hide sensitive input (🔒) for password broadcasts
- Precision targeting — select exactly which sessions receive each command

### Themes

**13 Terminal Themes:**

| Dark | Light |
|------|-------|
| Dark (Default) | Light |
| Dracula | Solarized Light |
| Monokai | Catppuccin Latte |
| One Dark | |
| Tokyo Night | |
| Catppuccin Mocha | |
| Gruvbox Dark | |
| Nord | |
| Solarized Dark | |
| Midnight | |

**13 matching Application Themes** — every terminal theme has a corresponding app theme that styles the entire UI: toolbar, session tree, tab bar, broadcast bar, dialogs, and all input widgets.

Full custom color picker for all 16 terminal colors + application chrome. Save, export, and import themes as JSON. Live preview with Apply button.

### Hotkeys
- All actions configurable via Preferences → Hotkeys
- Default shortcuts: `Ctrl+Tab` (next tab), `Ctrl+Shift+Tab` (prev tab), `F11` (fullscreen), `F2` (rename tab), `Ctrl+Shift+8` (command mask), `Ctrl+S` (save layout), and more
- Ctrl+C, Ctrl+Z, Ctrl+D, Ctrl+L, Ctrl+U and other terminal control sequences work correctly inside the terminal
- Ctrl+C in the broadcast bar sends SIGINT to all targeted sessions simultaneously

### Layouts
- Save your current split arrangement as a named layout
- Restore layouts to reopen sessions in the same configuration
- Delete layouts you no longer need

### Scrollback
- 10,000 lines of scrollback per terminal
- Scroll up to reference any previous output
- Themed scrollbar

---

## Requirements

- Linux (tested on Fedora 44; should work on any modern distro)
- Python 3.10+
- OpenSSH (`ssh` binary in `$PATH`)
- PyQt6 + PyQt6-WebEngine
- `websockets`, `cryptography` Python packages

> **macOS:** The architecture is fully POSIX-compatible. Should work with minor install script adjustments — untested.

---

## Installation

```bash
git clone https://github.com/datawarp/tunnelrat.git
cd tunnelrat
bash install.sh
```

Then run:
```bash
tunnelrat
```

Or launch from your application menu under **Internet → TunnelRAT**.

### Manual dependency install (if needed)

**Fedora / RHEL:**
```bash
sudo dnf install python3-pip python3-PyQt6 python3-pyqt6-webengine
pip install --user websockets cryptography
```

**Debian / Ubuntu:**
```bash
sudo apt install python3-pip python3-pyqt6 python3-pyqt6.qtwebengine
pip install --user websockets cryptography
```

---

## First Run

On first launch, import your existing sessions via **File → Import Sessions…**

Supports both **SuperPutty `Sessions.XML`** and **TunnelRAT JSON** export format.

Or create sessions manually via **Session → New Session**.

---

## Uninstall

```bash
bash uninstall.sh
```

---

## Architecture

TunnelRAT wraps the system `ssh` binary inside a real OS PTY (`pty.openpty()`), bridging it to an [xterm.js](https://xtermjs.org/) terminal via a local WebSocket server. Each session is a genuine `ssh` subprocess — not paramiko, not a reimplementation.

```
xterm.js ←→ WebSocket ←→ Python PTY bridge ←→ /usr/bin/ssh ←→ remote server
```

Password delivery uses atomic PTY writes — the password is written as a single `os.write()` call, which is required for reliable authentication through a PTY. This is why sudo, su, and SSH login all work correctly where other tools fail.

---

## Roadmap

- [ ] macOS support (architecture is compatible; install script needs a macOS branch)
- [ ] AUR package
- [ ] Flatpak / Flathub
- [ ] Rust/Tauri rewrite (v2.0) — same architecture, compiled binary, ~10MB footprint

---

## Contributing

Contributions welcome. Please open an issue before submitting a large PR so we can discuss the approach.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Credits

- **Logo** — designed by Autumn S.
- **Built with** — Python, PyQt6, xterm.js, OpenSSH
- **Inspired by** — SuperPutty (the Windows SSH manager Linux users have always envied)

---

*A thousand servers. One rat.* 🐀
