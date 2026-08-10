"""配置读写：config.json 持久化所有用户设置。"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# 语言代码 -> (显示名, OCR 模型名)
LANGS = {
    "zh": ("简体中文", "ch"),
    "en": ("英文", "en"),
    "ja": ("日文", "japan"),
}


@dataclass
class Region:
    """框选区域（虚拟桌面坐标）。x,y,w,h 为 None 表示未框选。"""
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None

    def is_set(self) -> bool:
        return all(v is not None for v in (self.x, self.y, self.w, self.h))


@dataclass
class AppConfig:
    api_key: str = ""                 # DeepSeek API Key
    base_url: str = "https://api.deepseek.com"  # OpenAI 兼容地址
    model: str = "deepseek-v4-flash"  # 模型名
    source_lang: str = "ja"           # 源语言（OCR 用）
    target_lang: str = "zh"           # 目标语言（翻译用）
    region: dict = field(default_factory=dict)  # 框选区域 {"x","y","w","h"}
    interval_ms: int = 600            # 自动模式循环间隔（秒级反馈）
    font_size: int = 20               # 悬浮窗译文字号
    overlay_opacity: float = 0.92     # 悬浮窗不透明度
    overlay_w: int = 480              # 悬浮窗宽度（可四角拖动调整）
    overlay_h: int = 300              # 悬浮窗高度
    hotkey: str = "Ctrl+1"            # 全局快捷键（PRESET_HOTKEYS 中的显示名）

    @property
    def ocr_lang(self) -> str:
        return LANGS.get(self.source_lang, LANGS["ja"])[1]

    @property
    def source_name(self) -> str:
        return LANGS.get(self.source_lang, LANGS["ja"])[0]

    @property
    def target_name(self) -> str:
        return LANGS.get(self.target_lang, LANGS["zh"])[0]


def load_config() -> AppConfig:
    cfg = AppConfig()
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            # region 从 dict 还原为 Region 对象（controller 依赖 is_set()）
            if isinstance(cfg.region, dict) and cfg.region:
                cfg.region = Region(**{kk: vv for kk, vv in cfg.region.items()
                                       if kk in ("x", "y", "w", "h")})
        except (json.JSONDecodeError, OSError, TypeError):
            pass  # 配置损坏时回退默认值
    return cfg


def save_config(cfg: AppConfig) -> None:
    CONFIG_PATH.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
