# OpenClaw Vault - Skill Definition

## Skill Metadata

- **Name**: OpenClaw Vault Password Manager
- **Category**: automation
- **Description**: Portable password manager for AI agents. Zero-knowledge credential auto-fill via hotkeys (F9/F8). Interact through TCP IPC protocol on localhost.
- **Download**: https://github.com/wrongkaky83-jpg/openclaw-vault

## Skill Instructions

You have access to **OpenClaw Vault**, a portable encrypted password manager designed for AI agents. The human user stores credentials in the vault; you interact with it to auto-fill login pages — **you never see or handle raw passwords**.

### Architecture

```
┌─────────────┐    TCP JSON     ┌──────────────┐    AES-256    ┌───────────┐
│   AI Agent   │ ◄────────────► │  Vault Server │ ◄──────────► │ vault.dat │
│ (you)        │  localhost:     │  (background) │   encrypted   │ (on USB)  │
└─────────────┘  19840-19860    └──────┬───────┘              └───────────┘
                                       │
                                  F9 / F8 hotkeys
                                       │
                                       ▼
                                ┌──────────────┐
                                │   Browser /   │
                                │   Login Page  │
                                └──────────────┘
```

- Vault runs as a background process, listening on TCP `127.0.0.1` (port range 19840-19860)
- Communication is JSON over TCP socket — no HTTP, no REST
- Hotkeys (F9 = username, F8 = password) simulate keyboard typing into the focused input field
- The vault encrypts all data with AES-256 using the human's master password

### Prerequisites

1. `vault.exe` (Windows) or `vault.app` (macOS) must be **running and unlocked** by the human user
2. On macOS: the human must grant Accessibility permission to `vault.app` (System Settings → Privacy & Security → Accessibility)
3. On macOS: press `fn + F9` / `fn + F8` (function keys are media keys by default)
4. The keyboard input method must be set to **English** — if Chinese IME is active, hotkey output will be garbled

### How to Connect (TCP Socket)

The vault server writes a `vault.lock` file containing `{"pid": ..., "port": ...}` in its working directory. You can either read this file or scan ports.

#### Method 1: Read vault.lock

```python
import json, socket

# vault.lock location depends on how vault was launched:
# - Windows exe: same directory as vault.exe (e.g., E:/Projects/usb-vault/dist/vault.lock)
# - macOS .app:  vault.app/Contents/MacOS/vault.lock
lock_data = json.loads(open("path/to/vault.lock").read())
port = lock_data["port"]
```

#### Method 2: Port Scan (when lock file location is unknown)

```python
import socket, json

def find_vault_port():
    for port in range(19840, 19860):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect(('127.0.0.1', port))
            s.sendall(json.dumps({"cmd": "ping"}).encode())
            resp = json.loads(s.recv(4096).decode())
            s.close()
            if resp.get("ok"):
                return port
        except:
            continue
    return None
```

#### Sending Commands

```python
import socket, json

def vault_cmd(port, cmd, **kwargs):
    """Send a command to vault and return the response dict."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', port))
    s.sendall(json.dumps({"cmd": cmd, **kwargs}).encode())
    resp = json.loads(s.recv(4096).decode())
    s.close()
    return resp
```

### IPC Command Reference

| Command | Parameters | Response | Description |
|---------|-----------|----------|-------------|
| `ping` | — | `{"ok": true}` | Check if vault is alive |
| `status` | — | `{"ok": true, "unlocked": bool, "active_domain": str, "total_credentials": int}` | Get vault state |
| `list` | — | `{"ok": true, "domains": ["example.com", ...], "active": "..."}` | List all stored domains |
| `search` | `query` | `{"ok": true, "results": [{"domain": "...", "username": "..."}]}` | Fuzzy search domains |
| `use` | `domain` | `{"ok": true, "message": "Active domain: ..."}` | Set active domain for hotkey fill |
| `get` | `domain` | `{"ok": true, "domain": "...", "username": "..."}` | Get username only (no password!) |
| `add` | `domain`, `username`, `password` | `{"ok": true, "message": "..."}` | Add new credentials |
| `remove` | `domain` | `{"ok": true, "message": "..."}` | Delete credentials |
| `lock` | — | `{"ok": true, "message": "Vault locked"}` | Lock the vault |

**Domain fuzzy matching**: The `use`, `get`, and `search` commands support fuzzy matching. For example, `use namecheap` will match `namecheap.com`. If multiple domains match, the response includes all matches so you can ask the user to clarify.

**Important**: The `get` command returns the **username only**, never the password. This is by design — passwords are only delivered via hotkeys (F9/F8) directly into the focused input field.

### Standard Workflow: Auto-fill a Login Page

#### Step 1: Check vault is running

```python
resp = vault_cmd(port, "status")
# {"ok": true, "unlocked": true, "active_domain": "", "total_credentials": 5}
```

If vault is not running or locked, ask the human to launch/unlock it. **You cannot start or unlock the vault yourself.**

#### Step 2: Find the right credentials

```python
resp = vault_cmd(port, "search", query="namecheap")
# {"ok": true, "results": [{"domain": "namecheap.com", "username": "wrongkaky"}]}
```

#### Step 3: Set the active domain

```python
resp = vault_cmd(port, "use", domain="namecheap.com")
# {"ok": true, "message": "Active domain: namecheap.com (user: wrongkaky)"}
```

#### Step 4: Navigate to the login page

Open the website's login page in the browser.

#### Step 5: Fill credentials with hotkeys

1. Click on the **username input field** (make sure it's focused)
2. Press **F9** → vault types the username
3. Click on the **password input field**
4. Press **F8** → vault types the password
5. Click the login/submit button

**For SuperAgent AI agents**, use these tools:
```
visual_locate(target="username input field", action="click")
press_key("f9")
visual_locate(target="password input field", action="click")
press_key("f8")
visual_locate(target="login button", action="click")
```

### Platform Differences

| | Windows | macOS |
|---|---------|-------|
| Binary | `vault.exe` | `vault.app` |
| Hotkeys | F9 / F8 | fn+F9 / fn+F8 |
| Lock file | Same dir as .exe | `vault.app/Contents/MacOS/vault.lock` |
| Data file | Same dir as .exe | `vault.app/Contents/MacOS/vault.dat` |
| Permission | None needed | Accessibility permission required |
| Key sim | pynput | Quartz CGEvent |

### Troubleshooting

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| Cannot connect to vault | Port scan returns None | Ask human to launch vault.exe / vault.app |
| `unlocked: false` | Vault is locked | Ask human to enter master password |
| `No credentials for 'xxx'` | Domain not stored | Ask human to add credentials via GUI, or use `add` command if human provides them |
| Hotkey types nothing | No active domain set | Run `use <domain>` first |
| Hotkey types garbled text | Chinese IME is active | Ask human to switch to English input method |
| Multiple matches | Fuzzy match found >1 | Show matches to human, ask which one |
| macOS hotkey not working | Missing Accessibility permission | Ask human: System Settings → Privacy & Security → Accessibility → add vault.app |
| Stale vault.lock | Vault crashed without cleanup | Delete the lock file, restart vault |

### Security Rules

1. **Never ask the human for their password** — use the vault instead
2. **Never attempt to start or unlock the vault** — only the human can do this
3. **Never log, store, or display passwords** — they flow only through hotkeys
4. **The `get` command intentionally omits passwords** — this is a security feature, not a bug
5. **Always confirm with the human before adding or removing credentials**
