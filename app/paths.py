"""路径定位：兼容开发环境与 PyInstaller 打包。

- 资源（assets/*）：打包后位于 PyInstaller 解压临时目录（_MEIPASS），只读
- config.json：必须可写，放在 exe 同目录（打包后）或项目根目录（开发时）
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> Path:
    """只读资源目录（assets 所在）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return PROJECT_ROOT


def asset_path(name: str) -> Path:
    return resource_dir() / "assets" / name


def writable_dir() -> Path:
    """可写目录（config.json 存放处）：exe 旁 / 项目根。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT
