import json
import os
from pathlib import Path
from session_model import Session
from crypto_util import encrypt_password, decrypt_password


CONFIG_DIR = Path.home() / ".config" / "tunnelrat"
SESSIONS_FILE = CONFIG_DIR / "sessions.json"


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}   # id -> Session

    def load(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE) as f:
                    data = json.load(f)
                rows = []
                for d in data:
                    if d.get("password"):
                        d["password"] = decrypt_password(d["password"])
                    rows.append(d)
                self.sessions = {r["id"]: Session.from_dict(r) for r in rows}
            except Exception as e:
                print(f"[SessionManager] Failed to load sessions: {e}")

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSIONS_FILE, "w") as f:
            rows = []
            for sess in self.sessions.values():
                d = sess.to_dict()
                if d.get("password"):
                    d["password"] = encrypt_password(d["password"])
                rows.append(d)
            json.dump(rows, f, indent=2)

    def add(self, session: Session):
        self.sessions[session.id] = session
        self.save()

    def update(self, session: Session):
        self.sessions[session.id] = session
        self.save()

    def delete(self, session_id: str):
        self.sessions.pop(session_id, None)
        self.save()

    def get(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def get_by_name_host(self, name: str, host: str) -> Session | None:
        for s in self.sessions.values():
            if s.name == name and s.host == host:
                return s
        return None

    def groups(self) -> list[str]:
        groups = list({s.group for s in self.sessions.values()})
        groups.sort()
        if "Default" in groups:
            groups.remove("Default")
            groups.insert(0, "Default")
        return groups

    def sessions_in_group(self, group: str) -> list[Session]:
        return sorted(
            [s for s in self.sessions.values() if s.group == group],
            key=lambda s: s.name.lower()
        )
