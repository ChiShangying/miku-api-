"""常驻区域框：选区边框常驻显示 + 顶部操作工具条。

- 青色描边 + 四角缩放手柄，框内拖动可移动选区
- 工具条在选区上方（不遮挡内容）：▶ 开始翻译 / ■ 停止 / ✕ 关闭
- 拖动、缩放结果通过 region_changed 信号回传
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QFrame, QPushButton, QHBoxLayout, QLabel

from .config import Region

ACCENT = QColor("#39C5BB")
HANDLE = 8                 # 四角手柄尺寸
BAR_H = 38                 # 工具条高度
BAR_GAP = 10               # 工具条与选区上边的间距
PAD_TOP = BAR_H + BAR_GAP  # 窗口顶部扩展（容纳工具条）


class RegionFrame(QWidget):
    region_changed = Signal(object)   # Region（移动/缩放后）
    start_requested = Signal()
    stop_requested = Signal()
    close_requested = Signal()

    def __init__(self, region: Region):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("翻译区域")

        self._region = Region(region.x, region.y, region.w, region.h)
        self._mode: str | None = None   # None / move / tl / tr / bl / br
        self._drag_start: QPoint | None = None
        self._geo_start: QRect | None = None

        self._build_bar()
        self._bar.hide()  # 默认隐藏，鼠标悬停时才显现
        self._sync_geometry()

    # ---------------- 工具条 ----------------
    def _build_bar(self):
        self._bar = QFrame(self)
        self._bar.setStyleSheet(
            "QFrame { background:rgba(13,31,35,235); border:1px solid #39C5BB;"
            " border-radius:8px; }"
            "QPushButton { background:transparent; color:#D8F7F4; border:none;"
            " padding:4px 10px; font-size:12px; font-family:'Microsoft YaHei'; }"
            "QPushButton:hover { color:#06282C; background:#39C5BB; border-radius:5px; }")
        lay = QHBoxLayout(self._bar)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(2)

        self.size_label = QLabel()
        self.size_label.setStyleSheet(
            "color:#9BE8E2; font-size:11px; font-family:'Microsoft YaHei';"
            "padding:0 4px; background:transparent;")
        lay.addWidget(self.size_label)

        lay.addStretch(1)

        self.start_btn = QPushButton("▶ 开始翻译")
        self.stop_btn = QPushButton("■ 停止")
        self.close_btn = QPushButton("✕ 关闭")
        self.start_btn.clicked.connect(self.start_requested)
        self.stop_btn.clicked.connect(self.stop_requested)
        self.close_btn.clicked.connect(self.close_requested)
        lay.addWidget(self.start_btn)
        lay.addWidget(self.stop_btn)
        lay.addWidget(self.close_btn)
        self._bar.setGeometry(0, 0, 1, 1)  # 尺寸由 _sync_geometry 设置

    # ---------------- 几何同步 ----------------
    def _sync_geometry(self):
        """窗口 = 选区 + 顶部工具条区。"""
        r = self._region
        self.setGeometry(r.x, r.y - PAD_TOP, r.w, r.h + PAD_TOP)
        self._bar.setGeometry(0, 0, r.w, BAR_H)
        self.size_label.setText(f"{r.w}×{r.h}")

    def current_region(self) -> Region:
        return self._region

    def set_region(self, region: Region):
        self._region = Region(region.x, region.y, region.w, region.h)
        self._sync_geometry()
        self.update()

    # ---------------- 选区内部矩形 ----------------
    def _inner_rect(self) -> QRect:
        """选区边框矩形：整体内缩 2px，避免描边画出窗口被裁剪（此前右/下边框消失）。"""
        return QRect(2, PAD_TOP + 2, max(1, self._region.w - 4), max(1, self._region.h - 4))

    def _corner_at(self, pos: QPoint) -> str | None:
        """判断点是否落在四角手柄上。"""
        inner = self._inner_rect()
        corners = {
            "tl": QPoint(inner.left(), inner.top()),
            "tr": QPoint(inner.right(), inner.top()),
            "bl": QPoint(inner.left(), inner.bottom()),
            "br": QPoint(inner.right(), inner.bottom()),
        }
        for name, c in corners.items():
            if abs(pos.x() - c.x()) <= HANDLE and abs(pos.y() - c.y()) <= HANDLE:
                return name
        return None

    # ---------------- 鼠标交互 ----------------
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._mode = self._corner_at(e.position().toPoint())
        if self._mode is None and self._inner_rect().contains(e.position().toPoint()):
            self._mode = "move"          # 框内拖动 = 移动选区
        self._drag_start = e.globalPosition().toPoint()
        self._geo_start = QRect(self.geometry())

    def mouseMoveEvent(self, e):
        if not self._mode or not self._drag_start or not self._geo_start:
            return
        delta = e.globalPosition().toPoint() - self._drag_start
        g = self._geo_start
        if self._mode == "move":
            self.move(g.topLeft() + delta)
        elif self._mode == "tl":
            self.setGeometry(g.left() + delta.x(), g.top() + delta.y(),
                             max(40, g.width() - delta.x()), max(40, g.height() - delta.y()))
        elif self._mode == "tr":
            self.setGeometry(g.left(), g.top() + delta.y(),
                             max(40, g.width() + delta.x()), max(40, g.height() - delta.y()))
        elif self._mode == "bl":
            self.setGeometry(g.left() + delta.x(), g.top(),
                             max(40, g.width() - delta.x()), max(40, g.height() + delta.y()))
        elif self._mode == "br":
            self.setGeometry(g.left(), g.top(),
                             max(40, g.width() + delta.x()), max(40, g.height() + delta.y()))
        self._update_region_from_geometry()

    def mouseReleaseEvent(self, _):
        self._mode = None
        self._drag_start = None
        self._geo_start = None
        self.region_changed.emit(self._region)

    def _update_region_from_geometry(self):
        g = self.geometry()
        self._region = Region(g.x(), g.y() + PAD_TOP, g.width(),
                              max(1, g.height() - PAD_TOP))
        self._bar.setGeometry(0, 0, g.width(), BAR_H)
        self.size_label.setText(f"{self._region.w}×{self._region.h}")
        self.update()

    # ---------------- 悬停显示工具条 ----------------
    def enterEvent(self, e):
        self._bar.show()
        self._bar.raise_()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._bar.hide()
        super().leaveEvent(e)

    # ---------------- 绘制 ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inner = self._inner_rect()
        # 选区描边
        pen = QPen(ACCENT, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(inner)
        # 四角手柄
        p.setBrush(ACCENT)
        p.setPen(Qt.PenStyle.NoPen)
        for x, y in ((inner.left(), inner.top()), (inner.right(), inner.top()),
                     (inner.left(), inner.bottom()), (inner.right(), inner.bottom())):
            p.drawRect(x - HANDLE // 2, y - HANDLE // 2, HANDLE, HANDLE)
