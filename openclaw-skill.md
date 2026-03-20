# OpenClaw Vault - Skill Definition

## Skill Metadata

- **Name**: OpenClaw Vault Password Manager
- **Category**: automation
- **Description**: Securely access stored credentials via USB Vault without exposing passwords in plain text. Supports hotkey auto-fill and CLI commands.
- **Download**: https://github.com/wrongkaky83-jpg/openclaw-vault/releases

## Skill Instructions

You have access to USB Vault, a portable password manager running on the user's machine. It stores credentials encrypted on a USB drive and provides hotkey-based auto-fill.

### How It Works

USB Vault runs as a background service with a local IPC server (TCP on localhost:19840-19860). You interact with it via CLI commands — you never see or handle raw passwords directly.

### Prerequisites

1. The user must have `vault.exe` (Windows) or `vault.app` (macOS) running
2. The vault must be unlocked (user enters master password at startup)
3. On Windows: ensure `vault.exe` path is accessible
4. On macOS: Accessibility permission must be granted to `vault.app`

### Available Commands

```bash
# Check if vault is running
vault status

# List all stored domains
vault list

# Search for a domain (fuzzy matching)
vault search <query>

# Set active domain (for hotkey auto-fill)
vault use <domain>

# Add new credentials
vault add <domain>

# Remove credentials
vault remove <domain>

# Lock the vault
vault lock
```

### Workflow: Auto-fill Login

When you need to log into a website for the user:

1. **Check vault status**: Run `vault status` to confirm it's running and unlocked
2. **Find the domain**: Run `vault search <site>` to find matching credentials
3. **Set active domain**: Run `vault use <domain>` to activate the credentials
4. **Navigate to login page**: Open the website's login page
5. **Fill username**: Click the username field, then press **F9** (macOS: fn+F9)
6. **Fill password**: Click the password field, then press **F8** (macOS: fn+F8)

### Important Notes

- **Never ask for passwords** — use the vault instead of asking the user to type passwords
- **Fuzzy matching works** — `vault use github` will match `github.com`
- **Input method must be English** — switch to English input before pressing hotkeys, or Chinese IME will intercept the simulated keystrokes
- **One domain at a time** — `vault use` sets the active domain; subsequent F9/F8 presses fill that domain's credentials
- **If vault is not running**, ask the user to start it and unlock with their master password
- **If credentials are not found**, inform the user and ask them to add the credentials via the GUI

### Error Handling

| Situation | Action |
|-----------|--------|
| Vault not running | Ask user to start vault.exe/vault.app |
| Vault locked | Ask user to unlock with master password |
| Domain not found | Run `vault search` to list similar domains, or ask user to add credentials |
| Multiple matches | `vault use` returns the list — pick the most specific one |
| Hotkey not working | Check: Is vault unlocked? Is active domain set? Is input method English? |
