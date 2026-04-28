from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class Session:
    name:          str  = ""
    host:          str  = ""
    port:          int  = 22
    username:      str  = ""
    auth_type:     str  = "key"        # "key" | "password"
    key_file:      str  = ""           # path to private key
    cert_file:     str  = ""           # path to cert (key-cert.pub), optional
    password:      str  = ""           # stored plaintext
    jump_host:     str  = ""           # bastion/jump host  user@host[:port]
    keepalive:     int  = 60           # ServerAliveInterval seconds (0=off)
    extra_args:    str  = ""
    group:         str  = "Default"
    notes:         str  = ""
    last_connected: str = ""           # ISO timestamp, set on connect
    id:            str  = field(default_factory=lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------ #

    def display_name(self) -> str:
        return self.name or f"{self.username}@{self.host}"

    def ssh_args(self) -> list[str]:
        args = ["-p", str(self.port)]
        if self.auth_type == "key":
            if self.key_file:
                args += ["-i", self.key_file]
            if self.cert_file:
                args += ["-o", f"CertificateFile={self.cert_file}"]
        if self.keepalive > 0:
            args += ["-o", f"ServerAliveInterval={self.keepalive}",
                     "-o", "ServerAliveCountMax=3"]
        if self.jump_host:
            args += ["-J", self.jump_host]
        args += ["-o", "StrictHostKeyChecking=accept-new"]
        if self.extra_args:
            args += self.extra_args.split()
        args.append(f"{self.username}@{self.host}")
        return args

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "id", "name", "host", "port", "username",
            "auth_type", "key_file", "cert_file", "password",
            "jump_host", "keepalive", "extra_args",
            "group", "notes", "last_connected",
        )}

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        # ── migration: old '::' key/cert storage ──────────────────────
        key_raw = d.get("key_file", "")
        cert_raw = d.get("cert_file", "")
        if "::" in key_raw and not cert_raw:
            key_raw, cert_raw = key_raw.split("::", 1)

        return cls(
            id            = d.get("id",             str(uuid.uuid4())),
            name          = d.get("name",           ""),
            host          = d.get("host",           ""),
            port          = int(d.get("port",       22)),
            username      = d.get("username",       ""),
            auth_type     = d.get("auth_type",      "key"),
            key_file      = key_raw,
            cert_file     = cert_raw,
            password      = d.get("password",       ""),
            jump_host     = d.get("jump_host",      ""),
            keepalive     = int(d.get("keepalive",  60)),
            extra_args    = d.get("extra_args",     ""),
            group         = d.get("group",          "Default"),
            notes         = d.get("notes",          ""),
            last_connected= d.get("last_connected", ""),
        )
