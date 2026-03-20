"""Vault data storage - manages vault.dat file and in-memory credential cache."""
from __future__ import annotations

import os
from pathlib import Path
from .crypto import encrypt_data, decrypt_data


class VaultStorage:
    """Manages encrypted credential storage."""

    def __init__(self, vault_dir: str):
        self.vault_dir = Path(vault_dir)
        self.vault_file = self.vault_dir / "vault.dat"
        self.config_file = self.vault_dir / "config.json"
        self._data: dict = {}  # {domain: {username, password}}
        self._master_password: str = ""
        self._unlocked = False

    @property
    def is_new(self) -> bool:
        return not self.vault_file.exists()

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    def setup(self, master_password: str):
        """First-time setup: create empty vault with master password."""
        self._master_password = master_password
        self._data = {}
        self._save()
        self._unlocked = True

    def unlock(self, master_password: str) -> bool:
        """Unlock vault with master password. Returns True on success."""
        try:
            encrypted = self.vault_file.read_bytes()
            self._data = decrypt_data(encrypted, master_password)
            self._master_password = master_password
            self._unlocked = True
            return True
        except ValueError:
            return False

    def lock(self):
        """Lock vault, clear sensitive data from memory."""
        self._data = {}
        self._master_password = ""
        self._unlocked = False

    def _save(self):
        """Encrypt and write data to vault.dat."""
        encrypted = encrypt_data(self._data, self._master_password)
        self.vault_file.write_bytes(encrypted)

    def add(self, domain: str, username: str, password: str):
        """Add or update credentials for a domain."""
        self._ensure_unlocked()
        self._data[domain.lower()] = {
            "username": username,
            "password": password,
        }
        self._save()

    def remove(self, domain: str) -> bool:
        """Remove credentials for a domain. Returns True if found."""
        self._ensure_unlocked()
        key = domain.lower()
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def get(self, domain: str) -> dict | None:
        """Get credentials for a domain. Returns {username, password} or None."""
        self._ensure_unlocked()
        return self._data.get(domain.lower())

    def search(self, query: str) -> list[dict]:
        """Fuzzy search: exact match first, then substring match.

        Returns list of {domain, username, password} dicts.
        Strips common prefixes (www., https://, http://) for matching.
        """
        self._ensure_unlocked()
        query = query.lower().strip()

        # Strip URL prefixes from query
        for prefix in ("https://", "http://", "www."):
            if query.startswith(prefix):
                query = query[len(prefix):]
        query = query.rstrip("/")

        # 1) Exact match
        if query in self._data:
            cred = self._data[query]
            return [{"domain": query, "username": cred["username"], "password": cred["password"]}]

        # 2) Fuzzy: query is substring of stored domain, or stored domain is substring of query
        results = []
        for domain, cred in self._data.items():
            # Also strip prefixes from stored domain for comparison
            clean_domain = domain
            for prefix in ("www.",):
                if clean_domain.startswith(prefix):
                    clean_domain = clean_domain[len(prefix):]

            if query in clean_domain or clean_domain in query:
                results.append({"domain": domain, "username": cred["username"], "password": cred["password"]})

        return sorted(results, key=lambda r: r["domain"])

    def list_domains(self) -> list[str]:
        """List all stored domains."""
        self._ensure_unlocked()
        return sorted(self._data.keys())

    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Change master password. Returns True on success."""
        self._ensure_unlocked()
        if old_password != self._master_password:
            return False
        self._master_password = new_password
        self._save()
        return True

    def _ensure_unlocked(self):
        if not self._unlocked:
            raise RuntimeError("Vault is locked")

    def check_usb_alive(self) -> bool:
        """Check if the USB drive is still accessible."""
        try:
            return self.vault_dir.exists()
        except OSError:
            return False
