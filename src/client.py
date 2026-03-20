"""CLI client - sends commands to the running vault service via IPC."""

from __future__ import annotations

import json
import socket
from pathlib import Path

LOCK_FILENAME = "vault.lock"


class VaultClient:
    """Sends commands to the vault background service."""

    def __init__(self, vault_dir: str):
        self.vault_dir = Path(vault_dir)
        self.lock_file = self.vault_dir / LOCK_FILENAME

    def is_server_running(self) -> bool:
        """Check if a vault server is already running."""
        port = self._get_port()
        if not port:
            return False
        try:
            resp = self._send({"cmd": "ping"})
            return resp.get("ok", False)
        except Exception:
            # Stale lock file - clean it up
            try:
                self.lock_file.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def send_command(self, cmd: str, **kwargs) -> dict:
        """Send a command to the server and return the response."""
        request = {"cmd": cmd, **kwargs}
        return self._send(request)

    def _get_port(self) -> int | None:
        """Read the server port from lock file."""
        try:
            data = json.loads(self.lock_file.read_text())
            return data.get("port")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _send(self, request: dict) -> dict:
        """Send request to server and get response."""
        port = self._get_port()
        if not port:
            raise ConnectionError("Vault service is not running")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect(('127.0.0.1', port))
            sock.sendall(json.dumps(request).encode('utf-8'))
            data = sock.recv(4096).decode('utf-8')
            return json.loads(data)
        finally:
            sock.close()
