"""Cross-platform global hotkey listener and keyboard input simulator."""

from __future__ import annotations

import sys
import time
import platform
import threading


IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

# macOS key codes for F-keys (from Events.h)
_MAC_F8 = 100
_MAC_F9 = 101


class HotkeyManager:
    """Manages global hotkeys for credential input."""

    def __init__(self, on_username_requested, on_password_requested):
        """
        Args:
            on_username_requested: callback() -> str or None, returns username to type
            on_password_requested: callback() -> str or None, returns password to type
        """
        self._on_username = on_username_requested
        self._on_password = on_password_requested
        self._listener = None
        self._running = False
        self._tap = None  # macOS event tap reference

    def start(self):
        """Start listening for global hotkeys in a background thread."""
        if self._running:
            return

        if IS_MAC:
            self._start_mac()
        else:
            self._start_pynput()

        self._running = True

    def _start_pynput(self):
        """Start hotkey listener using pynput (Windows/Linux)."""
        from pynput import keyboard

        self._pressed_keys = set()

        def on_press(key):
            try:
                self._pressed_keys.add(key)
                self._check_hotkey(key)
            except Exception:
                pass

        def on_release(key):
            try:
                self._pressed_keys.discard(key)
            except Exception:
                pass

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _start_mac(self):
        """Start hotkey listener using Quartz CGEvent tap (macOS).

        Avoids pynput's TSM/InputSource calls that crash on macOS 15+
        when called from a background thread.
        """
        import Quartz

        def _callback(proxy, event_type, event, refcon):
            try:
                keycode = Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventKeycode
                )
                if keycode == _MAC_F9:
                    text = self._on_username()
                    if text:
                        threading.Timer(0.1, lambda: self._type_text(text)).start()
                elif keycode == _MAC_F8:
                    text = self._on_password()
                    if text:
                        threading.Timer(0.1, lambda: self._type_text(text)).start()
            except Exception:
                pass
            return event

        mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            _callback,
            None,
        )

        if self._tap is None:
            print("[Vault] Failed to create event tap. Grant Accessibility permission.")
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)

        def _run_tap():
            loop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopDefaultMode)
            Quartz.CGEventTapEnable(self._tap, True)
            Quartz.CFRunLoopRun()

        t = threading.Thread(target=_run_tap, daemon=True)
        t.start()

    def stop(self):
        """Stop listening."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._tap is not None:
            try:
                import Quartz
                Quartz.CGEventTapEnable(self._tap, False)
            except Exception:
                pass
            self._tap = None
        self._running = False

    def _check_hotkey(self, key):
        """Check if current key combo matches our hotkeys (pynput path)."""
        from pynput.keyboard import Key

        # F9 → username
        if key == Key.f9:
            text = self._on_username()
            if text:
                threading.Timer(0.1, lambda: self._type_text(text)).start()

        # F8 → password
        elif key == Key.f8:
            text = self._on_password()
            if text:
                threading.Timer(0.1, lambda: self._type_text(text)).start()

    def _type_text(self, text: str):
        """Type text character by character using keyboard simulation."""
        if IS_MAC:
            self._type_text_mac(text)
        else:
            self._type_text_pynput(text)

    def _type_text_pynput(self, text: str):
        """Type text using pynput (Windows/Linux)."""
        from pynput.keyboard import Controller, Key

        kb = Controller()

        # Release modifier keys first to avoid interference
        for mod_key in [Key.ctrl_l, Key.ctrl_r, Key.shift_l, Key.shift_r]:
            try:
                kb.release(mod_key)
            except Exception:
                pass

        time.sleep(0.05)

        # Type each character
        for char in text:
            kb.type(char)
            time.sleep(0.01)  # Small delay for reliability

    def _type_text_mac(self, text: str):
        """Type text using Quartz CGEvents (macOS). Avoids pynput TSM crash."""
        import Quartz

        time.sleep(0.05)

        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

        for char in text:
            # Create a keyboard event and set the Unicode string
            event_down = Quartz.CGEventCreateKeyboardEvent(source, 0, True)
            event_up = Quartz.CGEventCreateKeyboardEvent(source, 0, False)

            Quartz.CGEventKeyboardSetUnicodeString(event_down, len(char), char)
            Quartz.CGEventKeyboardSetUnicodeString(event_up, len(char), char)

            Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, event_down)
            time.sleep(0.005)
            Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, event_up)

            time.sleep(0.03)
