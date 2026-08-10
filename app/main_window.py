"""主控制窗口：初音立绘 + 设置区 + 控制按钮。"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QApplication, QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton,
    QFormLayout, QVBoxLayout, QHBoxLayout, QFrame, QMessageBox,
)

from .config import AppConfig, Region, save_config, LANGS
from .capture import RegionSelector
from .controller import TranslationController
from .hotkey import GlobalHotkey
from .ocr_engine import OcrEngine
from .overlay import TranslationOverlay
from .region_frame import RegionFrame
from .translator import DeepSeekTranslator

log = logging.getLogger(__name__)
ASSETS = Path(__file__).resolve().parent.parent / "assets"

QSS = """
QWidget { background-color:#12262B; color:#D8F7F4; font-family:"Microsoft YaHei"; font-size:13px; }
QLabel#title { color:#7FF4E8; font-size:20px; font-weight:bold; }
QLabel#subtitle { color:#7A9BA0; font-size:11px; }
QLabel#status { color:#9BE8E2; font-size:12px; }
QFrame#card { background-color:#0E2024; border:1px solid #2A6B6E; border-radius:10px; }
QPushButton { background-color:#0E3F47; color:#D8F7F4; border:1px solid #39C5BB; border-radius:8px; padding:9px 20px; }
QPushButton:hover { background-color:#39C5BB; color:#06282C; }
QPushButton:pressed { background-color:#00A0B0; }
QPushButton:disabled { background-color:#1A2A2E; color:#55777B; border-color:#2A4A4E; }
QPushButton#primary { background-color:#39C5BB; color:#06282C; font-weight:bold; }
QPushButton#primary:hover { background-color:#5FE0D5; }
QPushButton#danger { background-color:#5C2E2E; border-color:#E57373; }
QPushButton#danger:hover { background-color:#E57373; color:#2B0A0A; }
QLineEdit, QComboBox, QSpinBox { background-color:#0D1F23; border:1px solid #2A6B6E; border-radius:6px; padding:6px 10px; color:#D8F7F4; selection-background-color:#39C5BB; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color:#39C5BB; }
QComboBox QAbstractItemView { background-color:#0D1F23; border:1px solid #39C5BB; selection-background-color:#39C5BB; selection-color:#06282C; }
QSpinBox::up-button, QSpinBox::down-button { background-color:#0E3F47; border:none; width:18px; }
"""


class MainWindow(QWidget):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Miku 屏幕翻译 ｜ 实时OCR翻译")
        self.setFixedSize(560, 430)

        self.ocr = OcrEngine()
        self.translator = DeepSeekTranslator(
            api_key=cfg.api_key, base_url=cfg.base_url, model=cfg.model)
        self.overlay = TranslationOverlay(font_size=cfg.font_size,
                                          width=cfg.overlay_w, height=cfg.overlay_h)
        self.controller = TranslationController(self.ocr, self.translator, cfg)
        self._selector: RegionSelector | None = None
        self._region_frame: RegionFrame | None = None

        # 全局热键 Ctrl+1 弹出框选
        self._hotkey = GlobalHotkey(callback=self._on_select_region)
        if self._hotkey.register():
            QApplication.instance().installNativeEventFilter(self._hotkey)

        self._build_ui()
        self._bind_signals()
        self.setStyleSheet(QSS)
        self._refresh_region_label()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(16)

        # ---- 左侧：初音立绘 ----
        left = QFrame()
        left.setObjectName("card")
        left.setFixedWidth(190)
        v = QVBoxLayout(left)
        v.setContentsMargins(10, 10, 10, 10)
        art = QLabel()
        pix = QPixmap(str(ASSETS / "miku_01_flower.jpg"))
        art.setPixmap(pix.scaled(170, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation))
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(art)
        name = QLabel("初音ミク\nHatsune Miku")
        name.setObjectName("title")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(name)
        v.addWidget(QLabel("「屏幕翻译，交给未来酱！」"), alignment=Qt.AlignmentFlag.AlignCenter)
        v.addStretch(1)
        root.addWidget(left)

        # ---- 右侧：设置区 ----
        right = QVBoxLayout()
        right.setSpacing(10)
        title = QLabel("实时屏幕翻译")
        title.setObjectName("title")
        right.addWidget(title)
        right.addWidget(QLabel("框选屏幕区域 → 自动OCR识别 → AI实时翻译"))

        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.key_edit = QLineEdit(self.cfg.api_key)
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-...（DeepSeek 开放平台申请）")
        form.addRow("API Key", self.key_edit)

        self.model_edit = QLineEdit(self.cfg.model)
        self.model_edit.setPlaceholderText("deepseek-v4-flash")
        form.addRow("模型", self.model_edit)

        self.src_combo = QComboBox()
        for code, (name, _) in LANGS.items():
            self.src_combo.addItem(name, code)
        self.src_combo.setCurrentIndex(max(0, list(LANGS).index(self.cfg.source_lang)))
        self.tgt_combo = QComboBox()
        for code, (name, _) in LANGS.items():
            self.tgt_combo.addItem(name, code)
        self.tgt_combo.setCurrentIndex(max(0, list(LANGS).index(self.cfg.target_lang)))
        lang_row = QHBoxLayout()
        lang_row.addWidget(self.src_combo)
        lang_row.addWidget(QLabel("→"))
        lang_row.addWidget(self.tgt_combo)
        lang_row.addStretch(1)
        form.addRow("语言", lang_row)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(400, 10000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setValue(self.cfg.interval_ms)
        self.interval_spin.setSuffix(" ms")
        form.addRow("刷新间隔", self.interval_spin)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 40)
        self.font_spin.setValue(self.cfg.font_size)
        self.font_spin.setSuffix(" px")
        form.addRow("译文字号", self.font_spin)

        self.region_label = QLabel()
        self.region_label.setStyleSheet("color:#9BE8E2;")
        form.addRow("翻译区域", self.region_label)

        right.addWidget(card)

        # ---- 按钮 ----
        btns = QHBoxLayout()
        self.select_btn = QPushButton("📌 框选区域")
        self.start_btn = QPushButton("▶ 开始翻译")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        for b in (self.select_btn, self.start_btn, self.stop_btn):
            btns.addWidget(b)
        right.addLayout(btns)

        self.status_label = QLabel("就绪：填写 API Key 并框选区域后开始")
        self.status_label.setObjectName("status")
        right.addWidget(self.status_label)
        right.addStretch(1)
        root.addLayout(right, 1)

    def _bind_signals(self):
        self.select_btn.clicked.connect(self._on_select_region)
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.interval_spin.valueChanged.connect(
            lambda ms: (setattr(self.cfg, "interval_ms", ms),
                        self.controller.set_interval(ms)))
        self.font_spin.valueChanged.connect(
            lambda v: (setattr(self.cfg, "font_size", v), self.overlay.set_font_size(v)))

        self.controller.status_changed.connect(self.status_label.setText)
        self.controller.translated.connect(self._on_translated)
        self.controller.ocr_changed.connect(self._on_ocr)
        self.controller.failed.connect(self._on_failed)
        self.overlay.resize_done.connect(self._on_overlay_resized)

    # ---------------- 行为 ----------------
    def _on_select_region(self):
        # 重新框选前收起旧区域框
        if self._region_frame:
            self._region_frame.close()
            self._region_frame = None
        self.hide()
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region_picked)
        self._selector.cancelled.connect(self._on_region_cancelled)
        self._selector.show()
        self._selector.activateWindow()
        self._selector.setFocus()

    def _on_region_picked(self, region: Region):
        self.cfg.region = region
        save_config(self.cfg)
        self._selector.close()
        self._selector = None
        self.show()
        self._refresh_region_label()
        self._show_region_frame(region)
        self._position_overlay(region)
        self.overlay.set_text("", "区域已框选，点框上“▶ 开始翻译”或主窗按钮")

    def _on_region_cancelled(self):
        self._selector.close()
        self._selector = None
        self.show()

    # ---------------- 常驻区域框 ----------------
    def _show_region_frame(self, region: Region):
        if self._region_frame:
            self._region_frame.set_region(region)
            self._region_frame.show()
            self._region_frame.raise_()
        else:
            self._region_frame = RegionFrame(region)
            self._region_frame.region_changed.connect(self._on_region_changed)
            self._region_frame.start_requested.connect(self._on_start)
            self._region_frame.stop_requested.connect(self._on_stop)
            self._region_frame.close_requested.connect(self._on_region_frame_close)
            self._region_frame.show()

    def _on_region_changed(self, region: Region):
        """框被拖动/缩放后：同步配置，悬浮窗跟随。"""
        self.cfg.region = region
        save_config(self.cfg)
        self._refresh_region_label()
        self._position_overlay(region)

    def _on_region_frame_close(self):
        """✕ 关闭区域框：停止翻译并清空区域。"""
        if self.controller.is_running():
            self._on_stop()
        if self._region_frame:
            self._region_frame.close()
            self._region_frame = None
        self.cfg.region = Region()
        save_config(self.cfg)
        self._refresh_region_label()
        self.overlay.hide()

    def _refresh_region_label(self):
        r = self.cfg.region
        if isinstance(r, dict):
            r = Region(r.get("x"), r.get("y"), r.get("w"), r.get("h"))
        if r.is_set():
            self.region_label.setText(f"({r.x}, {r.y})  {r.w}×{r.h}")
        else:
            self.region_label.setText("未框选")

    def _position_overlay(self, region: Region):
        """悬浮窗放在选区正下方（空间不足则上方），限制在屏幕内。"""
        screen = QGuiApplication.screenAt(QPoint(region.x + region.w // 2,
                                                 region.y + region.h // 2))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        geo = screen.geometry()
        x = region.x + (region.w - self.overlay.width()) // 2
        y = region.y + region.h + 12
        if y + self.overlay.height() > geo.bottom():
            y = region.y - self.overlay.height() - 12
        x = max(geo.left(), min(x, geo.right() - self.overlay.width()))
        y = max(geo.top(), y)
        self.overlay.move(x, y)
        self.overlay.show()

    def _on_start(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "缺少 API Key",
                                "请先在 DeepSeek 开放平台申请 API Key 并填入左侧输入框。")
            return
        self.cfg.api_key = key
        self.cfg.model = self.model_edit.text().strip() or "deepseek-chat"
        self.cfg.source_lang = self.src_combo.currentData()
        self.cfg.target_lang = self.tgt_combo.currentData()
        self.cfg.interval_ms = self.interval_spin.value()
        self.cfg.font_size = self.font_spin.value()
        save_config(self.cfg)

        self.translator.set_api_key(key)
        self.overlay.set_font_size(self.cfg.font_size)
        # 悬浮窗对齐选区（支持从配置恢复的区域）
        if isinstance(self.cfg.region, dict):
            self.cfg.region = Region(self.cfg.region.get("x"), self.cfg.region.get("y"),
                                     self.cfg.region.get("w"), self.cfg.region.get("h"))
        if self.cfg.region.is_set():
            self._position_overlay(self.cfg.region)
        self.controller.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.select_btn.setEnabled(False)
        if self._region_frame:
            self._region_frame.start_btn.setEnabled(False)
            self._region_frame.stop_btn.setEnabled(True)

    def _on_stop(self):
        self.controller.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_btn.setEnabled(True)
        if self._region_frame:
            self._region_frame.start_btn.setEnabled(True)
            self._region_frame.stop_btn.setEnabled(False)

    def _on_translated(self, original: str, translated: str):
        if translated:
            self.overlay.add_translation(original, translated)  # 追加进历史，保留最近2条
            self.status_label.setText(f"✓ 已翻译（{len(translated)}字）")
        else:
            self.overlay.set_text(original, "区域无文字")

    def _on_overlay_resized(self, w: int, h: int):
        self.cfg.overlay_w = w
        self.cfg.overlay_h = h
        save_config(self.cfg)

    def _on_ocr(self, text: str):
        if text.strip():
            self.status_label.setText(f"识别到 {len(text)} 字符…")

    def _on_failed(self, msg: str):
        self.status_label.setText(f"⚠ {msg[:60]}")
        log.error("流程错误: %s", msg)

    # ---------------- 关闭 ----------------
    def closeEvent(self, e):
        self.controller.shutdown()
        if self._region_frame:
            self._region_frame.close()
        self.overlay.close()
        QApplication.instance().removeNativeEventFilter(self._hotkey)
        self._hotkey.unregister()
        super().closeEvent(e)
