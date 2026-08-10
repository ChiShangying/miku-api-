"""主控制窗口：无边框，横板壁纸背景，初音立绘，设置/最小化/关闭融入界面。"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QRect, QPoint, QRectF
from PySide6.QtGui import (
    QPixmap, QGuiApplication, QPainter, QPainterPath, QLinearGradient,
    QColor, QIcon,
)
from PySide6.QtWidgets import (
    QWidget, QApplication, QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton,
    QFormLayout, QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QSizePolicy,
)

from .config import AppConfig, Region, save_config, LANGS
from .capture import RegionSelector
from .controller import TranslationController
from .hotkey import GlobalHotkey, PRESET_HOTKEYS
from .ocr_engine import OcrEngine
from .overlay import TranslationOverlay
from .region_frame import RegionFrame
from .settings import SettingsDialog
from .translator import DeepSeekTranslator

log = logging.getLogger(__name__)
from .paths import asset_path
ASSETS = Path(__file__).resolve().parent.parent / "assets"  # 仅开发期兜底，运行用 asset_path()

# 字体策略：标题/按钮用华文琥珀（粗圆可爱），缺失时回退黑体（也够粗）；
# 正文幼圆，回退雅黑。所有符号只用这些字体都支持的（▶ ■ ★ ♪ ≧▽≦），不用 emoji。
FONT_HEAVY = '"STHupo","SimHei","Microsoft YaHei"'
FONT_BODY = '"YouYuan","Microsoft YaHei"'

QSS = f"""
QWidget {{ font-family:{FONT_BODY}; font-size:14px; color:#D8F7F4; }}
QLabel#title {{ font-family:{FONT_HEAVY}; color:#7FF4E8; font-size:24px; }}
QLabel#subtitle {{ color:#A8CDD2; font-size:12px; }}
QLabel#status {{ color:#9BE8E2; font-size:13px; }}
QLabel#formLabel {{ font-family:{FONT_BODY}; font-size:15px;
                   color:#B8F2EC; font-weight:bold; }}
QFrame#card {{ background-color:rgba(10, 26, 30, 200); border:1px solid #2A6B6E; border-radius:14px; }}
QLabel#sectionTitle {{ font-family:{FONT_HEAVY}; font-size:18px; color:#7FF4E8;
    border-bottom:2px solid rgba(57,197,187,130); padding-bottom:4px; }}
QPushButton {{ font-family:{FONT_HEAVY}; font-size:15px;
              background-color:rgba(14, 63, 71, 230); color:#D8F7F4;
              border:2px solid #39C5BB; border-radius:10px; padding:8px 14px; }}
QPushButton:hover {{ background-color:#39C5BB; color:#06282C; }}
QPushButton:pressed {{ background-color:#00A0B0; }}
QPushButton:disabled {{ background-color:#1A2A2E; color:#55777B; border-color:#2A4A4E; }}
QPushButton#primary {{ background-color:#39C5BB; color:#06282C; }}
QPushButton#primary:hover {{ background-color:#5FE0D5; }}
QPushButton#danger {{ background-color:rgba(92, 46, 46, 230); border-color:#E57373; }}
QPushButton#danger:hover {{ background-color:#E57373; color:#2B0A0A; }}
QPushButton#titleBtn {{ background:transparent; border:none; border-radius:6px;
                       color:#9BE8E2; font-size:14px; padding:2px 10px; }}
QPushButton#titleBtn:hover {{ background-color:rgba(57,197,187,90); color:#FFFFFF; }}
QPushButton#titleBtnClose:hover {{ background-color:#E57373; color:#FFFFFF; }}
QLineEdit, QComboBox, QSpinBox {{ font-family:{FONT_BODY}; font-size:15px;
    background-color:rgba(13, 31, 35, 230); border:2px solid #2A6B6E; border-radius:10px;
    padding:6px 12px; color:#EAFBF8; selection-background-color:#39C5BB; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color:#39C5BB; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color:#3E8A90; }}
QComboBox::drop-down {{ border:none; width:28px; }}
QComboBox::down-arrow {{ width:0; height:0; border-left:5px solid transparent;
    border-right:5px solid transparent; border-top:7px solid #39C5BB; margin-right:4px; }}
QComboBox QAbstractItemView {{ background-color:#0D1F23; border:1px solid #39C5BB;
    selection-background-color:#39C5BB; selection-color:#06282C; }}
QSpinBox::up-button, QSpinBox::down-button {{ background-color:#0E3F47; border:none; width:20px; }}
QSpinBox::up-arrow, QSpinBox::down-arrow {{ width:0; height:0; }}
"""


class MikuArt(QWidget):
    """初音立绘：圆角裁剪 + 底部青色光晕，自然融入。"""

    def __init__(self, pix: QPixmap, width: int = 210, height: int = 330,
                 crop_shift_y: int = -25, parent=None):
        """crop_shift_y: 裁剪窗口垂直偏移（负=上移，让主体头部上移露出）。"""
        super().__init__(parent)
        self._pix = pix
        self._crop_shift_y = crop_shift_y
        self.setFixedSize(width, height)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 整体轻微透明，更通透地融入壁纸（无渐变叠加）
        p.setOpacity(0.92)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.setClipPath(path)
        # 等比放大填充（居中裁剪，不变形）
        # 注意：drawPixmap 三参重载的 sourceRect 必须用 QRect（QRectF 会重载解析失败）
        scaled = self._pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
        src_y = min(max(round((scaled.height() - self.height()) / 2 + self._crop_shift_y), 0),
                    scaled.height() - self.height())
        src = QRect(round((scaled.width() - self.width()) / 2), src_y,
                    self.width(), self.height())
        p.drawPixmap(self.rect(), scaled, src)


class MainWindow(QWidget):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)  # 无边框：标题栏融入界面
        self.setWindowTitle("Miku 屏幕翻译")
        self.setWindowIcon(QIcon(str(asset_path("miku.png"))))
        self.setFixedSize(720, 540)  # 加宽，给右侧卡片充足空间（按钮可等宽铺满）

        self._wallpaper = QPixmap(str(asset_path("miku_wallpaper.png")))

        self.ocr = OcrEngine()
        self.translator = DeepSeekTranslator(
            api_key=cfg.api_key, base_url=cfg.base_url, model=cfg.model)
        self.overlay = TranslationOverlay(font_size=cfg.font_size,
                                          width=cfg.overlay_w, height=cfg.overlay_h)
        self.controller = TranslationController(self.ocr, self.translator, cfg)
        self._selector: RegionSelector | None = None
        self._region_frame: RegionFrame | None = None
        self._drag_offset: QPoint | None = None
        self._overlay_placed = False   # 输出框是否已定位过（之后位置只由用户拖动决定）

        # 全局热键（可配置）
        mod, key = PRESET_HOTKEYS.get(cfg.hotkey, PRESET_HOTKEYS["Ctrl+1"])
        self._hotkey = GlobalHotkey(mod, key, callback=self._on_select_region)
        if self._hotkey.register():
            QApplication.instance().installNativeEventFilter(self._hotkey)

        self._build_ui()
        self._bind_signals()
        self.setStyleSheet(QSS)
        self._refresh_region_label()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部标题栏（融入界面）：标题 + 设置/最小化/关闭
        title_bar = QFrame(self)
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet(
            "QFrame { background-color:rgba(8, 22, 26, 210); border:none; }")
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(14, 0, 6, 0)
        tb_label = QLabel("★ Miku 屏幕翻译 (≧▽≦)♪")
        tb_label.setObjectName("title")
        tb_label.setStyleSheet(f"font-family:{FONT_HEAVY}; font-size:16px; color:#7FF4E8;")
        tb.addWidget(tb_label)
        tb.addStretch(1)
        self.settings_btn = QPushButton("设置")
        self.min_btn = QPushButton("—")
        self.close_btn = QPushButton("×")
        for b in (self.settings_btn, self.min_btn, self.close_btn):
            b.setObjectName("titleBtn" if b is not self.close_btn else "titleBtnClose")
            b.setFixedSize(52, 30)
            tb.addWidget(b)
        self._title_bar = title_bar
        root.addWidget(title_bar)

        # 内容区
        content = QHBoxLayout()
        content.setContentsMargins(18, 14, 18, 16)
        content.setSpacing(18)

        # 左侧：初音立绘 + 卖萌标语（整体与右侧卡片顶对齐）
        left = QVBoxLayout()
        left.setSpacing(8)
        art = MikuArt(QPixmap(str(asset_path("miku_cutout.png"))), 240, 300, crop_shift_y=0)
        left.addWidget(art, alignment=Qt.AlignmentFlag.AlignTop)
        # 卖萌标语：合并为一个四行文本块，行距紧凑（文字→颜文字→文字→颜文字）
        moe = QLabel("「屏幕翻译，交给未来酱！」\n(≧▽≦)\n「看不懂的语言，就交给我吧」\n♪")
        moe.setStyleSheet(
            f"color:#A8F0E8; font-size:16px; font-family:{FONT_HEAVY}; line-height:1.25;"
            "background-color:rgba(8, 22, 26, 150); border-radius:10px; padding:8px 12px;")
        moe.setMaximumWidth(250)  # 限宽略大于最长行（16px 琥珀 ≈ 244px），防自动换行
        moe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        moe.setWordWrap(False)  # 换行只由文本中的 \n 决定
        left.addWidget(moe)
        content.addLayout(left)

        # 右侧：设置卡片（分区布局，占满右侧空间）
        card = QFrame()
        card.setObjectName("card")
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(20, 16, 20, 14)
        card_v.setSpacing(10)

        sec1 = QLabel("♪ 翻译设置")
        sec1.setObjectName("sectionTitle")
        card_v.addWidget(sec1)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(13)
        form.setHorizontalSpacing(10)  # 标签与输入框贴近
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.key_edit = QLineEdit(self.cfg.api_key)
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-...（DeepSeek 开放平台申请）")
        self.key_edit.setFixedHeight(38)
        form.addRow(self._label("API Key"), self.key_edit)

        self.model_edit = QLineEdit(self.cfg.model)
        self.model_edit.setPlaceholderText("deepseek-v4-flash")
        self.model_edit.setFixedHeight(38)
        form.addRow(self._label("模型"), self.model_edit)

        self.src_combo = QComboBox()
        for code, (name, _) in LANGS.items():
            self.src_combo.addItem(name, code)
        self.src_combo.setCurrentIndex(max(0, list(LANGS).index(self.cfg.source_lang)))
        self.tgt_combo = QComboBox()
        for code, (name, _) in LANGS.items():
            self.tgt_combo.addItem(name, code)
        self.tgt_combo.setCurrentIndex(max(0, list(LANGS).index(self.cfg.target_lang)))
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        lang_row.addWidget(self.src_combo)
        lang_row.addWidget(QLabel("→"), alignment=Qt.AlignmentFlag.AlignCenter)
        lang_row.addWidget(self.tgt_combo)
        lang_row.addStretch(1)
        for c in (self.src_combo, self.tgt_combo):
            c.setFixedHeight(38)
            c.setMinimumWidth(120)  # 两个下拉等宽
        form.addRow(self._label("语言"), lang_row)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(400, 10000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setValue(self.cfg.interval_ms)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setFixedHeight(38)
        form.addRow(self._label("刷新间隔"), self.interval_spin)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 40)
        self.font_spin.setValue(self.cfg.font_size)
        self.font_spin.setSuffix(" px")
        self.font_spin.setFixedHeight(38)
        form.addRow(self._label("译文字号"), self.font_spin)

        self.region_label = QLabel()
        self.region_label.setObjectName("status")
        form.addRow(self._label("翻译区域"), self.region_label)
        card_v.addLayout(form)

        # 分隔线
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color:rgba(57,197,187,90); border:none;")
        card_v.addWidget(line)

        sec2 = QLabel("♪ 操作")
        sec2.setObjectName("sectionTitle")
        card_v.addWidget(sec2)

        # 按钮（等宽均分，铺满整行）
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.select_btn = QPushButton("框选区域")
        self.start_btn = QPushButton("▶ 开始翻译")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        for b in (self.select_btn, self.start_btn, self.stop_btn):
            b.setFixedHeight(44)
            b.setFixedWidth(122)  # 固定等宽，3×122+2×10 恰好铺满卡片整行
            btns.addWidget(b)
        btns.addStretch(1)
        card_v.addLayout(btns)

        self.status_label = QLabel("就绪：填写 API Key 并框选区域后开始 (＾▽＾)")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)  # 长错误信息自动换行，防止撑宽卡片
        card_v.addWidget(self.status_label)
        card_v.addStretch(1)  # 状态区沉底，卡片占满

        content.addWidget(card, 1)
        root.addLayout(content, 1)

    def _label(self, text: str) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName("formLabel")
        lb.setMinimumWidth(66)  # 标签列统一宽度，输入框对齐
        return lb

    def _bind_signals(self):
        self.select_btn.clicked.connect(self._on_select_region)
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.min_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(self.close)
        self.settings_btn.clicked.connect(self._on_settings)
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

    # ---------------- 标题栏拖动 ----------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 42:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset:
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _):
        self._drag_offset = None

    # ---------------- 背景绘制 ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 壁纸等比裁剪铺满（KeepAspectRatioByExpanding = 铺满后居中裁剪）
        scaled = self._wallpaper.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                        Qt.TransformationMode.SmoothTransformation)
        src = QRect((scaled.width() - self.width()) // 2,
                    (scaled.height() - self.height()) // 2,
                    self.width(), self.height())
        p.drawPixmap(self.rect(), scaled, src)
        # 深色叠加，保证控件可读性
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))

    # ---------------- 设置 ----------------
    def _on_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            save_config(self.cfg)
            self._apply_hotkey()

    def _apply_hotkey(self):
        """按新配置重注册全局热键。"""
        QApplication.instance().removeNativeEventFilter(self._hotkey)
        self._hotkey.unregister()
        mod, key = PRESET_HOTKEYS.get(self.cfg.hotkey, PRESET_HOTKEYS["Ctrl+1"])
        self._hotkey = GlobalHotkey(mod, key, callback=self._on_select_region)
        if self._hotkey.register():
            QApplication.instance().installNativeEventFilter(self._hotkey)
            self.status_label.setText(f"快捷键已更新：{self.cfg.hotkey}")
        else:
            self.status_label.setText(f"⚠ 快捷键 {self.cfg.hotkey} 注册失败（可能被占用）")

    # ---------------- 框选与区域框 ----------------
    def _on_select_region(self):
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
        # 输出框：首次框选定位一次，之后保持用户拖动的位置
        self._ensure_overlay_placed(region)
        self.overlay.set_text("", "区域已框选，点框上“▶ 开始翻译”")

    def _ensure_overlay_placed(self, region: Region | None):
        """输出框只定位一次；后续框选/区域调整不再移动它。"""
        if not self._overlay_placed:
            if region is not None and region.is_set():
                self._position_overlay(region)
            self._overlay_placed = True
        self.overlay.show()

    def _on_region_cancelled(self):
        self._selector.close()
        self._selector = None
        self.show()

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
        """区域框被拖动/缩放：只同步配置，输出框位置不受影响。"""
        self.cfg.region = region
        save_config(self.cfg)
        self._refresh_region_label()

    def _on_region_frame_close(self):
        """关闭区域框：停止翻译并清空区域；输出框保留（由自身按钮/退出关闭）。"""
        if self.controller.is_running():
            self._on_stop()
        if self._region_frame:
            self._region_frame.close()
            self._region_frame = None
        self.cfg.region = Region()
        save_config(self.cfg)
        self._refresh_region_label()

    def _refresh_region_label(self):
        r = self.cfg.region
        if isinstance(r, dict):
            r = Region(r.get("x"), r.get("y"), r.get("w"), r.get("h"))
        if r.is_set():
            self.region_label.setText(f"({r.x}, {r.y})  {r.w}×{r.h}")
        else:
            self.region_label.setText("未框选")

    def _position_overlay(self, region: Region):
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

    # ---------------- 翻译控制 ----------------
    def _on_start(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "缺少 API Key",
                                "请先在 DeepSeek 开放平台申请 API Key 并填入左侧输入框。")
            return
        self.cfg.api_key = key
        self.cfg.model = self.model_edit.text().strip() or "deepseek-v4-flash"
        self.cfg.source_lang = self.src_combo.currentData()
        self.cfg.target_lang = self.tgt_combo.currentData()
        self.cfg.interval_ms = self.interval_spin.value()
        self.cfg.font_size = self.font_spin.value()
        save_config(self.cfg)

        self.translator.set_api_key(key)
        self.overlay.set_font_size(self.cfg.font_size)
        if isinstance(self.cfg.region, dict):
            self.cfg.region = Region(self.cfg.region.get("x"), self.cfg.region.get("y"),
                                     self.cfg.region.get("w"), self.cfg.region.get("h"))
        self._ensure_overlay_placed(self.cfg.region if self.cfg.region.is_set() else None)
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
            self.overlay.add_translation(original, translated)
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
