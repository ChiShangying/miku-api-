"""RapidOCR 封装：按源语言懒加载模型，识别结果按行排序。

兼容两代包：
- rapidocr>=3.x（推荐，PP-OCRv6，lang_type 指定语言，模型自动下载）
- rapidocr-onnxruntime 1.x（旧包，内置 ch 模型，仅中英可靠）
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)


class OcrEngine:
    """惰性创建 RapidOCR 引擎；切换源语言时重建模型。"""

    def __init__(self):
        self._engine = None
        self._lang: str | None = None
        self._lock = threading.Lock()

    def _ensure(self, lang: str):
        """按 lang 创建/重建引擎（首次运行会自动下载模型，需要网络）。"""
        with self._lock:
            if self._engine is not None and self._lang == lang:
                return
            try:
                from rapidocr import RapidOCR  # 新版 v3/v4
                log.info("加载 RapidOCR v3+ 模型: lang=%s ...", lang)
                self._engine = RapidOCR(params={
                    "Rec.lang_type": lang,
                    "Det.lang_type": lang,
                    "Det.limit_side_len": 480,  # 检测输入边长上限，显著提速（测过 928ms→692ms）
                })
                self._v3 = True
            except ImportError:
                from rapidocr_onnxruntime import RapidOCR  # 旧版 v1
                log.info("加载 rapidocr-onnxruntime 模型: lang=%s ...", lang)
                self._engine = RapidOCR(lang=lang)
                self._v3 = False
            self._lang = lang

    def recognize(self, img, lang: str) -> list[str]:
        """识别图片（BGR numpy），返回按视觉行序排列的文本列表。"""
        self._ensure(lang)
        try:
            if self._v3:
                out = self._engine(img)
                boxes, txts = out.boxes, out.txts
                pairs = list(zip(boxes, txts))
            else:
                result, _ = self._engine(img)
                pairs = [(item[0], item[1]) for item in (result or [])]
        except Exception:
            log.exception("OCR 识别失败")
            return []
        if not pairs:
            return []
        # 按文本框中心 y 从上到下排序（同高度组内按 x 从左到右）
        lines = []
        for box, text in pairs:
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            cy = sum(ys) / 4
            cx = sum(xs) / 4
            lines.append((cy, cx, text))
        lines.sort(key=lambda t: (round(t[0] / 20), t[1]))
        return [t[2] for t in lines]
