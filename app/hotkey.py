"""全局快捷键（默认 Ctrl+1 弹出框选）。

用 Win32 RegisterHotKey + Qt nativeEventFilter 捕获 WM_HOTKEY：
- 不依赖第三方库，系统原生 API
- 程序未激活/最小化时也能触发（全局热键语义）
- 必须在 GUI 线程注册（消息队列归属该线程）
- 组合键可配置（modifiers + vk），支持 Ctrl/Ctrl+Alt + 数字键
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging

from PySide6.QtCore import QAbstractNativeEventFilter

log = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# 预设快捷键：显示名 -> (修饰键, 虚拟键码)
PRESET_HOTKEYS: dict[str, tuple[int, int]] = {
    "Ctrl+1": (MOD_CONTROL, 0x31),
    "Ctrl+2": (MOD_CONTROL, 0x32),
    "Ctrl+3": (MOD_CONTROL, 0x33),
    "Ctrl+4": (MOD_CONTROL, 0x34),
    "Ctrl+5": (MOD_CONTROL, 0x35),
    "Ctrl+Alt+1": (MOD_CONTROL | MOD_ALT, 0x31),
    "Ctrl+Alt+2": (MOD_CONTROL | MOD_ALT, 0x32),
    "Ctrl+Alt+3": (MOD_CONTROL | MOD_ALT, 0x33),
    "Shift+Ctrl+1": (MOD_CONTROL | MOD_SHIFT, 0x31),
    "Shift+Ctrl+2": (MOD_CONTROL | MOD_SHIFT, 0x32),
}


class GlobalHotkey(QAbstractNativeEventFilter):
    """注册全局热键；触发时回调 callback()。应用退出时需 unregister。"""

    def __init__(self, modifiers: int = MOD_CONTROL, key: int = 0x31,
                 hotkey_id: int = 1, callback=None):
        super().__init__()
        self._modifiers = modifiers
        self._key = key
        self._id = hotkey_id
        self._callback = callback
        self._registered = False
        self._user32 = ctypes.windll.user32

    def register(self) -> bool:
        """在 GUI 线程注册热键。返回是否成功。"""
        ok = self._user32.RegisterHotKey(0, self._id, self._modifiers, self._key)
        self._registered = bool(ok)
        if not ok:
            log.warning("全局热键注册失败（可能被其他程序占用）")
        else:
            log.info("全局热键已注册")
        return self._registered

    def unregister(self):
        if self._registered:
            self._user32.UnregisterHotKey(0, self._id)
            self._registered = False

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._id and self._callback:
                self._callback()
        return False, 0
