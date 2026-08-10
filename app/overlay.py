"""悬浮翻译窗：置顶、半透明、初音青色主题。

- 翻译历史累积：最多保留 2 条，新译文追加在下方；内容超高可滚动，滚轮回看最早一条
- 原文（小字灰）在上、译文（大字青）在下，条目间青色分隔线
- 顶部标题栏「✦ Miku 译文」可拖动；四角手柄可缩放窗口（尺寸持久化）
- 右键菜单退出
"""
from __future__ import annotations

from collections import deque
from html import escape

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QAction, QTextOption
from PySide6.QtWidgets import (
    QWidget, QFrame, QTextBrowser, QLabel, QVBoxLayout, QHBoxLayout,
    QMenu, QApplication,
)

ACCENT = "#39C5BB"
BG = "rgba(24, 44, 50, 240)"          # 内容区背景（高不透明度，文字更清晰）
ORIGINAL_COLOR = "#B0BEC5"
TRANSLATED_COLOR = "#7FF4E8"
MAX_HISTORY = 2                        # 不操作时最多显示条数
HANDLE = 14                            # 四角缩放手柄感应尺寸


class TranslationOverlay(QWidget):
    resize_done = Signal(int, int)     # 用户缩放结束 (w, h)，供持久化

    def __init__(self, font_size: int = 20, width: int = 480, height: int = 300):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._font_size = font_size
        self._history: deque[tuple[str, str]] = deque(maxlen=MAX_HISTORY)
        self._drag_offset: QPoint | None = None
        self._resize_mode: str | None = None   # tl/tr/bl/br
        self._resize_start: QPoint | None = None
        self._resize_geo = None
        self._min_w, self._min_h = 320, 220

        self.setMinimumSize(self._min_w, self._min_h)
        self.resize(max(width, self._min_w), max(height, self._min_h))
        self._build_ui()
        self._render()

    def _build_ui(self):
        outer = QFrame(self)
        outer.setGeometry(0, 0, self.width(), self.height())
        outer.setStyleSheet(f"""
            QFrame#card {{
                background:{BG}; border:1px solid {ACCENT}; border-radius:12px;
            }}
            QLabel#title {{
                color:#9BE8E2; font-size:12px; font-family:'Microsoft YaHei';
                background:transparent; padding:0 6px;
            }}
            QTextBrowser {{
                background:transparent; border:none; color:#D8F7F4;
                font-family:'Microsoft YaHei'; font-size:15px;
                selection-background-color:{ACCENT}; selection-color:#06282C;
            }}
            QScrollBar:vertical {{ background:rgba(13,31,35,200); width:10px; border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{ACCENT}; border-radius:5px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        outer.setObjectName("card")
        self._outer = outer

        lay = QVBoxLayout(outer)
        lay.setContentsMargins(14, 8, 14, 12)
        lay.setSpacing(6)

        title_row = QHBoxLayout()
        self.title_label = QLabel("✦ Miku 译文 (≧▽≦)♪")
        self.title_label.setObjectName("title")
        hint = QLabel("滚轮回看 ｜ 拖角调宽 ｜ 右键退出")
        hint.setObjectName("title")
        hint.setStyleSheet("color:#55777B;")
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(hint)
        lay.addLayout(title_row)

        self.browser = QTextBrowser()
        self.browser.setStyleSheet("font-size:15px;")
        # 智能换行：长单词/URL 允许任意处断行，中文按字符断行
        self.browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        lay.addWidget(self.browser, 1)

    # ---------------- 内容 ----------------
    def set_text(self, original: str, translated: str):
        """状态提示：直接显示一条，不加入历史（如"区域已框选"）。"""
        self._history.clear()
        self._history.append((original, translated))
        self._render()

    def add_translation(self, original: str, translated: str):
        """追加一条翻译记录，保留最近 MAX_HISTORY 条，滚动到最新。"""
        self._history.append((original, translated))
        self._render()
        vsb = self.browser.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    @staticmethod
    def _esc(s: str) -> str:
        """HTML 转义并保留换行结构（换行转 <br>）。"""
        return escape(s).replace("\n", "<br>")

    def _render(self):
        src_size = max(10, int(self._font_size * 0.7))
        tr_size = self._font_size
        parts = [f'<div style="font-family:\'Microsoft YaHei\'; word-break:break-word;">']
        for i, (orig, tr) in enumerate(self._history):
            if i:
                parts.append(
                    f'<div style="border-top:1px solid rgba(57,197,187,0.35);'
                    f' margin:8px 0;"></div>')
            if orig.strip():
                parts.append(
                    f'<div style="color:{ORIGINAL_COLOR}; font-size:{src_size}px;'
                    f' line-height:1.5;">{self._esc(orig)}</div>')
            parts.append(
                f'<div style="color:{TRANSLATED_COLOR}; font-size:{tr_size}px;'
                f' line-height:1.6; margin-top:4px;">{self._esc(tr)}</div>')
        parts.append('</div>')
        self.browser.setHtml("".join(parts))
        vsb = self.browser.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def set_font_size(self, size: int):
        self._font_size = size
        if hasattr(self, "browser"):
            self._render()

    # ---------------- 交互 ----------------
    def _hit_test(self, pos: QPoint) -> str | None:
        """命中检测：四角优先，其次四边，标题栏中部 move，内容区 None。"""
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        on_l = x <= HANDLE
        on_r = x >= w - HANDLE
        on_t = y <= HANDLE
        on_b = y >= h - HANDLE
        if on_l and on_t: return "tl"
        if on_r and on_t: return "tr"
        if on_l and on_b: return "bl"
        if on_r and on_b: return "br"
        if y < 34:
            return "move"   # 标题栏整条：拖动窗口
        if on_l: return "left"
        if on_r: return "right"
        if on_b: return "bottom"
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        mode = self._hit_test(e.position().toPoint())
        if mode == "move":
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return
        if mode:
            self._resize_mode = mode
            self._resize_start = e.globalPosition().toPoint()
            self._resize_geo = self.frameGeometry()

    def mouseMoveEvent(self, e):
        pos = e.globalPosition().toPoint()
        if self._drag_offset:
            self.move(pos - self._drag_offset)
            return
        if self._resize_mode and self._resize_start and self._resize_geo:
            g = self._resize_geo
            dx = pos.x() - self._resize_start.x()
            dy = pos.y() - self._resize_start.y()
            m = self._resize_mode
            # 八向调整：每边独立伸缩，同时约束最小尺寸
            l, t, r, b = g.left(), g.top(), g.right(), g.bottom()
            if m in ("tl", "left"):  l = min(l + dx, r - self._min_w)
            if m in ("tr", "right"): r = max(r + dx, l + self._min_w)
            if m in ("bl", "left"):  l = min(l + dx, r - self._min_w)
            if m in ("br", "right"): r = max(r + dx, l + self._min_w)
            if m in ("tl", "top"):   t = min(t + dy, b - self._min_h)
            if m in ("tr", "top"):   t = min(t + dy, b - self._min_h)
            if m in ("bl", "bottom"): b = max(b + dy, t + self._min_h)
            if m in ("br", "bottom"): b = max(b + dy, t + self._min_h)
            self.setGeometry(l, t, r - l, b - t)
            self._outer.setGeometry(0, 0, self.width(), self.height())
        else:
            # 悬停光标反馈
            hit = self._hit_test(e.position().toPoint())
            cursors = {
                "left": Qt.CursorShape.SizeHorCursor,
                "right": Qt.CursorShape.SizeHorCursor,
                "top": Qt.CursorShape.SizeVerCursor,
                "bottom": Qt.CursorShape.SizeVerCursor,
                "tl": Qt.CursorShape.SizeFDiagCursor,
                "br": Qt.CursorShape.SizeFDiagCursor,
                "tr": Qt.CursorShape.SizeBDiagCursor,
                "bl": Qt.CursorShape.SizeBDiagCursor,
                "move": Qt.CursorShape.SizeAllCursor,
            }
            self.setCursor(cursors.get(hit, Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, _):
        if self._resize_mode:
            self._resize_mode = None
            self._resize_start = None
            self._resize_geo = None
            self.resize_done.emit(self.width(), self.height())
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ---------------- 右键菜单 ----------------
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#1a2a2e; color:#d0f5f2; border:1px solid #39C5BB; }"
            "QMenu::item:selected { background:#39C5BB; color:#06282c; }")
        act_exit = QAction("退出 Miku 翻译", self)
        act_exit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_exit)
        menu.exec(e.globalPos())
