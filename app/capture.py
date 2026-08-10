"""区域框选 + 静默截图。

- RegionSelector: 全屏半透明遮罩，鼠标拖拽画矩形选区（全局坐标，支持多屏）
- grab_region: 截取指定区域像素，返回 numpy 数组（BGR，RapidOCR 直接吃）
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QColor, QFont, QImage
from PySide6.QtWidgets import QWidget

from .config import Region

# 初音青色主题
ACCENT = QColor("#39C5BB")
ACCENT_DARK = QColor("#00A0B0")
HINT_TEXT = "拖拽框选要翻译的区域 ｜ ESC 取消"


class RegionSelector(QWidget):
    """全屏遮罩：选区外压暗，选区内清晰并带青色描边。"""

    region_selected = Signal(Region)   # 拖拽完成
    cancelled = Signal()               # ESC 取消

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        # 覆盖整个虚拟桌面（含所有屏幕）
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())

        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self._size_hint = (520, 280)  # 默认选区大小（直接点击时用）

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, e):
        self._origin = e.globalPosition().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, e):
        if self._origin:
            self._current = e.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if not self._origin:
            return
        rect = self._to_rect(self._origin, e.globalPosition().toPoint())
        self._origin = None
        self._current = None
        if rect.width() >= 8 and rect.height() >= 8:
            self.region_selected.emit(Region(rect.x(), rect.y(), rect.width(), rect.height()))
        else:
            # 点击未拖拽：以点击点为中心生成默认选区
            p = e.globalPosition().toPoint()
            r = QRect(p.x() - self._size_hint[0] // 2, p.y() - self._size_hint[1] // 2,
                      self._size_hint[0], self._size_hint[1])
            self.region_selected.emit(Region(r.x(), r.y(), r.width(), r.height()))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

    @staticmethod
    def _to_rect(a: QPoint, b: QPoint) -> QRect:
        return QRect(min(a.x(), b.x()), min(a.y(), b.y()),
                     abs(a.x() - b.x()), abs(a.y() - b.y())).normalized()

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 全局坐标 -> 窗口本地坐标
        top_left = self.geometry().topLeft()

        # 整个桌面压暗
        p.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._origin and self._current:
            sel = QRect(self._origin, self._current).normalized()
            sel = sel.translated(-top_left)
        else:
            sel = None

        if sel:
            # 选区区域挖空（透明），恢复亮度
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.fillRect(sel, Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            # 青色描边 + 四角
            pen = QPen(ACCENT, 2)
            p.setPen(pen)
            p.drawRect(sel.adjusted(0, 0, -1, -1))
            corner = 6
            for x, y in ((sel.left(), sel.top()), (sel.right(), sel.top()),
                         (sel.left(), sel.bottom()), (sel.right(), sel.bottom())):
                p.fillRect(x - corner // 2, y - corner // 2, corner, corner, ACCENT)
            # 尺寸提示
            p.setPen(QPen(QColor("white"), 1))
            font = QFont("Microsoft YaHei", 9)
            p.setFont(font)
            p.drawText(sel.left(), max(sel.top() - 8, 12), f"{sel.width()} x {sel.height()}")

        # 顶部操作提示
        p.setPen(Qt.GlobalColor.white)
        font = QFont("Microsoft YaHei", 11)
        p.setFont(font)
        tw = p.fontMetrics().horizontalAdvance(HINT_TEXT)
        p.fillRect(8, 8, tw + 24, 32, QColor(0, 0, 0, 160))
        p.drawText(20, 30, HINT_TEXT)


def grab_region(region: Region) -> np.ndarray | None:
    """截取选区，返回 BGR numpy 数组（RapidOCR 直接输入）。失败返回 None。"""
    if not region.is_set():
        return None
    center = QPoint(region.x + region.w // 2, region.y + region.h // 2)
    screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
    # 屏幕坐标偏移（副屏原点是全局偏移，grabWindow 返回的是该屏本地像素）
    offset = screen.geometry().topLeft()
    local = QRect(region.x - offset.x(), region.y - offset.y(),
                  region.w, region.h)
    # 限制在屏幕范围内
    local = local.intersected(screen.geometry().translated(-offset))
    if local.width() < 4 or local.height() < 4:
        return None
    pixmap = screen.grabWindow(0, local.x(), local.y(), local.width(), local.height())
    if pixmap.isNull():
        return None
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    ptr = img.constBits()
    # 行宽按 bytesPerLine 取（Qt 会做 4 字节对齐，width*3 会算错）
    bpl = img.bytesPerLine()
    raw = np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), bpl)
    arr = raw[:, : img.width() * 3].reshape(img.height(), img.width(), 3)
    return arr[:, :, ::-1].copy()  # RGB -> BGR
