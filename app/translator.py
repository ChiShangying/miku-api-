"""DeepSeek 翻译模块：OpenAI 兼容 API + 内存 LRU 缓存。

缓存的必要性：实时翻译模式下同一句话会反复识别到，
不缓存则每帧都扣 token；相同文本直接命中缓存零成本。
"""
from __future__ import annotations

import logging
from collections import OrderedDict

log = logging.getLogger(__name__)

LANG_NAMES = {"zh": "中文", "en": "英文", "ja": "日文"}

SYSTEM_PROMPT = (
    "你是一位母语级的专业翻译专家，擅长把{source}翻译成地道自然的{target}。\n"
    "翻译要求：\n"
    "1. 译文必须自然流畅，完全符合{target}母语者的表达习惯，杜绝翻译腔和生硬直译；\n"
    "2. 保留原文的语气和情绪：口语对话用口语化表达，正式文本用书面语；\n"
    "3. 多行文本按行对应翻译，保留原有换行结构；\n"
    "4. 专有名词、人名、作品/游戏术语优先采用公认译法，必要时保留原文；\n"
    "5. 只输出译文本身，不添加任何解释、注释、引言或修饰。\n"
    "若原文本身就是{target}，直接原样输出。"
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

        prompt = SYSTEM_PROMPT.format(
            source=LANG_NAMES.get(source, source), target=LANG_NAMES.get(target, target))
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
