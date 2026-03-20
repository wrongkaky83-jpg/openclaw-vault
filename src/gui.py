"""USB Vault GUI - Complete password management interface with system tray."""
from __future__ import annotations

import os
import sys
import platform
import threading
import atexit
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


class VaultApp:
    """Main GUI application for USB Vault."""

    # Color scheme
    BG = "#1e1e2e"          # Dark background
    BG_SECONDARY = "#2a2a3c"  # Slightly lighter
    BG_ENTRY = "#313145"     # Input fields
    FG = "#cdd6f4"           # Light text
    FG_DIM = "#6c7086"       # Dimmed text
    ACCENT = "#89b4fa"       # Blue accent
    ACCENT_HOVER = "#74c7ec" # Lighter blue
    SUCCESS = "#a6e3a1"      # Green
    DANGER = "#f38ba8"       # Red/pink
    WARNING = "#fab387"      # Orange
    BORDER = "#45475a"       # Border color

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir
        self.storage = None
        self.server = None
        self._server_thread = None
        self._current_domain = ""
        self._tray_icon = None
        self._quitting = False

        self.root = tk.Tk()
        self.root.withdraw()  # Hide until ready

        self._setup_styles()
        self._show_unlock_screen()

    def _setup_styles(self):
        """Configure ttk styles for dark theme."""
        self.root.configure(bg=self.BG)
        self.root.option_add("*Font", ("Segoe UI", 10) if IS_WIN else ("SF Pro", 10))

        style = ttk.Style()
        style.theme_use("clam")

        # General
        style.configure(".", background=self.BG, foreground=self.FG,
                        fieldbackground=self.BG_ENTRY, borderwidth=0)
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.FG)
        style.configure("TEntry", fieldbackground=self.BG_ENTRY, foreground=self.FG,
                        insertcolor=self.FG, borderwidth=1, relief="solid")
        style.map("TEntry", bordercolor=[("focus", self.ACCENT), ("!focus", self.BORDER)])

        # Buttons
        style.configure("Accent.TButton", background=self.ACCENT, foreground="#1e1e2e",
                        font=("Segoe UI", 10, "bold") if IS_WIN else ("SF Pro", 10, "bold"),
                        padding=(16, 8))
        style.map("Accent.TButton",
                  background=[("active", self.ACCENT_HOVER), ("pressed", "#5d9df5")])

        style.configure("Danger.TButton", background=self.DANGER, foreground="#1e1e2e",
                        font=("Segoe UI", 10, "bold") if IS_WIN else ("SF Pro", 10, "bold"),
                        padding=(16, 8))
        style.map("Danger.TButton",
                  background=[("active", "#f17497"), ("pressed", "#e86b88")])

        style.configure("Ghost.TButton", background=self.BG_SECONDARY, foreground=self.FG,
                        padding=(12, 8))
        style.map("Ghost.TButton",
                  background=[("active", self.BORDER)])

        # Treeview
        style.configure("Treeview",
                        background=self.BG_SECONDARY,
                        foreground=self.FG,
                        fieldbackground=self.BG_SECONDARY,
                        rowheight=36,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background=self.BG,
                        foreground=self.FG_DIM,
                        font=("Segoe UI", 9) if IS_WIN else ("SF Pro", 9),
                        borderwidth=0,
                        relief="flat")
        style.map("Treeview",
                  background=[("selected", "#45475a")],
                  foreground=[("selected", self.ACCENT)])
        style.map("Treeview.Heading",
                  background=[("active", self.BG_SECONDARY)])

        # Scrollbar
        style.configure("TScrollbar", background=self.BG_SECONDARY,
                        troughcolor=self.BG, borderwidth=0, arrowsize=0)
        style.map("TScrollbar", background=[("active", self.BORDER)])

    # ── Unlock / Setup Screen ──────────────────────────────────────────

    def _show_unlock_screen(self):
        """Show the master password unlock/setup screen."""
        from .storage import VaultStorage
        self.storage = VaultStorage(self.vault_dir)
        is_new = self.storage.is_new

        self.root.title("USB Vault")
        self.root.geometry("400x340")
        self.root.resizable(False, False)
        self._center_window(400, 340)
        self.root.deiconify()

        # Protocol for close button
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Clear any existing widgets
        for w in self.root.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.root, padding=30)
        frame.pack(fill="both", expand=True)

        # Logo / Title
        title_text = "USB Vault"
        tk.Label(frame, text="🔐", font=("Segoe UI", 32), bg=self.BG).pack(pady=(10, 5))
        tk.Label(frame, text=title_text, font=("Segoe UI", 18, "bold") if IS_WIN else ("SF Pro", 18, "bold"),
                 bg=self.BG, fg=self.FG).pack()

        if is_new:
            tk.Label(frame, text="First time? Set your master password", font=("Segoe UI", 10),
                     bg=self.BG, fg=self.FG_DIM).pack(pady=(5, 15))

            # Password
            tk.Label(frame, text="Master Password", bg=self.BG, fg=self.FG_DIM,
                     font=("Segoe UI", 9), anchor="w").pack(fill="x")
            self._pw1_var = tk.StringVar()
            pw1_entry = ttk.Entry(frame, textvariable=self._pw1_var, show="●", font=("Segoe UI", 12))
            pw1_entry.pack(fill="x", pady=(2, 8))
            pw1_entry.focus_set()

            # Confirm
            tk.Label(frame, text="Confirm Password", bg=self.BG, fg=self.FG_DIM,
                     font=("Segoe UI", 9), anchor="w").pack(fill="x")
            self._pw2_var = tk.StringVar()
            pw2_entry = ttk.Entry(frame, textvariable=self._pw2_var, show="●", font=("Segoe UI", 12))
            pw2_entry.pack(fill="x", pady=(2, 15))
            pw2_entry.bind("<Return>", lambda e: self._do_setup())

            ttk.Button(frame, text="Create Vault", style="Accent.TButton",
                       command=self._do_setup).pack(fill="x")
        else:
            tk.Label(frame, text="Enter master password to unlock", font=("Segoe UI", 10),
                     bg=self.BG, fg=self.FG_DIM).pack(pady=(5, 20))

            # Password
            self._pw_var = tk.StringVar()
            pw_entry = ttk.Entry(frame, textvariable=self._pw_var, show="●", font=("Segoe UI", 12))
            pw_entry.pack(fill="x", pady=(0, 5))
            pw_entry.focus_set()
            pw_entry.bind("<Return>", lambda e: self._do_unlock())

            # Error label
            self._error_label = tk.Label(frame, text="", bg=self.BG, fg=self.DANGER,
                                         font=("Segoe UI", 9))
            self._error_label.pack(fill="x", pady=(0, 10))

            ttk.Button(frame, text="Unlock", style="Accent.TButton",
                       command=self._do_unlock).pack(fill="x")

    def _do_setup(self):
        """Handle first-time setup."""
        pw1 = self._pw1_var.get()
        pw2 = self._pw2_var.get()

        if len(pw1) < 4:
            messagebox.showwarning("Too Short", "Master password must be at least 4 characters")
            return
        if pw1 != pw2:
            messagebox.showwarning("Mismatch", "Passwords do not match")
            return

        self.storage.setup(pw1)
        self._start_service_and_show_main()

    def _do_unlock(self):
        """Handle unlock attempt."""
        pw = self._pw_var.get()
        if not pw:
            return

        if self.storage.unlock(pw):
            self._start_service_and_show_main()
        else:
            self._error_label.config(text="Wrong password, try again")
            self._pw_var.set("")

    # ── Main Window ────────────────────────────────────────────────────

    def _start_service_and_show_main(self):
        """Start background service and show main management window."""
        # Start background server (hotkeys + IPC)
        self._start_background_server()
        self._show_main_window()

    def _start_background_server(self):
        """Start the vault server in a background thread."""
        from .server import VaultServer, LOCK_FILENAME
        from .guide import check_accessibility_permission, show_accessibility_guide

        # Clean up stale lock file from previous crash/force-close
        lock_file = Path(self.vault_dir) / LOCK_FILENAME
        if lock_file.exists():
            try:
                lock_data = json.loads(lock_file.read_text())
                old_pid = lock_data.get("pid")
                # Check if the old process is still alive
                if old_pid:
                    try:
                        os.kill(old_pid, 0)  # signal 0 = just check existence
                        # Process exists — might be a real running instance
                        # Try to ping it
                        import socket
                        port = lock_data.get("port")
                        if port:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(1.0)
                            try:
                                s.connect(('127.0.0.1', port))
                                s.sendall(json.dumps({"cmd": "ping"}).encode())
                                s.recv(1024)
                                s.close()
                                # Server is actually running — warn user
                                messagebox.showwarning("Already Running", "Vault is already running.")
                                self._quit()
                                return
                            except Exception:
                                s.close()
                                # Process exists but not responding — stale
                                lock_file.unlink(missing_ok=True)
                    except OSError:
                        # Process doesn't exist — stale lock
                        lock_file.unlink(missing_ok=True)
            except Exception:
                # Corrupted lock file — just remove it
                lock_file.unlink(missing_ok=True)

        # Mac accessibility check
        if IS_MAC and not check_accessibility_permission():
            show_accessibility_guide()

        self.server = VaultServer(self.vault_dir, self.storage)

        def run_server():
            try:
                self.server.start()
            except Exception:
                pass

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

        # Register atexit to clean lock file on abnormal exit
        def cleanup_lock():
            if self.server:
                try:
                    self.server._remove_lock()
                except Exception:
                    pass
        atexit.register(cleanup_lock)

    def _show_main_window(self):
        """Show the main credential management window."""
        self.root.title("USB Vault")
        self.root.geometry("680x520")
        self.root.resizable(True, True)
        self.root.minsize(500, 400)
        self._center_window(680, 520)

        # Clear
        for w in self.root.winfo_children():
            w.destroy()

        # ── Top bar ──
        topbar = tk.Frame(self.root, bg=self.BG, padx=16, pady=12)
        topbar.pack(fill="x")

        tk.Label(topbar, text="🔐 USB Vault", font=("Segoe UI", 14, "bold") if IS_WIN else ("SF Pro", 14, "bold"),
                 bg=self.BG, fg=self.FG).pack(side="left")

        # Right side buttons
        btn_frame = tk.Frame(topbar, bg=self.BG)
        btn_frame.pack(side="right")

        ttk.Button(btn_frame, text="Change Password", style="Ghost.TButton",
                   command=self._change_password).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Lock", style="Ghost.TButton",
                   command=self._lock_vault).pack(side="left")

        # ── Separator ──
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(fill="x")

        # ── Toolbar ──
        toolbar = tk.Frame(self.root, bg=self.BG, padx=16, pady=10)
        toolbar.pack(fill="x")

        # Search
        search_frame = tk.Frame(toolbar, bg=self.BG)
        search_frame.pack(side="left", fill="x", expand=True)

        tk.Label(search_frame, text="🔍", bg=self.BG, fg=self.FG_DIM,
                 font=("Segoe UI", 10)).pack(side="left")
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var,
                                 font=("Segoe UI", 10), width=25)
        search_entry.pack(side="left", padx=(4, 0))
        # Placeholder
        self._search_placeholder = True

        # Buttons
        ttk.Button(toolbar, text="+ Add", style="Accent.TButton",
                   command=self._add_credential).pack(side="right", padx=(6, 0))

        # ── Credential List ──
        list_frame = tk.Frame(self.root, bg=self.BG, padx=16, pady=0)
        list_frame.pack(fill="both", expand=True)

        columns = ("domain", "username", "password", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 selectmode="browse")

        self.tree.heading("domain", text="Domain / Service")
        self.tree.heading("username", text="Username")
        self.tree.heading("password", text="Password")
        self.tree.heading("status", text="Status")

        self.tree.column("domain", width=180, minwidth=120)
        self.tree.column("username", width=180, minwidth=100)
        self.tree.column("password", width=160, minwidth=80)
        self.tree.column("status", width=80, minwidth=60, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self._edit_credential())
        # Right-click context menu
        self.tree.bind("<Button-3>" if IS_WIN else "<Button-2>", self._show_context_menu)
        # Select changes active domain
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # ── Context Menu ──
        self._context_menu = tk.Menu(self.root, tearoff=0, bg=self.BG_SECONDARY, fg=self.FG,
                                     activebackground=self.ACCENT, activeforeground="#1e1e2e",
                                     font=("Segoe UI", 10) if IS_WIN else ("SF Pro", 10))
        self._context_menu.add_command(label="Copy Username", command=self._copy_username)
        self._context_menu.add_command(label="Copy Password", command=self._copy_password)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Edit", command=self._edit_credential)
        self._context_menu.add_command(label="Set Active", command=self._set_active)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Delete", command=self._delete_credential)

        # ── Bottom bar ──
        bottombar = tk.Frame(self.root, bg=self.BG_SECONDARY, padx=16, pady=8)
        bottombar.pack(fill="x", side="bottom")

        self._status_label = tk.Label(bottombar, text="", bg=self.BG_SECONDARY, fg=self.FG_DIM,
                                      font=("Segoe UI", 9) if IS_WIN else ("SF Pro", 9))
        self._status_label.pack(side="left")

        self._active_label = tk.Label(bottombar, text="", bg=self.BG_SECONDARY, fg=self.SUCCESS,
                                      font=("Segoe UI", 9, "bold") if IS_WIN else ("SF Pro", 9, "bold"))
        self._active_label.pack(side="right")

        # Setup tray icon
        self._setup_tray()

        # Register search trace AFTER tree is created
        self._search_var.trace_add("write", lambda *_: self._refresh_list())

        # Load data
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the credential list."""
        try:
            self._refresh_list_inner()
        except Exception as e:
            messagebox.showerror("Refresh Failed", f"Error: {e}")

    def _refresh_list_inner(self):
        if not hasattr(self, 'tree'):
            return
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self._search_var.get().lower().strip()
        domains = self.storage.list_domains()


        count = 0
        for domain in domains:
            if search and search not in domain:
                continue
            cred = self.storage.get(domain)
            if not cred:
                continue
            masked_pw = "●" * min(len(cred["password"]), 12)
            status = "Active" if domain == self._current_domain else ""
            self.tree.insert("", "end", iid=domain, values=(
                domain, cred["username"], masked_pw, status
            ))
            count += 1

        # Update status bar
        total = len(domains)
        self._status_label.config(
            text=f"{total} entries | Hotkeys: F9 (username) / F8 (password)"
        )
        if self._current_domain:
            self._active_label.config(text=f"Active: {self._current_domain}")
        else:
            self._active_label.config(text="No domain selected", fg=self.WARNING)

    def _get_selected_domain(self) -> str | None:
        """Get the currently selected domain in the tree."""
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _on_select(self, event):
        """Handle tree selection change."""
        pass  # Selection is visual only, use "Set Active" to activate

    # ── CRUD Operations ────────────────────────────────────────────────

    def _add_credential(self):
        """Show dialog to add a new credential."""
        try:
            dialog = CredentialDialog(self.root, title="Add Credential", colors=self._colors())
            if dialog.result:
                domain, username, password = dialog.result
                domain = domain.lower().strip()
                if not domain or not username or not password:
                    messagebox.showwarning("Incomplete", "Domain, username, and password are all required")
                    return
                existing = self.storage.get(domain)
                if existing:
                    if not messagebox.askyesno("Already Exists", f"'{domain}' already has credentials. Overwrite?"):
                        return
                self.storage.add(domain, username, password)
                self._refresh_list()
                self._flash_status(f"Added: {domain}")
        except Exception as e:
            messagebox.showerror("Add Failed", f"Error: {e}")

    def _edit_credential(self):
        """Edit the selected credential."""
        try:
            domain = self._get_selected_domain()
            if not domain:
                messagebox.showinfo("Hint", "Please select a record first")
                return

            cred = self.storage.get(domain)
            if not cred:
                return

            dialog = CredentialDialog(
                self.root, title="Edit Credential",
                initial_domain=domain, initial_username=cred["username"],
                initial_password=cred["password"],
                domain_readonly=True,
                colors=self._colors(),
                verify_callback=self._verify_master_password
            )
            if dialog.result:
                _, username, password = dialog.result
                if username and password:
                    self.storage.add(domain, username, password)
                    self._refresh_list()
                    self._flash_status(f"Updated: {domain}")
        except Exception as e:
            messagebox.showerror("Edit Failed", f"Error: {e}")

    def _delete_credential(self):
        """Delete the selected credential."""
        try:
            domain = self._get_selected_domain()
            if not domain:
                messagebox.showinfo("Hint", "Please select a record first")
                return

            if messagebox.askyesno("Confirm Delete", f"Delete credentials for '{domain}'?"):
                self.storage.remove(domain)
                if self._current_domain == domain:
                    self._current_domain = ""
                    if self.server:
                        self.server._current_domain = ""
                self._refresh_list()
                self._flash_status(f"Deleted: {domain}")
        except Exception as e:
            messagebox.showerror("Delete Failed", f"Error: {e}")

    def _set_active(self):
        """Set the selected domain as active for hotkey input."""
        domain = self._get_selected_domain()
        if not domain:
            return
        self._current_domain = domain
        # Sync to server
        if self.server:
            self.server._current_domain = domain
        self._refresh_list()
        self._flash_status(f"Active: {domain}")

    def _copy_username(self):
        """Copy username of selected credential to clipboard."""
        domain = self._get_selected_domain()
        if not domain:
            return
        cred = self.storage.get(domain)
        if cred:
            self.root.clipboard_clear()
            self.root.clipboard_append(cred["username"])
            self._flash_status("Username copied to clipboard")
            # Auto-clear clipboard after 30 seconds
            self.root.after(30000, self._clear_clipboard)

    def _verify_master_password(self) -> bool:
        """Prompt user to re-enter master password. Returns True if correct."""
        pw = simpledialog.askstring(
            "Security Verification", "Enter master password to view sensitive data:",
            show="●", parent=self.root
        )
        if pw is None:
            return False
        if pw == self.storage._master_password:
            return True
        messagebox.showerror("Verification Failed", "Wrong master password", parent=self.root)
        return False

    def _copy_password(self):
        """Copy password of selected credential to clipboard (requires master password)."""
        domain = self._get_selected_domain()
        if not domain:
            return
        if not self._verify_master_password():
            return
        cred = self.storage.get(domain)
        if cred:
            self.root.clipboard_clear()
            self.root.clipboard_append(cred["password"])
            self._flash_status("Password copied (auto-clear in 30s)")
            # Auto-clear clipboard after 30 seconds
            self.root.after(30000, self._clear_clipboard)

    def _clear_clipboard(self):
        """Clear the clipboard for security."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append("")
        except Exception:
            pass

    def _change_password(self):
        """Change master password dialog."""
        dialog = ChangePasswordDialog(self.root, colors=self._colors())
        if dialog.result:
            old_pw, new_pw = dialog.result
            if self.storage.change_master_password(old_pw, new_pw):
                messagebox.showinfo("Success", "Master password changed")
            else:
                messagebox.showerror("Failed", "Current password is incorrect")

    def _lock_vault(self):
        """Lock the vault and return to unlock screen."""
        if self.server:
            self.server.stop()
            self.server = None
        self.storage.lock()
        self._current_domain = ""
        self._destroy_tray()
        self._show_unlock_screen()

    # ── Context Menu ───────────────────────────────────────────────────

    def _show_context_menu(self, event):
        """Show right-click context menu."""
        # Select the item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self._context_menu.post(event.x_root, event.y_root)

    # ── Status Flash ───────────────────────────────────────────────────

    def _flash_status(self, msg: str, duration: int = 3000):
        """Show a temporary status message."""
        if not hasattr(self, '_status_label'):
            return
        self._status_label.config(text=msg, fg=self.ACCENT)
        self.root.after(duration, self._refresh_list)

    # ── System Tray ────────────────────────────────────────────────────

    def _setup_tray(self):
        """Setup system tray icon."""
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Create a simple icon
            img = Image.new("RGB", (64, 64), self.ACCENT)
            draw = ImageDraw.Draw(img)
            # Draw a lock shape
            draw.rectangle([18, 28, 46, 52], fill="#1e1e2e")
            draw.arc([22, 12, 42, 36], 0, 180, fill="#1e1e2e", width=4)
            draw.rectangle([28, 36, 36, 44], fill=self.ACCENT)

            menu = pystray.Menu(
                pystray.MenuItem("Show Window", self._tray_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Lock", self._tray_lock),
                pystray.MenuItem("Quit", self._tray_quit),
            )

            self._tray_icon = pystray.Icon("vault", img, "USB Vault", menu)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except ImportError:
            # pystray or Pillow not available - skip tray
            pass

    def _destroy_tray(self):
        """Remove tray icon."""
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None

    def _tray_show(self, icon=None, item=None):
        """Show the main window from tray."""
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _tray_lock(self, icon=None, item=None):
        """Lock vault from tray."""
        self.root.after(0, self._lock_vault)

    def _tray_quit(self, icon=None, item=None):
        """Quit from tray."""
        self._quitting = True
        self.root.after(0, self._quit)

    # ── Window Management ──────────────────────────────────────────────

    def _on_close(self):
        """Handle window close button - ask user what to do."""
        if self._tray_icon and self.storage and self.storage.is_unlocked:
            choice = messagebox.askyesnocancel(
                "Close Window",
                "Minimize to system tray and keep running?\n\n"
                "Yes → Minimize to tray (AI can still use it)\n"
                "No → Quit completely\n"
                "Cancel → Stay open"
            )
            if choice is True:
                self.root.withdraw()  # Minimize to tray
            elif choice is False:
                self._quit()  # Full quit
            # choice is None = cancel, do nothing
        else:
            self._quit()

    def _quit(self):
        """Full quit - stop everything."""
        self._quitting = True
        if self.server:
            self.server.stop()
        self._destroy_tray()
        self.root.quit()
        self.root.destroy()

    def _center_window(self, w: int, h: int):
        """Center the window on screen."""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _colors(self) -> dict:
        """Return color dict for dialogs."""
        return {
            "bg": self.BG, "bg2": self.BG_SECONDARY, "bg_entry": self.BG_ENTRY,
            "fg": self.FG, "fg_dim": self.FG_DIM, "accent": self.ACCENT,
            "border": self.BORDER, "danger": self.DANGER,
        }

    def run(self):
        """Start the application."""
        self.root.mainloop()


class CredentialDialog:
    """Dialog for adding/editing a credential."""

    def __init__(self, parent, title="Add Credential", initial_domain="", initial_username="",
                 initial_password="", domain_readonly=False, colors=None,
                 verify_callback=None):
        self.result = None
        self._verify_callback = verify_callback
        c = colors or {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("420x320")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.configure(bg=c.get("bg", "#1e1e2e"))

        # Center
        self.dialog.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 420) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 320) // 2
        self.dialog.geometry(f"+{x}+{y}")

        bg = c.get("bg", "#1e1e2e")
        fg = c.get("fg", "#cdd6f4")
        fg_dim = c.get("fg_dim", "#6c7086")
        bg_entry = c.get("bg_entry", "#313145")
        accent = c.get("accent", "#89b4fa")

        frame = tk.Frame(self.dialog, bg=bg, padx=24, pady=20)
        frame.pack(fill="both", expand=True)

        # Domain
        tk.Label(frame, text="Domain / Service", bg=bg, fg=fg_dim,
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w")
        self._domain_var = tk.StringVar(value=initial_domain)
        domain_entry = tk.Entry(frame, textvariable=self._domain_var,
                                font=("Segoe UI", 11), bg=bg_entry, fg=fg,
                                insertbackground=fg, relief="solid", bd=1,
                                highlightthickness=1, highlightcolor=accent,
                                highlightbackground=c.get("border", "#45475a"))
        domain_entry.pack(fill="x", pady=(2, 12))
        if domain_readonly:
            domain_entry.config(state="readonly", readonlybackground=bg_entry)
        else:
            domain_entry.focus_set()

        # Username
        tk.Label(frame, text="Username / Email", bg=bg, fg=fg_dim,
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w")
        self._username_var = tk.StringVar(value=initial_username)
        username_entry = tk.Entry(frame, textvariable=self._username_var,
                                  font=("Segoe UI", 11), bg=bg_entry, fg=fg,
                                  insertbackground=fg, relief="solid", bd=1,
                                  highlightthickness=1, highlightcolor=accent,
                                  highlightbackground=c.get("border", "#45475a"))
        username_entry.pack(fill="x", pady=(2, 12))
        if domain_readonly:
            username_entry.focus_set()

        # Password
        tk.Label(frame, text="Password", bg=bg, fg=fg_dim,
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w")

        pw_frame = tk.Frame(frame, bg=bg)
        pw_frame.pack(fill="x", pady=(2, 20))

        self._password_var = tk.StringVar(value=initial_password)
        self._pw_show = False
        self._pw_entry = tk.Entry(pw_frame, textvariable=self._password_var,
                                  font=("Segoe UI", 11), bg=bg_entry, fg=fg,
                                  insertbackground=fg, relief="solid", bd=1, show="●",
                                  highlightthickness=1, highlightcolor=accent,
                                  highlightbackground=c.get("border", "#45475a"))
        self._pw_entry.pack(side="left", fill="x", expand=True)

        toggle_btn = tk.Button(pw_frame, text="👁", bg=bg_entry, fg=fg_dim,
                               relief="flat", font=("Segoe UI", 10), width=3,
                               command=self._toggle_password)
        toggle_btn.pack(side="right", padx=(6, 0))

        # Buttons
        btn_frame = tk.Frame(frame, bg=bg)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right")
        ttk.Button(btn_frame, text="Cancel", style="Ghost.TButton",
                   command=self.dialog.destroy).pack(side="right", padx=(0, 8))

        # Bind Enter to save
        self.dialog.bind("<Return>", lambda e: self._save())
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

        self.dialog.wait_window()

    def _toggle_password(self):
        """Toggle password visibility (requires master password to reveal)."""
        if not self._pw_show:
            # Revealing password - verify master password first
            if self._verify_callback and not self._verify_callback():
                return
        self._pw_show = not self._pw_show
        self._pw_entry.config(show="" if self._pw_show else "●")

    def _save(self):
        """Save and close."""
        domain = self._domain_var.get().strip()
        username = self._username_var.get().strip()
        password = self._password_var.get()

        if not domain:
            messagebox.showwarning("Missing Domain", "Please enter a domain or service name", parent=self.dialog)
            return
        if not username:
            messagebox.showwarning("Missing Username", "Please enter a username", parent=self.dialog)
            return
        if not password:
            messagebox.showwarning("Missing Password", "Please enter a password", parent=self.dialog)
            return

        self.result = (domain, username, password)
        self.dialog.destroy()


class ChangePasswordDialog:
    """Dialog for changing the master password."""

    def __init__(self, parent, colors=None):
        self.result = None
        c = colors or {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Change Master Password")
        self.dialog.geometry("380x280")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.configure(bg=c.get("bg", "#1e1e2e"))

        # Center
        self.dialog.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 380) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 280) // 2
        self.dialog.geometry(f"+{x}+{y}")

        bg = c.get("bg", "#1e1e2e")
        fg = c.get("fg", "#cdd6f4")
        fg_dim = c.get("fg_dim", "#6c7086")
        bg_entry = c.get("bg_entry", "#313145")
        accent = c.get("accent", "#89b4fa")
        border = c.get("border", "#45475a")

        frame = tk.Frame(self.dialog, bg=bg, padx=24, pady=20)
        frame.pack(fill="both", expand=True)

        # Current password
        tk.Label(frame, text="Current Password", bg=bg, fg=fg_dim,
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w")
        self._old_var = tk.StringVar()
        old_entry = tk.Entry(frame, textvariable=self._old_var, show="●",
                             font=("Segoe UI", 11), bg=bg_entry, fg=fg,
                             insertbackground=fg, relief="solid", bd=1,
                             highlightthickness=1, highlightcolor=accent,
                             highlightbackground=border)
        old_entry.pack(fill="x", pady=(2, 12))
        old_entry.focus_set()

        # New password
        tk.Label(frame, text="New Password", bg=bg, fg=fg_dim,
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w")
        self._new_var = tk.StringVar()
        tk.Entry(frame, textvariable=self._new_var, show="●",
                 font=("Segoe UI", 11), bg=bg_entry, fg=fg,
                 insertbackground=fg, relief="solid", bd=1,
                 highlightthickness=1, highlightcolor=accent,
                 highlightbackground=border).pack(fill="x", pady=(2, 12))

        # Confirm new password
        tk.Label(frame, text="Confirm New Password", bg=bg, fg=fg_dim,
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w")
        self._confirm_var = tk.StringVar()
        tk.Entry(frame, textvariable=self._confirm_var, show="●",
                 font=("Segoe UI", 11), bg=bg_entry, fg=fg,
                 insertbackground=fg, relief="solid", bd=1,
                 highlightthickness=1, highlightcolor=accent,
                 highlightbackground=border).pack(fill="x", pady=(2, 16))

        # Buttons
        btn_frame = tk.Frame(frame, bg=bg)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Confirm", style="Accent.TButton",
                   command=self._save).pack(side="right")
        ttk.Button(btn_frame, text="Cancel", style="Ghost.TButton",
                   command=self.dialog.destroy).pack(side="right", padx=(0, 8))

        self.dialog.bind("<Return>", lambda e: self._save())
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())
        self.dialog.wait_window()

    def _save(self):
        old_pw = self._old_var.get()
        new_pw = self._new_var.get()
        confirm = self._confirm_var.get()

        if not old_pw:
            messagebox.showwarning("Required", "Please enter current password", parent=self.dialog)
            return
        if len(new_pw) < 4:
            messagebox.showwarning("Too Short", "New password must be at least 4 characters", parent=self.dialog)
            return
        if new_pw != confirm:
            messagebox.showwarning("Mismatch", "New passwords do not match", parent=self.dialog)
            return

        self.result = (old_pw, new_pw)
        self.dialog.destroy()
