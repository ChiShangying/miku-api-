"""设置对话框：目前先提供快捷键配置。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QComboBox, QFormLayout, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QDialogButtonBox,
)

from .hotkey import PRESET_HOTKEYS


class SettingsDialog(QDialog):
    """设置：全局快捷键选择。确定后热键由主窗口重新注册。"""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedWidth(360)
        self._cfg = cfg

        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        self.hotkey_combo = QComboBox()
        for name in PRESET_HOTKEYS:
            self.hotkey_combo.addItem(name)
        if cfg.hotkey in PRESET_HOTKEYS:
            self.hotkey_combo.setCurrentText(cfg.hotkey)
        form.addRow("全局快捷键（框选）", self.hotkey_combo)

        hint = QLabel("快捷键在软件未激活时也生效；\n若与其他软件冲突，可在此更换。")
        hint.setStyleSheet("color:#7A9BA0; font-size:11px;")
        form.addRow("", hint)
        lay.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

        self.setStyleSheet("""
            QDialog { background-color:#12262B; color:#D8F7F4;
                      font-family:'Microsoft YaHei'; font-size:13px; }
            QLabel { color:#D8F7F4; }
            QComboBox { background-color:#0D1F23; border:1px solid #2A6B6E;
                        border-radius:6px; padding:6px 10px; color:#D8F7F4; }
            QComboBox QAbstractItemView { background-color:#0D1F23; border:1px solid #39C5BB;
                                          selection-background-color:#39C5BB;
                                          selection-color:#06282C; }
            QPushButton { background-color:#0E3F47; color:#D8F7F4; border:1px solid #39C5BB;
                          border-radius:8px; padding:7px 18px; }
            QPushButton:hover { background-color:#39C5BB; color:#06282C; }
        """)

    def _on_accept(self):
        self._cfg.hotkey = self.hotkey_combo.currentText()
        self.accept()

    @staticmethod
    def current_hotkey(cfg) -> str:
        return cfg.hotkey
