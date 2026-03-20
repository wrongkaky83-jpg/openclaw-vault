# OpenClaw Vault - Portable Password Manager for AI Agents

A portable, zero-install password manager that runs directly from a USB drive. Designed for both human users (GUI + hotkeys) and **AI agents via [OpenClaw](https://openclaw.org)** — enabling secure credential access without exposing passwords in plain text.

## Why OpenClaw Vault?

AI agents often need to log into websites on your behalf, but storing passwords in AI memory or config files is a security risk. OpenClaw Vault solves this:

- **Encrypted at rest** — AES-256-GCM with PBKDF2 key derivation
- **Portable** — runs from USB drive, no installation needed
- **AI-ready** — CLI/IPC interface for OpenClaw skills and other AI frameworks
- **Auto-lock** — locks automatically when USB is removed
- **Cross-platform** — Windows & macOS

## Features

### For Humans
- Dark-themed GUI (Catppuccin) for managing credentials
- Global hotkeys: **F9** (username) / **F8** (password) to auto-fill into any input field
- System tray integration — runs in background
- Master password protection with re-verification for sensitive operations

### For AI Agents (OpenClaw)
- **IPC command interface** — AI agents interact via CLI commands, never seeing raw passwords
- **Fuzzy domain matching** — `vault use cloudflare` finds `cloudflare.com` automatically
- **Search** — `vault search <query>` to discover stored credentials
- **Hotkey triggering** — AI agent sets the active domain, then simulates F9/F8 to fill credentials

```
# AI agent workflow
vault use github.com        # Set active domain
vault list                   # List all stored domains
vault search cloud           # Fuzzy search
vault status                 # Check vault state
```

## Quick Start

### Download

| Platform | File | Size |
|----------|------|------|
| Windows | `vault.exe` | ~35 MB |
| macOS | `vault.app` | ~13 MB |

Download from [Releases](../../releases) and copy to your USB drive. No installation required.

### First Run

1. Run `vault.exe` (Windows) or `vault.app` (macOS)
2. Set your master password
3. Add credentials via the GUI
4. Use F9/F8 hotkeys to auto-fill (macOS: fn+F9/fn+F8)

### macOS Permissions

macOS requires **Accessibility** permission for hotkeys and auto-fill:
- System Settings > Privacy & Security > Accessibility > Add `vault.app`
- System Settings > Privacy & Security > Input Monitoring > Add `vault.app`

### CLI Mode

```bash
vault --cli                  # Start in CLI/service mode (no GUI)
vault add github.com         # Add credentials interactively
vault use github.com         # Set active domain for hotkeys
vault list                   # List all domains
vault search <query>         # Fuzzy search domains
vault status                 # Show vault status
vault lock                   # Lock vault
vault remove github.com      # Remove credentials
```

## OpenClaw Integration

OpenClaw Vault is designed to work with [OpenClaw](https://openclaw.org) AI agent skills. Install the **OpenClaw Vault** skill from the marketplace to let your AI employees securely access credentials.

The skill teaches AI agents to:
1. Check if the vault is running
2. Set the active domain for the target website
3. Use hotkeys to fill credentials without ever reading the raw password

See [openclaw-skill.md](openclaw-skill.md) for the full skill definition.

## Architecture

```
vault.exe / vault.app
  ├── GUI (tkinter)        — credential management UI
  ├── IPC Server (TCP)     — listens on localhost:19840-19860
  ├── Hotkey Listener      — F9/F8 global hotkeys
  │   ├── Windows: pynput
  │   └── macOS: Quartz CGEvent Tap
  ├── Storage              — encrypted vault.dat (AES-256-GCM)
  └── USB Watchdog         — auto-lock on USB removal
```

### Data Files

| File | Purpose |
|------|---------|
| `vault.dat` | Encrypted credential database |
| `vault.lock` | Runtime lock file (PID + port) |

All data stays on the USB drive. Nothing is written to the host system.

## Security

- **Encryption**: AES-256-GCM with PBKDF2-SHA256 (100,000 iterations)
- **No network**: Zero network access — everything runs locally via localhost IPC
- **Memory safety**: Credentials are cleared from memory on lock
- **USB removal detection**: Auto-locks when the drive is disconnected
- **Password verification**: Re-authentication required before viewing/copying passwords

## Build from Source

### Requirements

- Python 3.10+ (macOS needs 3.10+ for Tk 8.6 dark mode support)
- Dependencies: `cryptography`, `pynput`, `pystray`, `Pillow`

### Build

```bash
pip install -r requirements.txt
python build.py              # GUI mode (default)
python build.py --console    # Console mode (for debugging)
```

Output: `dist/vault.exe` (Windows) or `dist/vault.app` (macOS)

### Development

```bash
pip install -r requirements.txt
python vault.py              # Run GUI directly
python vault.py --cli        # Run CLI service
```

## Project Structure

```
openclaw-vault/
├── vault.py              # Entry point
├── build.py              # PyInstaller build script
├── requirements.txt      # Python dependencies
└── src/
    ├── main.py           # CLI argument routing
    ├── gui.py            # Tkinter GUI (Catppuccin dark theme)
    ├── server.py         # IPC server + hotkey integration
    ├── client.py         # IPC client for CLI commands
    ├── hotkeys.py        # Global hotkey listener + keyboard simulator
    ├── crypto.py         # AES-256-GCM encryption
    ├── storage.py        # Encrypted credential storage
    └── guide.py          # macOS accessibility permission guide
```

## License

[MIT](LICENSE) — do whatever you want with it.
