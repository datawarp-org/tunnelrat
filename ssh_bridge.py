"""
ssh_bridge.py — HTTP + WebSocket + real ssh binary bridge for TunnelRAT.

Architecture:
  HTTP server  — serves terminal HTML (real http:// fixes WebEngine keyboard focus)
  WS server    — bidirectional PTY ↔ xterm.js data pump

Each terminal session spawns the system ssh binary inside a real OS PTY via
pty.openpty(). sudo, su, passwd, tmux, screen, vim — everything works exactly
as in a normal terminal because it IS a normal terminal.

PTY reader uses loop.add_reader() — proper async I/O, no thread-pool races,
no select() EBADF issues during sudo/PAM process transitions.

Broadcast: os.write() directly to PTY master fd.
Session hold/resume: PTY process keeps running across WS reconnects.
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import pty
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import termios
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)


# ── Terminal HTML ─────────────────────────────────────────────────────────────
TERMINAL_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%;background:#0d1117;overflow:hidden}
#t{width:100%;height:100%}
.xterm{height:100%!important}
.xterm-viewport{overflow-y:scroll!important}
.xterm-viewport::-webkit-scrollbar{width:8px}
.xterm-viewport::-webkit-scrollbar-track{background:transparent}
.xterm-viewport::-webkit-scrollbar-thumb{background:#30363d;border-radius:4px}
.xterm-viewport::-webkit-scrollbar-thumb:hover{background:#484f58}
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css"/>
<script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.js"></script>
</head>
<body>
<div id="t"></div>
<script>
const SID='%%SESSION_ID%%', WS_PORT='%%WS_PORT%%';

const PREFS = %%PREFS_JSON%%;
const term = new Terminal({
  theme: PREFS.theme,
  fontFamily: PREFS.fontFamily,
  fontSize: PREFS.fontSize,
  lineHeight: PREFS.lineHeight,
  cursorBlink:true,scrollback:10000,
  allowTransparency:false,
});

const fit = new FitAddon.FitAddon();
term.loadAddon(fit);
try{term.loadAddon(new WebLinksAddon.WebLinksAddon());}catch(e){}
term.open(document.getElementById('t'));

let ws=null, wsReady=false;
const pending=[];

function doFit(){
  try{
    fit.fit();
    var msg=JSON.stringify({type:'resize',cols:term.cols,rows:term.rows});
    if(wsReady) ws.send(msg); else pending.push(msg);
  }catch(e){}
}

function connect(){
  ws=new WebSocket('ws://127.0.0.1:'+WS_PORT+'/'+SID);
  ws.binaryType='arraybuffer';
  ws.onopen=function(){
    wsReady=true;
    pending.forEach(function(d){ws.send(d);}); pending.length=0;
    doFit(); term.focus();
  };
  ws.onmessage=function(e){
    if(e.data instanceof ArrayBuffer){ term.write(new Uint8Array(e.data)); return; }
    try{
      var m=JSON.parse(e.data);
      if(m.type==='status'){
        term.write('\r\n\x1b['+(m.ok?'32':'31')+'m[TunnelRAT] '+m.text+'\x1b[0m\r\n');
        if(m.ok) term.focus();
        return;
      }
      if(m.type==='auth_prompt'){
        // Used before spawn (pre-PTY) - display prompt + enter buffering mode
        authMode=true; authBuf='';
        term.write('\r\n\x1b[33m'+m.prompt+'\x1b[0m');
        return;
      }
      if(m.type==='auth_mode'){
        // Prompt already shown by PTY - just enter silent buffering mode
        authMode=true; authBuf='';
        return;
      }
      if(m.type==='auth_done'){
        // Password delivered - exit auth mode unconditionally
        authMode=false; authBuf='';
        return;
      }
    }catch(ex){}
    term.write(e.data);
  };
  ws.onclose=function(){ wsReady=false; };
  ws.onerror=function(){
    term.write('\r\n\x1b[31m[TunnelRAT] connection error\x1b[0m\r\n');
  };
}

/* Password buffering mode.
   When auth_prompt is received, authMode=true. Keystrokes are buffered
   locally with no echo. On Enter the complete password is sent as one
   JSON message so Python can write it atomically to the PTY.
   Atomic write is required — character-by-character writes fail for
   password authentication through pty.openpty(). */
var authMode=false, authBuf='';
/* Intercept control keys before Chromium/WebEngine grabs them.
   Ctrl+C = \x03 (SIGINT), Ctrl+Z = \x1a (SIGTSTP), Ctrl+D = \x04 (EOF)
   Ctrl+\ = \x1c (SIGQUIT). Without this, Chromium swallows Ctrl+C for copy. */
term.attachCustomKeyEventHandler(function(e){
  if(e.type !== 'keydown') return true;
  if(e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey){
    var ch = e.key.toLowerCase();
    var sigMap = {c:'\x03', z:'\x1a', d:'\x04', q:'\x11',
                  a:'\x01', e:'\x05', k:'\x0b', u:'\x15',
                  l:'\x0c', r:'\x12', w:'\x17'};
    if(sigMap[ch]){
      if(authMode){ authMode=false; authBuf=''; }
      if(wsReady) ws.send(sigMap[ch]);
      return false; /* prevent browser default */
    }
  }
  return true;
});

term.onData(function(d){
  if(authMode){
    if(d==='\r'||d==='\n'){
      authMode=false;
      term.write('\r\n');
      if(wsReady) ws.send(JSON.stringify({type:'auth_response',value:authBuf}));
      authBuf='';
    } else if(d==='\x7f'||d==='\x08'){
      if(authBuf.length>0){ authBuf=authBuf.slice(0,-1); term.write('\b \b'); }
    } else if(d==='\x03'||d==='\x1a'||d==='\x04'){
      /* Ctrl+C/Z/D during auth mode cancels it */
      authMode=false; authBuf='';
      if(wsReady) ws.send(d);
    } else {
      authBuf+=d; /* no echo */
    }
    return;
  }
  if(wsReady) ws.send(d);
  else pending.push(d);
});

term.onResize(function(s){
  if(wsReady) ws.send(JSON.stringify({type:'resize',cols:s.cols,rows:s.rows}));
});

document.getElementById('t').addEventListener('click', function(){ term.focus(); });
new ResizeObserver(function(){ doFit(); }).observe(document.getElementById('t'));
window.addEventListener('load',function(){ setTimeout(function(){doFit();connect();},150); });
</script>
</body>
</html>
"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

def _build_xterm_theme_dict(prefs: dict) -> dict:
    """Build xterm.js theme dict from prefs — serializable to JSON."""
    return {
        "background":        prefs.get("background",  "#0d1117"),
        "foreground":        prefs.get("foreground",  "#c9d1d9"),
        "cursor":            prefs.get("cursor",      "#58a6ff"),
        "cursorAccent":      prefs.get("background",  "#0d1117"),
        "selectionBackground": prefs.get("selection", "rgba(88,166,255,0.28)"),
        "black":             prefs.get("black",        "#484f58"),
        "red":               prefs.get("red",          "#ff7b72"),
        "green":             prefs.get("green",        "#3fb950"),
        "yellow":            prefs.get("yellow",       "#d29922"),
        "blue":              prefs.get("blue",         "#58a6ff"),
        "magenta":           prefs.get("magenta",      "#bc8cff"),
        "cyan":              prefs.get("cyan",         "#39c5cf"),
        "white":             prefs.get("white",        "#b1bac4"),
        "brightBlack":       prefs.get("bright_black", "#6e7681"),
        "brightRed":         prefs.get("bright_red",   "#ffa198"),
        "brightGreen":       prefs.get("bright_green", "#56d364"),
        "brightYellow":      prefs.get("bright_yellow","#e3b341"),
        "brightBlue":        prefs.get("bright_blue",  "#79c0ff"),
        "brightMagenta":     prefs.get("bright_magenta","#d2a8ff"),
        "brightCyan":        prefs.get("bright_cyan",  "#56d4dd"),
        "brightWhite":       prefs.get("bright_white", "#f0f6fc"),
    }


def _css_font_stack(font_family: str) -> str:
    """Convert comma-separated font list to CSS font-family value for xterm.js."""
    fonts = [f.strip() for f in font_family.split(",") if f.strip()]
    if not fonts:
        return "monospace"
    parts = []
    for f in fonts:
        if " " in f:
            parts.append(f"'{f}'")
        else:
            parts.append(f)
    return ", ".join(parts)


class _HTMLHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from preferences_dialog import load_prefs, build_xterm_theme
            p    = parse_qs(urlparse(self.path).query)
            sid  = p.get('sid',  [''])[0]
            port = p.get('port', [''])[0]
            prefs = load_prefs()
            # Build prefs JSON for xterm.js — inject as a single object
            # to avoid any string template substitution issues
            import json as _json
            fallback_stack = "JetBrains Mono,Cascadia Code,Fira Code,SF Mono,Menlo,Consolas,monospace"
            font_fam = prefs.get("font_family", fallback_stack)
            # Ensure full fallback stack is always present
            if "," not in font_fam:
                font_fam = font_fam + "," + fallback_stack
            prefs_js = _json.dumps({
                "theme":      _build_xterm_theme_dict(prefs),
                "fontFamily": font_fam,
                "fontSize":   int(prefs.get("font_size", 13)),
                "lineHeight": round(float(prefs.get("line_height", 1.2)), 2),
            })
            html = (TERMINAL_HTML
                    .replace('%%SESSION_ID%%', sid)
                    .replace('%%WS_PORT%%',    port)
                    .replace('%%PREFS_JSON%%', prefs_js))
            data = html.encode()
            self.send_response(200)
            self.send_header('Content-Type',  'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control',  'no-cache')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            log.debug("HTTP handler: %s", e)
    def log_message(self, *a): pass


# ── PTY session state ─────────────────────────────────────────────────────────

class _PTYConn:
    def __init__(self):
        self.proc:          subprocess.Popen | None = None
        self.master_fd:     int | None = None
        self.output_buffer: bytearray = bytearray()
        self.buf_max:       int = 65536
        self.askpass_path:  str | None = None
        self.websocket:     object | None = None  # active WS, for auth_done delivery


# ── Bridge singleton ──────────────────────────────────────────────────────────

class SSHBridge(QObject):
    session_status       = pyqtSignal(str, str)  # sid, status
    password_needed      = pyqtSignal(str, str)  # sid, SSH login prompt
    sudo_password_needed = pyqtSignal(str, str)  # sid, sudo prompt
    tab_title_changed    = pyqtSignal(str, str)  # sid, new title

    _instance: "SSHBridge | None" = None

    @classmethod
    def instance(cls) -> "SSHBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._ws_port   = self._free_port()
        self._http_port = self._free_port()
        self._sessions: dict = {}
        self._conns:    dict = {}
        self._held:     set  = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._password_events: dict = {}  # sid → (threading.Event, list[str])

        http = HTTPServer(('127.0.0.1', self._http_port), _HTMLHandler)
        threading.Thread(target=http.serve_forever, daemon=True,
                         name="TR-HTTP").start()
        threading.Thread(target=self._run_loop, daemon=True,
                         name="TR-WS").start()
        self._ready.wait(timeout=5)
        log.debug("SSHBridge ready  http=%d  ws=%d", self._http_port, self._ws_port)

    @property
    def port(self) -> int:      return self._ws_port
    @property
    def http_port(self) -> int: return self._http_port

    def register(self, sid: str, session):
        self._sessions[sid] = session

    def hold_session(self, sid: str):
        self._held.add(sid)

    def release_session(self, sid: str):
        self._held.discard(sid)

    def unregister(self, sid: str):
        self._sessions.pop(sid, None)
        self._held.discard(sid)
        conn = self._conns.pop(sid, None)
        if conn:
            self._close_conn(conn)

    def send_data(self, sid: str, data: str):
        """
        Broadcast: write data to the PTY master fd atomically.
        After writing, send auth_done to xterm.js so it exits auth_mode
        (which was entered when the password prompt was detected).
        Without this, xterm.js stays in silent-buffering mode after
        broadcast-based login and keystrokes appear invisible.
        """
        conn = self._conns.get(sid)
        if conn and conn.master_fd is not None:
            try:
                os.write(conn.master_fd, data.encode())
            except OSError as e:
                log.warning("send_data %s: %s", sid[:8], e)
                return
            # Send auth_done so xterm.js exits auth_mode after broadcast password
            if conn.websocket is not None:
                import asyncio as _aio
                async def _send_done(ws):
                    try:
                        await ws.send('{"type":"auth_done"}')
                    except Exception:
                        pass
                try:
                    loop = self._loop
                    if loop and loop.is_running():
                        _aio.run_coroutine_threadsafe(_send_done(conn.websocket), loop)
                except Exception:
                    pass

    def provide_password(self, sid: str, password: str):
        """Called from Qt main thread after user enters password in dialog."""
        entry = self._password_events.get(sid)
        if entry:
            event, store = entry
            store.append(password)
            event.set()

    # ── asyncio loop ──────────────────────────────────────────────────────────

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        try:
            import websockets
        except ImportError:
            log.error("websockets not installed"); self._ready.set(); return

        async def handler(websocket, *args):
            path = None
            for src in [lambda: args[0] if args else None,
                        lambda: getattr(websocket, 'path', None),
                        lambda: websocket.request.path]:
                try:
                    v = src()
                    if v: path = v; break
                except Exception: pass
            sid = (path or '/').lstrip('/').split('?')[0]
            await self._handle_terminal(websocket, sid)

        try:
            async with websockets.serve(
                handler, "127.0.0.1", self._ws_port,
                ping_interval=None,   # disable keepalive pings
                ping_timeout=None,    # never time out
                max_size=10*1024*1024 # 10MB max message
            ):
                self._ready.set()
                await asyncio.Future()
        except Exception as e:
            log.error("WS server: %s", e); self._ready.set()

    # ── WebSocket / PTY handler ───────────────────────────────────────────────

    async def _handle_terminal(self, websocket, sid: str):
        session = self._sessions.get(sid)
        if not session:
            await self._ws_status(websocket, False, f"Unknown session: {sid[:8]}")
            return

        loop = asyncio.get_event_loop()

        # ── Resume held PTY ────────────────────────────────────────────────
        existing = self._conns.get(sid)
        if existing and existing.proc and existing.proc.poll() is None \
                and existing.master_fd is not None:
            conn = existing
            conn.websocket = websocket
            self.session_status.emit(sid, "connected")
            await self._ws_status(websocket, True, f"Resumed {session.host}")
            if conn.output_buffer:
                try:
                    await websocket.send(bytes(conn.output_buffer))
                except Exception:
                    pass
        else:
            # ── Spawn new ssh immediately ──────────────────────────────────
            # No pre-spawn password collection. ssh prompts on the PTY when
            # needed. pty_reader detects prompts and handles delivery:
            #   - stored password → auto-written atomically
            #   - no stored password → auth_mode sent to xterm.js so user
            #     can type in terminal OR broadcast can deliver the password
            conn = _PTYConn()
            err  = await loop.run_in_executor(
                None, self._spawn_ssh, conn, session, sid)
            if err:
                await self._ws_status(websocket, False, err)
                self.session_status.emit(sid, "failed")
                return
            self._conns[sid] = conn
            conn.websocket = websocket
            try:
                session.last_connected = datetime.now(timezone.utc).isoformat()
            except Exception:
                pass
            self.session_status.emit(sid, "connected")
            await self._ws_status(websocket, True, f"Connected to {session.host}")

        master_fd = conn.master_fd

        # ── PTY → WS reader using loop.add_reader() ────────────────────────
        # This is the correct async approach for PTY fds.
        # loop.add_reader() uses epoll — no threads, no select() EBADF races,
        # no proc.poll() checks that can misfire during sudo/PAM transitions.
        # The callback fires only when the OS says data is available.
        # EIO (errno 5) from os.read() means all PTY slaves closed — ssh exited.
        data_queue: asyncio.Queue = asyncio.Queue()

        def _pty_readable():
            try:
                data = os.read(master_fd, 4096)
                # Empty read on PTY = treat as no-data, not EOF
                if data:
                    data_queue.put_nowait(data)
            except BlockingIOError:
                pass   # EAGAIN — spurious wakeup, no data yet
            except OSError as _e:
                # EIO — all slave fds closed, ssh has exited
                import errno as _errno
                rc = conn.proc.poll() if conn.proc else "?"
                log.error("PTY EIO errno=%s — ssh exited (rc=%s)", _e.errno, rc)
                data_queue.put_nowait(None)
            except Exception as e:
                log.debug("PTY read callback: %s", e)

        # Make master_fd non-blocking so os.read never hangs in the callback
        try:
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        except Exception as e:
            log.debug("fcntl non-blocking: %s", e)

        loop.add_reader(master_fd, _pty_readable)

        async def pty_reader():
            try:
                while True:
                    item = await data_queue.get()
                    if item is None:
                        rc = conn.proc.poll() if conn.proc else '?'
                        log.error("SSH process ended rc=%s host=%s", rc, session.host)
                        # Close the WebSocket so the WS pump loop exits
                        # and the finally block runs (tab goes red).
                        try:
                            await websocket.close()
                        except Exception:
                            pass
                        break
                    conn.output_buffer.extend(item)
                    if len(conn.output_buffer) > conn.buf_max:
                        conn.output_buffer = conn.output_buffer[-conn.buf_max:]
                    try:
                        await websocket.send(item)
                    except Exception:
                        break
                    # ── Prompt interception ───────────────────────────────
                    # Detect password/passphrase prompts in PTY output.
                    # For stored passwords: write atomically and silently.
                    # For no stored password: send auth_mode to put xterm.js
                    # in silent buffering mode. The WS pump then receives
                    # the auth_response and writes it atomically.
                    # We NEVER call websocket.recv() from pty_reader —
                    # the WS pump is the sole reader of websocket messages.
                    try:
                        text = item.decode(errors="replace")
                        if self._is_password_prompt(text):
                            import re
                            # SSH login prompt with stored password → auto-deliver
                            if (re.search(r"'s password:", text, re.IGNORECASE)
                                    and session.password):
                                try:
                                    os.write(conn.master_fd,
                                             (session.password + "\r").encode())
                                    log.debug("Auto-delivered stored password")
                                except OSError as e:
                                    log.error("Auto-password write: %s", e)
                                # No auth_mode was entered, no auth_done needed
                            else:
                                # No stored password — put xterm.js in silent
                                # buffering mode. User types, WS pump delivers.
                                try:
                                    await websocket.send(
                                        json.dumps({"type": "auth_mode"}))
                                except Exception:
                                    pass
                    except Exception as e:
                        log.debug("Prompt detection: %s", e)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                log.error("pty_reader exception: %s", e)
            finally:
                try:
                    loop.remove_reader(master_fd)
                except Exception:
                    pass

        reader = asyncio.ensure_future(pty_reader())

        # ── WS → PTY pump ──────────────────────────────────────────────────
        # CRITICAL: every message is wrapped in its own try/except so that
        # no per-message exception can exit the async-for loop and cause
        # the finally block to close the session. The outer except only
        # triggers if the WebSocket itself closes (which is correct).
        try:
            async for message in websocket:
                try:
                    if isinstance(message, bytes):
                        os.write(master_fd, message)
                    elif isinstance(message, str):
                        try:
                            msg = json.loads(message)
                            if isinstance(msg, dict):
                                t = msg.get('type', '')
                                if t == 'resize':
                                    cols = max(1, int(msg.get('cols') or 80))
                                    rows = max(1, int(msg.get('rows') or 24))
                                    self._resize_pty(master_fd, cols, rows)
                                elif t == 'auth_response':
                                    # Password collected by xterm.js auth_mode.
                                    # Write as ONE atomic os.write — required for
                                    # reliable password auth through PTY.
                                    pw = msg.get('value', '')
                                    if pw and conn.master_fd is not None:
                                        try:
                                            os.write(conn.master_fd,
                                                     (pw + '\r').encode())
                                            log.debug("auth_response atomic write OK")
                                        except OSError as e:
                                            log.error("auth_response write: %s", e)
                                    # Exit auth mode in xterm.js unconditionally
                                    # so terminal input is always visible after
                                    try:
                                        await websocket.send(
                                            json.dumps({"type": "auth_done"}))
                                    except Exception:
                                        pass
                                    # Also satisfy any pending broadcast event
                                    auth_key = f"auth_{sid}"
                                    entry = self._password_events.get(auth_key)
                                    if entry:
                                        ev, store = entry
                                        store.append(pw)
                                        ev.set()
                            else:
                                # json.loads gave a non-dict (e.g. '0'→0, '1'→1)
                                # These are digit keystrokes — write as-is
                                os.write(master_fd, message.encode())
                        except (json.JSONDecodeError, ValueError):
                            # Not JSON — raw keystroke string from xterm.js
                            os.write(master_fd, message.encode())
                except Exception as e:
                    # Per-message error — log and CONTINUE, never exit the loop
                    log.debug("WS→PTY message error (continuing): %s", e)
        except Exception as e:
            log.error("WS pump exited %s: %s", session.host, e)
        finally:
            reader.cancel()
            if sid in self._held:
                log.debug("PTY held: %s", sid[:8])
            else:
                self._close_conn(conn)
                self._conns.pop(sid, None)
                try:
                    self.session_status.emit(sid, "closed")
                except RuntimeError:
                    pass  # Qt object already deleted (app shutting down)

    # ── SSH spawn ─────────────────────────────────────────────────────────────

    def _spawn_ssh(self, conn: _PTYConn, session, sid: str = "") -> str | None:
        import stat, tempfile
        ssh = shutil.which("ssh")
        if not ssh:
            return "ssh binary not found — install openssh-clients"

        cmd = self._build_ssh_cmd(ssh, session)
        log.debug("SSH cmd: %s", " ".join(cmd))

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        # Passwords are delivered through the PTY by pty_reader prompt
        # detection — no SSH_ASKPASS needed.

        try:
            master_fd, slave_fd = pty.openpty()
            self._resize_pty(master_fd, 220, 50)
            # Leave PTY in default state — pty.openpty() gives a standard
            # cooked terminal. Custom TERMIOS init causes issues on WSL.

            def _child_setup():
                os.setsid()
                try:
                    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
                except Exception:
                    pass

            proc = subprocess.Popen(
                cmd,
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                close_fds=True,
                env=env,
                preexec_fn=_child_setup,
            )
            os.close(slave_fd)

            conn.proc      = proc
            conn.master_fd = master_fd
            return None

        except Exception as e:
            log.error("ssh spawn: %s", e)
            return f"Failed to spawn ssh: {e}"

    @staticmethod
    def _build_ssh_cmd(ssh_bin: str, session) -> list[str]:
        cmd = [ssh_bin, "-p", str(session.port), "-t", "-t"]
        cmd += ["-o", "ControlMaster=no"]
        cmd += ["-o", "StrictHostKeyChecking=accept-new"]

        if session.auth_type == "key" and session.key_file:
            cmd += ["-i", session.key_file]
            if session.cert_file:
                cmd += ["-o", f"CertificateFile={session.cert_file}"]
            cmd += ["-o", "IdentitiesOnly=yes"]

        if session.jump_host:
            cmd += ["-J", session.jump_host]

        if session.keepalive > 0:
            cmd += ["-o", f"ServerAliveInterval={session.keepalive}",
                    "-o", "ServerAliveCountMax=3"]

        if session.extra_args:
            cmd += shlex.split(session.extra_args)

        # Build destination — if no username specified use current user
        if session.username:
            destination = f"{session.username}@{session.host}"
        else:
            import getpass
            destination = f"{getpass.getuser()}@{session.host}"
        cmd.append(destination)
        return cmd

    # ── PTY resize ────────────────────────────────────────────────────────────

    @staticmethod
    def _resize_pty(fd: int, cols: int, rows: int):
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except Exception as e:
            log.debug("resize_pty: %s", e)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _is_password_prompt(self, text: str) -> bool:
        """Detect password/passphrase prompts in PTY output."""
        import re
        patterns = [
            r"\[sudo\]",           # sudo password
            r"sudo.*password",
            r"'s password:",         # ssh login: user@host's password:
            r"password:",            # generic password prompt
            r"enter passphrase",     # key passphrase
        ]
        t = text.strip()
        for p in patterns:
            if re.search(p, t, re.IGNORECASE):
                return True
        return False

    async def _handle_auth_prompt(self, websocket, sid, conn, session,
                                    prompt_text, loop, auto_password=""):
        """
        Unified handler for all password/passphrase prompts:
          - SSH login: user@host's password:
          - sudo/su: [sudo] password for user:
          - Key passphrases: Enter passphrase for key ...

        Priority order:
          1. auto_password supplied (stored password) → write silently
          2. Broadcast via send_data → _password_events threading.Event
          3. User types in terminal → xterm.js auth_response (no-echo, atomic)
        """
        key = f"auth_{sid}"
        if key in self._password_events:
            return  # Already handling a prompt for this session

        prompt = prompt_text.strip().split("\n")[-1].strip()

        # 1. Stored password — deliver silently without prompting
        if auto_password:
            if conn.master_fd is not None:
                try:
                    os.write(conn.master_fd, (auto_password + "\r").encode())
                    log.debug("Auto-delivered stored password for %s", sid[:8])
                except OSError as e:
                    log.error("Auto-password write failed: %s", e)
            return

        # 2+3. Register event so broadcast (send_data) can satisfy the wait,
        #       then show in-terminal prompt as fallback for manual entry.
        event = threading.Event()
        store: list = []
        self._password_events[key] = (event, store)

        try:
            await websocket.send(
                json.dumps({"type": "auth_prompt", "prompt": prompt}))
        except Exception:
            self._password_events.pop(key, None)
            return

        try:
            while True:
                # Check if broadcast already delivered a password
                if event.is_set() and store:
                    break

                try:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    # No WS message yet — check if event fired (broadcast)
                    if event.is_set() and store:
                        break
                    # Check overall 60s timeout via event
                    # (event.wait handles the 60s in send_data)
                    continue
                if isinstance(raw, bytes):
                    continue
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "auth_response":
                        store.append(msg.get("value", ""))
                        break
                    elif msg.get("type") == "resize":
                        try:
                            self._resize_pty(conn.master_fd,
                                int(msg.get("cols", 80)), int(msg.get("rows", 24)))
                        except Exception:
                            pass
                except (json.JSONDecodeError, ValueError):
                    pass
        finally:
            self._password_events.pop(key, None)

        password = store[0] if store else ""
        if password and conn.master_fd is not None:
            try:
                os.write(conn.master_fd, (password + "\r").encode())
                log.debug("Auth password written atomically for %s", sid[:8])
            except OSError as e:
                log.error("Auth password write failed: %s", e)
        # Always exit auth mode so terminal input stays visible
        try:
            await websocket.send(json.dumps({"type": "auth_done"}))
        except Exception:
            pass

    async def _handle_sudo_prompt(self, websocket, sid, conn, session,
                                   prompt_text, loop):
        """Backwards-compatible alias — now calls unified handler."""
        # For sudo, check if the session has a stored password
        # (some users store sudo password same as login password)
        await self._handle_auth_prompt(
            websocket, sid, conn, session, prompt_text, loop)

    @staticmethod
    def _close_conn(conn: _PTYConn):
        if conn.master_fd is not None:
            try:
                os.close(conn.master_fd)
            except OSError:
                pass
            conn.master_fd = None
        if conn.proc and conn.proc.poll() is None:
            try:
                conn.proc.send_signal(signal.SIGHUP)
                conn.proc.wait(timeout=2)
            except Exception:
                try:
                    conn.proc.kill()
                except Exception:
                    pass
        conn.proc = None
        # Clean up SSH_ASKPASS temp script now that the process is gone
        if conn.askpass_path:
            try:
                os.unlink(conn.askpass_path)
            except OSError:
                pass
            conn.askpass_path = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @staticmethod
    async def _ws_status(ws, ok: bool, text: str):
        try:
            await ws.send(json.dumps({"type": "status", "ok": ok, "text": text}))
        except Exception:
            pass
