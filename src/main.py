"""USB Vault - Portable password manager with hotkey support.

Usage:
    vault                   Start GUI (default)
    vault --cli             Start CLI service mode
    vault add <domain>      Add credentials for a domain
    vault list              List all stored domains
    vault use <domain>      Set active domain for hotkey input
    vault remove <domain>   Remove credentials
    vault status            Show vault status
    vault lock              Lock the vault
"""

import os
import sys
import getpass
import platform
from pathlib import Path


def get_vault_dir() -> str:
    """Get the vault directory (same directory as the executable/script)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return str(Path(sys.executable).parent)
    else:
        # Running as script - use project root for development
        return str(Path(__file__).parent.parent)


def run_gui_mode(vault_dir: str):
    """Start the GUI application."""
    from .gui import VaultApp
    app = VaultApp(vault_dir)
    app.run()


def run_server_mode(vault_dir: str):
    """Start the vault background service (CLI mode)."""
    from .storage import VaultStorage
    from .server import VaultServer
    from .guide import check_accessibility_permission, show_accessibility_guide

    # Mac: check accessibility permission
    if platform.system() == "Darwin":
        if not check_accessibility_permission():
            print("macOS requires Accessibility permission for hotkeys.")
            show_accessibility_guide()
            if not check_accessibility_permission():
                print("Accessibility permission not granted. Hotkeys will not work.")
                print("You can still use CLI commands.")

    storage = VaultStorage(vault_dir)

    if storage.is_new:
        print("=" * 50)
        print("  USB Vault - First Time Setup")
        print("=" * 50)
        print()
        while True:
            pw1 = getpass.getpass("Set master password: ")
            if len(pw1) < 4:
                print("Password must be at least 4 characters.")
                continue
            pw2 = getpass.getpass("Confirm master password: ")
            if pw1 != pw2:
                print("Passwords don't match. Try again.")
                continue
            break
        storage.setup(pw1)
        print("\nVault created successfully!")
    else:
        print("=" * 50)
        print("  USB Vault - Unlock")
        print("=" * 50)
        print()
        for attempt in range(3):
            pw = getpass.getpass("Master password: ")
            if storage.unlock(pw):
                break
            remaining = 2 - attempt
            if remaining > 0:
                print(f"Wrong password. {remaining} attempts remaining.")
            else:
                print("Too many failed attempts. Exiting.")
                sys.exit(1)

        count = len(storage.list_domains())
        print(f"\nVault unlocked! ({count} credential{'s' if count != 1 else ''} stored)")

    print()
    server = VaultServer(vault_dir, storage)
    server.start()


def run_client_mode(vault_dir: str, args: list[str]):
    """Send a command to the running vault service."""
    from .client import VaultClient

    client = VaultClient(vault_dir)

    if not client.is_server_running():
        print("Vault service is not running. Start it first by running 'vault' without arguments.")
        sys.exit(1)

    cmd = args[0]

    if cmd == "use":
        if len(args) < 2:
            print("Usage: vault use <domain>")
            sys.exit(1)
        resp = client.send_command("use", domain=args[1])

    elif cmd == "add":
        if len(args) < 2:
            print("Usage: vault add <domain>")
            sys.exit(1)
        domain = args[1]
        username = input(f"Username for {domain}: ")
        password = getpass.getpass(f"Password for {domain}: ")
        if not username or not password:
            print("Username and password cannot be empty.")
            sys.exit(1)
        resp = client.send_command("add", domain=domain, username=username, password=password)

    elif cmd == "remove":
        if len(args) < 2:
            print("Usage: vault remove <domain>")
            sys.exit(1)
        resp = client.send_command("remove", domain=args[1])

    elif cmd == "list":
        resp = client.send_command("list")
        if resp.get("ok"):
            domains = resp.get("domains", [])
            active = resp.get("active", "")
            if not domains:
                print("No credentials stored.")
            else:
                print(f"Stored credentials ({len(domains)}):")
                for d in domains:
                    marker = " ← active" if d == active else ""
                    print(f"  • {d}{marker}")
            return

    elif cmd == "status":
        resp = client.send_command("status")
        if resp.get("ok"):
            print(f"Unlocked: {resp['unlocked']}")
            print(f"Active domain: {resp.get('active_domain') or '(none)'}")
            print(f"Total credentials: {resp['total_credentials']}")
            return

    elif cmd == "lock":
        resp = client.send_command("lock")

    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: add, list, use, remove, status, lock")
        sys.exit(1)

    # Print response
    if resp.get("ok"):
        print(resp.get("message", "OK"))
    else:
        print(f"Error: {resp.get('error', 'Unknown error')}")
        sys.exit(1)


def main():
    vault_dir = get_vault_dir()
    args = sys.argv[1:]

    if not args:
        # No arguments → start GUI mode (default)
        from .client import VaultClient
        client = VaultClient(vault_dir)
        if client.is_server_running():
            print("Vault service is already running.")
            print("Use 'vault <command>' to interact, or 'vault lock' to lock.")
            sys.exit(0)
        run_gui_mode(vault_dir)
    elif args[0] == "--cli":
        # Explicit CLI server mode
        run_server_mode(vault_dir)
    else:
        run_client_mode(vault_dir, args)


if __name__ == "__main__":
    main()
