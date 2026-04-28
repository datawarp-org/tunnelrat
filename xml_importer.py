import xml.etree.ElementTree as ET
from pathlib import Path
from session_model import Session


def import_superputty_xml(path: str) -> list[Session]:
    """Parse a SuperPutty Sessions.XML file and return a list of Session objects."""
    tree = ET.parse(path)
    root = tree.getroot()

    sessions = []
    for elem in root.iter("SessionData"):
        try:
            session_id = elem.get("SessionId", "")
            # SessionId is typically "Group\Name" or just "Name"
            parts = session_id.replace("/", "\\").split("\\")
            if len(parts) >= 2:
                group = parts[-2] or "Default"
                name = parts[-1]
            else:
                group = "Default"
                name = parts[0] if parts else elem.get("SessionName", "Unknown")

            name = name or elem.get("SessionName", "Unknown")
            host = elem.get("Host", "")
            if not host:
                continue

            proto = elem.get("Proto", "SSH").upper()
            if proto != "SSH":
                continue  # only SSH sessions

            port_str = elem.get("Port", "22")
            try:
                port = int(port_str)
            except ValueError:
                port = 22

            username = elem.get("Username", "")

            # ExtraArgs might contain -i key path
            extra_args = elem.get("ExtraArgs", "")
            key_file = ""
            auth_type = "key"

            # Try to extract -i from ExtraArgs
            ea_parts = extra_args.split()
            cleaned_extras = []
            i = 0
            while i < len(ea_parts):
                if ea_parts[i] == "-i" and i + 1 < len(ea_parts):
                    key_file = ea_parts[i + 1]
                    i += 2
                else:
                    cleaned_extras.append(ea_parts[i])
                    i += 1

            if not key_file:
                auth_type = "password"

            session = Session(
                name=name,
                host=host,
                port=port,
                username=username,
                auth_type=auth_type,
                key_file=key_file,
                extra_args=" ".join(cleaned_extras),
                group=group,
            )
            sessions.append(session)

        except Exception as e:
            print(f"[XML Import] Skipping element due to error: {e}")
            continue

    return sessions
