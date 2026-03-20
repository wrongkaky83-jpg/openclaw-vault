"""Background vault service - handles IPC commands and hotkey events."""
from __future__ import annotations

import os
import sys
import json
import socket
import threading
import time
import platform
from pathlib import Path

from .storage import VaultStorage
from .hotkeys import HotkeyManager

IPC_PORT_RANGE = (19840, 19860)  # Try ports in this range
LOCK_FILENAME = "vault.lock"
USB_CHECK_INTERVAL = 3  # seconds


class VaultServer:
    """Background service that listens for CLI commands and hotkey events."""

    def __init__(self, vault_dir: str, storage: VaultStorage):
        self.vault_dir = Path(vault_dir)
        self.storage = storage
        self.lock_file = self.vault_dir / LOCK_FILENAME
        self._current_domain: str = ""
        self._server_socket: socket.socket | None = None
        self._port: int = 0
        self._running = False
        self._hotkey_manager: HotkeyManager | None = None

    def start(self):
        """Start the background service."""
        # Find an available port
        self._port = self._find_port()
        if not self._port:
            print("Error: Could not find available port for IPC")
            sys.exit(1)

        # Write lock file
        self._write_lock()

        # Start hotkey listener
        self._hotkey_manager = HotkeyManager(
            on_username_requested=self._get_current_username,
            on_password_requested=self._get_current_password,
        )
        self._hotkey_manager.start()

        # Start USB watchdog
        self._start_usb_watchdog()

        # Start IPC server (blocking)
        self._running = True
        self._run_ipc_server()

    def stop(self):
        """Stop the service and clean up."""
        self._running = False
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        if self._server_socket:
            self._server_socket.close()
        self._remove_lock()
        self.storage.lock()

    def _find_port(self) -> int:
        """Find an available port in our range."""
        for port in range(*IPC_PORT_RANGE):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('127.0.0.1', port))
                s.close()
                return port
            except OSError:
                continue
        return 0

    def _write_lock(self):
        """Write lock file with PID and port."""
        lock_data = {
            "pid": os.getpid(),
            "port": self._port,
        }
        self.lock_file.write_text(json.dumps(lock_data))

    def _remove_lock(self):
        """Remove lock file."""
        try:
            self.lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    def _get_current_username(self) -> str | None:
        """Hotkey callback: get username for current domain."""
        if not self._current_domain:
            return None
        cred = self.storage.get(self._current_domain)
        return cred["username"] if cred else None

    def _get_current_password(self) -> str | None:
        """Hotkey callback: get password for current domain."""
        if not self._current_domain:
            return None
        cred = self.storage.get(self._current_domain)
        return cred["password"] if cred else None

    def _start_usb_watchdog(self):
        """Monitor USB drive availability, exit if removed."""
        def watchdog():
            while self._running:
                time.sleep(USB_CHECK_INTERVAL)
                if not self.storage.check_usb_alive():
                    print("\nUSB drive removed. Locking vault and exiting...")
                    self.stop()
                    os._exit(0)

        t = threading.Thread(target=watchdog, daemon=True)
        t.start()

    def _run_ipc_server(self):
        """Run TCP IPC server to handle CLI commands."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('127.0.0.1', self._port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)  # Allow periodic check for shutdown

        print(f"Vault service running on port {self._port}")
        print(f"Hotkeys active: F9 (username) / F8 (password)")
        if self._current_domain:
            print(f"Current domain: {self._current_domain}")
        print("Waiting for commands... (Press Ctrl+C to stop)")

        try:
            while self._running:
                try:
                    conn, _ = self._server_socket.accept()
                    self._handle_client(conn)
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def _handle_client(self, conn: socket.socket):
        """Handle a single CLI client connection."""
        try:
            data = conn.recv(4096).decode('utf-8')
            request = json.loads(data)
            response = self._process_command(request)
            conn.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            try:
                conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))
            except Exception:
                pass
        finally:
            conn.close()

    def _process_command(self, request: dict) -> dict:
        """Process a CLI command and return response."""
        cmd = request.get("cmd", "")

        if cmd == "use":
            domain = request.get("domain", "").lower()
            cred = self.storage.get(domain)
            if cred:
                self._current_domain = domain
                return {"ok": True, "message": f"Active domain: {domain} (user: {cred['username']})"}
            # Fuzzy search fallback
            matches = self.storage.search(domain)
            if len(matches) == 1:
                self._current_domain = matches[0]["domain"]
                return {"ok": True, "message": f"Active domain: {matches[0]['domain']} (user: {matches[0]['username']})"}
            elif matches:
                return {"ok": False, "error": f"Multiple matches for '{domain}': {[m['domain'] for m in matches]}. Please be more specific."}
            else:
                return {"ok": False, "error": f"No credentials found for '{domain}'", "available": self.storage.list_domains()}

        elif cmd == "add":
            domain = request.get("domain", "").lower()
            username = request.get("username", "")
            password = request.get("password", "")
            if not all([domain, username, password]):
                return {"ok": False, "error": "Missing domain, username, or password"}
            self.storage.add(domain, username, password)
            return {"ok": True, "message": f"Credentials saved for '{domain}'"}

        elif cmd == "remove":
            domain = request.get("domain", "").lower()
            if self.storage.remove(domain):
                if self._current_domain == domain:
                    self._current_domain = ""
                return {"ok": True, "message": f"Removed '{domain}'"}
            return {"ok": False, "error": f"'{domain}' not found"}

        elif cmd == "list":
            domains = self.storage.list_domains()
            return {"ok": True, "domains": domains, "active": self._current_domain}

        elif cmd == "status":
            return {
                "ok": True,
                "unlocked": self.storage.is_unlocked,
                "active_domain": self._current_domain,
                "total_credentials": len(self.storage.list_domains()),
            }

        elif cmd == "get":
            # Direct get for AI usage (returns username/password without typing)
            domain = request.get("domain", "").lower()
            cred = self.storage.get(domain)
            if cred:
                return {"ok": True, "domain": domain, "username": cred["username"]}
            # Fuzzy search fallback
            matches = self.storage.search(domain)
            if len(matches) == 1:
                return {"ok": True, "domain": matches[0]["domain"], "username": matches[0]["username"]}
            elif matches:
                return {"ok": False, "error": f"Multiple matches for '{domain}'", "matches": [{"domain": m["domain"], "username": m["username"]} for m in matches]}
            return {"ok": False, "error": f"No credentials for '{domain}'", "available": self.storage.list_domains()}

        elif cmd == "search":
            query = request.get("query", "").strip()
            if not query:
                return {"ok": True, "results": [{"domain": d, "username": self.storage.get(d)["username"]} for d in self.storage.list_domains()]}
            matches = self.storage.search(query)
            return {"ok": True, "results": [{"domain": m["domain"], "username": m["username"]} for m in matches]}

        elif cmd == "lock":
            self.storage.lock()
            self._current_domain = ""
            return {"ok": True, "message": "Vault locked"}

        elif cmd == "ping":
            return {"ok": True}

        else:
            return {"ok": False, "error": f"Unknown command: {cmd}"}
