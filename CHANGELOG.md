# Changelog

All notable changes to TunnelRAT will be documented here.

---

## [0.1.0] — 2026-04-27 — Initial Release

### 🐀 First public release

TunnelRAT v0.1.0 is the first public release — a native Linux SSH session manager
built as a drop-in replacement for SuperPutty.

### Core Features
- Tabbed SSH sessions via xterm.js + WebSocket + real OpenSSH PTY bridge
- Drag-to-tile split panes (Right / Down / Left / Up)
- Detach tabs to floating windows, re-dock back
- Session tree with groups and custom color coding
- Session search/filter
- Active pane visual indicator

### Session Management
- Create, edit, duplicate, delete sessions
- Group management — create, rename, recolor, delete groups
- Import from SuperPutty Sessions.XML
- Import/Export TunnelRAT native JSON format
- Quick Connect (connect without saving)
- SSH key, certificate, and PPK support (auto-converts via puttygen)
- Jump host / ProxyJump support
- Per-session keepalive, extra SSH args, and notes
- Passwords encrypted at rest (Fernet/AES-128)

### Broadcast
- Send commands to any subset of open sessions simultaneously
- Mass login — type password once, all sessions authenticate
- Mass sudo — broadcast sudo password to all targeted sessions
- Ctrl+C in broadcast bar sends SIGINT to all targeted sessions instantly
- Ctrl+Z, Ctrl+D, Ctrl+L, Ctrl+U also supported in broadcast bar
- Paste Script — multi-line script broadcast
- Load Script — broadcast from file
- Command mask (👁/🔒) — hide sensitive input
- Precision targeting — select exactly which sessions receive each command

### Themes
- 13 terminal theme presets: Dark (Default), Dracula, Monokai, One Dark,
  Tokyo Night, Catppuccin Mocha, Gruvbox Dark, Nord, Solarized Dark,
  Midnight, Light, Solarized Light, Catppuccin Latte
- 13 matching application theme presets
- Full custom color picker for all 16 terminal colors + app chrome
- Save, export, and import themes as JSON
- Live theme preview with Apply button

### Hotkeys
- All actions configurable via Preferences → Hotkeys
- Ctrl+C/Z/D/L/U work correctly inside terminals (intercepted before Chromium)
- 13 configurable actions with QKeySequenceEdit
- Reset to Defaults button

### Layouts
- Save named layouts (split arrangements + open sessions)
- Restore layouts on demand
- Delete saved layouts

### Terminal
- 10,000 line scrollback with themed scrollbar
- Dynamic tab titles from remote shell OSC sequences
- Rename tabs manually
- Font family, size, and line height configurable

### Other
- Fullscreen mode (F11) — fills screen, all UI stays accessible
- Always on Top
- Status bar showing session count and open count
- Logo designed by Autumn S.
- MIT License

---

*"A thousand servers. One rat."* 🐀
