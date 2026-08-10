"""DeepSeek 翻译模块：OpenAI 兼容 API + 内存 LRU 缓存。

缓存的必要性：实时翻译模式下同一句话会反复识别到，
不缓存则每帧都扣 token；相同文本直接命中缓存零成本。
"""
from __future__ import annotations

import logging
from collections import OrderedDict

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个专业翻译引擎。把用户发来的原文翻译成{target}语言。"
    "要求：1) 只输出译文本身，不要解释、注释、引言或任何额外内容；"
    "2) 多行文本按行对应翻译，保留换行；3) 专有名词保留原文；"
    "4) 若原文是目标语言，直接原样输出。"
)


class DeepSeekTranslator:
    def __init__(self, api_key: str = "", base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat"):
        self._client = None
        self.base_url = base_url
        self.model = model
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_limit = 300
        if api_key:
            self.set_api_key(api_key)

    def set_api_key(self, key: str):
        from openai import OpenAI
        self._client = OpenAI(api_key=key, base_url=self.base_url)
        log.info("翻译客户端已配置: %s / %s", self.base_url, self.model)

    @property
    def ready(self) -> bool:
        return self._client is not None

    def _cached(self, text: str) -> str | None:
        if text in self._cache:
            self._cache.move_to_end(text)  # LRU 热度刷新
            return self._cache[text]
        return None

    def _store(self, text: str, translated: str):
        self._cache[text] = translated
        if len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)

    def translate(self, text: str, source: str = "ja", target: str = "zh",
                  timeout: float = 20.0) -> str:
        """翻译整段文本。失败时抛异常（由调用方处理并提示用户）。"""
        if not text.strip():
            return ""
        hit = self._cached(text)
        if hit is not None:
            return hit
        if not self.ready:
            raise RuntimeError("未配置 API Key")

        prompt = SYSTEM_PROMPT.format(target=target)
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=1024,   # 限制输出上限：翻译场景足够，减少生成等待
                timeout=timeout,
            )
        except Exception:
            log.exception("翻译请求失败")
            raise
        translated = (resp.choices[0].message.content or "").strip()
        self._store(text, translated)
        return translated
