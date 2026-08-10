"""全局快捷键（Ctrl+1 弹出框选）。

用 Win32 RegisterHotKey + Qt nativeEventFilter 捕获 WM_HOTKEY：
- 不依赖第三方库，系统原生 API
- 程序未激活/最小化时也能触发（全局热键语义）
- 必须在 GUI 线程注册（消息队列归属该线程）
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging

from PySide6.QtCore import QAbstractNativeEventFilter

log = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
VK_1 = 0x31  # '1' 键


class GlobalHotkey(QAbstractNativeEventFilter):
    """注册 Ctrl+1；触发时回调 callback()。应用退出时需 unregister。"""

    def __init__(self, hotkey_id: int = 1, callback=None):
        super().__init__()
        self._id = hotkey_id
        self._callback = callback
        self._registered = False
        self._user32 = ctypes.windll.user32

    def register(self) -> bool:
        """在 GUI 线程注册热键。返回是否成功。"""
        ok = self._user32.RegisterHotKey(0, self._id, MOD_CONTROL, VK_1)
        self._registered = bool(ok)
        if not ok:
            log.warning("Ctrl+1 全局热键注册失败（可能被其他程序占用）")
        else:
            log.info("全局热键 Ctrl+1 已注册")
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
