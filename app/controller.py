"""翻译流程控制器：定时 截图→OCR→翻译 循环。

线程模型：
- 截图在主线程（QScreen.grabWindow 是 GUI 线程 API，且耗时毫秒级）
- OCR + AI 翻译在工作线程（耗时秒级，绝不能卡 UI）
- 信号用 Qt 队列连接跨线程传递 numpy 数组 / 字符串
去重：OCR 文本指纹不变 → 不调翻译 API（省 token）；指纹变了才翻译。
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from .capture import grab_region

log = logging.getLogger(__name__)


class TranslationWorker(QObject):
    """运行在工作线程：OCR + 翻译。"""

    ocr_text = Signal(str)            # 本次识别出的原文
    translated = Signal(str, str)     # (原文, 译文)
    failed = Signal(str)
    done = Signal()                   # 一个周期完成

    def __init__(self, ocr, translator, cfg):
        super().__init__()
        self._ocr = ocr
        self._translator = translator
        self._cfg = cfg
        self._last_fp: int | None = None
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    @Slot(object)
    def process(self, img):
        """一个处理周期：OCR → 指纹对比 → 翻译。img 为 BGR numpy。"""
        if self._busy:
            return
        self._busy = True
        try:
            lines = self._ocr.recognize(img, self._cfg.ocr_lang)
            text = "\n".join(lines)
            self.ocr_text.emit(text)
            fp = hash(text)
            if fp == self._last_fp:
                return  # 内容没变，不重复翻译
            self._last_fp = fp
            if not text.strip():
                self.translated.emit("", "")
                return
            result = self._translator.translate(
                text, source=self._cfg.source_lang, target=self._cfg.target_lang)
            self.translated.emit(text, result)
        except Exception as e:  # noqa: BLE001 - 所有异常都上报 UI
            log.exception("处理周期失败")
            self.failed.emit(str(e))
        finally:
            self._busy = False
            self.done.emit()


class TranslationController(QObject):
    """主线程侧调度器。"""

    status_changed = Signal(str)
    ocr_changed = Signal(str)
    translated = Signal(str, str)
    failed = Signal(str)
    _to_worker = Signal(object)        # 发给工作线程的截图（BGR numpy）

    def __init__(self, ocr, translator, cfg):
        super().__init__()
        self._ocr = ocr
        self._translator = translator
        self._cfg = cfg

        self._thread = QThread(self)
        self._worker = TranslationWorker(ocr, translator, cfg)
        self._worker.moveToThread(self._thread)
        self._thread.start()

        # 跨线程信号
        self._to_worker.connect(self._worker.process)
        self._worker.ocr_text.connect(self.ocr_changed)
        self._worker.translated.connect(self.translated)
        self._worker.failed.connect(self.failed)
        self._worker.done.connect(self._on_done)

        self._timer = QTimer(self)
        self._timer.setInterval(cfg.interval_ms)
        self._timer.timeout.connect(self._tick)
        self._running = False

    # ---------- 生命周期 ----------
    def start(self):
        if not self._cfg.region.is_set():
            self.failed.emit("请先框选要翻译的区域")
            return
        self._worker._last_fp = None  # 重新开始后首次必定翻译
        self._running = True
        self._timer.start(self._cfg.interval_ms)
        self.status_changed.emit("翻译中…（Ctrl+C 或点停止结束）")

    def stop(self):
        self._running = False
        self._timer.stop()
        self.status_changed.emit("已停止")

    def is_running(self) -> bool:
        return self._running

    def set_interval(self, ms: int):
        if self._running:
            self._timer.start(ms)

    def shutdown(self):
        self.stop()
        self._thread.quit()
        self._thread.wait(3000)

    # ---------- 定时周期 ----------
    def _tick(self):
        if self._worker.busy:
            return  # 上一周期未完成则跳过，防堆积
        img = grab_region(self._cfg.region)
        if img is None:
            self.failed.emit("截图失败：区域可能超出屏幕范围")
            return
        self._to_worker.emit(img)

    def _on_done(self):
        """周期完成：若运行中且已空闲，立即进入下一周期（不等心跳）。"""
        if self._running and not self._worker.busy:
            self._tick()
