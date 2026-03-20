"""Build script for USB Vault - creates single-file executable."""
import subprocess
import sys
import platform
from pathlib import Path

def build():
    system = platform.system()
    use_console = "--console" in sys.argv
    project_dir = Path(__file__).parent.resolve()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console" if use_console else "--windowed",
        "--name", "vault",
        "--clean",
        "--noconfirm",
        "--hidden-import", "pynput.keyboard._win32" if system == "Windows" else "pynput.keyboard._darwin",
        "--hidden-import", "pynput.keyboard",
        "vault.py",
    ]

    print(f"Building for {system} ({'console' if use_console else 'GUI'} mode)...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(project_dir))

    if result.returncode == 0:
        ext = ".exe" if system == "Windows" else ""
        print(f"\nBuild successful! Output: dist/vault{ext}")
    else:
        print(f"\nBuild failed with code {result.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    build()
