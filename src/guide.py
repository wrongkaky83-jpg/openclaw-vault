"""Mac accessibility permission guide."""

import platform
import subprocess
import sys


IS_MAC = platform.system() == "Darwin"


def check_accessibility_permission() -> bool:
    """Check if the app has accessibility permission on macOS.
    Returns True on non-Mac platforms."""
    if not IS_MAC:
        return True

    try:
        # Use Apple's accessibility API to check permission
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process'],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def show_accessibility_guide():
    """Show a tkinter window with accessibility setup instructions for macOS."""
    if not IS_MAC:
        return

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("Vault - Accessibility Permission")
    root.geometry("520x420")
    root.resizable(False, False)

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 520) // 2
    y = (root.winfo_screenheight() - 420) // 2
    root.geometry(f"+{x}+{y}")

    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack(fill="both", expand=True)

    # Title
    tk.Label(frame, text="Accessibility Permission Required", font=("Helvetica", 16, "bold")).pack(pady=(0, 10))

    # Description
    desc = (
        "Vault needs Accessibility permission to:\n"
        "• Listen for global hotkeys (F9/F8)\n"
        "• Simulate keyboard input for auto-fill\n"
    )
    tk.Label(frame, text=desc, font=("Helvetica", 12), justify="left", anchor="w").pack(fill="x", pady=(0, 15))

    # Steps
    steps = (
        "Setup steps:\n\n"
        "1. Click the button below to open System Settings\n\n"
        "2. Go to Privacy & Security > Accessibility\n\n"
        "3. Click the lock icon to unlock (password required)\n\n"
        "4. Click \"+\" to add the Vault app\n\n"
        "5. Make sure the toggle next to Vault is ON\n\n"
        "6. Come back here and click \"Re-check\""
    )
    tk.Label(frame, text=steps, font=("Helvetica", 11), justify="left", anchor="w").pack(fill="x")

    # Buttons
    btn_frame = tk.Frame(frame)
    btn_frame.pack(fill="x", pady=(15, 0))

    def open_settings():
        """Open macOS Accessibility settings."""
        subprocess.Popen([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ])

    def recheck():
        """Re-check accessibility permission."""
        if check_accessibility_permission():
            messagebox.showinfo("Success", "Accessibility permission granted! Vault will start now.")
            root.destroy()
        else:
            messagebox.showwarning("Not Detected", "Please follow the steps above, then click \"Re-check\" again.")

    def quit_app():
        root.destroy()
        sys.exit(0)

    tk.Button(btn_frame, text="Open Settings", command=open_settings,
              font=("Helvetica", 12), bg="#2563eb", fg="white",
              width=14, height=1).pack(side="left", padx=(0, 10))

    tk.Button(btn_frame, text="Re-check", command=recheck,
              font=("Helvetica", 12), width=10, height=1).pack(side="left", padx=(0, 10))

    tk.Button(btn_frame, text="Quit", command=quit_app,
              font=("Helvetica", 12), width=8, height=1).pack(side="right")

    root.mainloop()
