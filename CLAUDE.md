# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Miku 屏幕翻译：Windows 桌面 OCR 实时翻译工具（初音未来风格 UI）。流程：Ctrl+1 框选屏幕区域 → 本地 OCR 识别 → DeepSeek AI 翻译 → 置顶悬浮窗展示译文。

## 常用命令

```bash
# 运行（依赖装在 .venv 虚拟环境，Python 3.13）
.venv/Scripts/python.exe main.py

# 语法检查
.venv/Scripts/python.exe -m py_compile main.py app/*.py

# 安装依赖（国内镜像）
.venv/Scripts/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

无正式测试框架；验证方式是编写一次性临时脚本（offscreen 平台 `QT_QPA_PLATFORM=offscreen` 下构建 UI 冒烟，或真实平台截屏验证）。注意：Python 是 Windows 进程，脚本里不要用 Git Bash 的 `/tmp` 路径。

## 架构

- `main.py` 入口；`app/` 包内按职责分模块：
  - `config.py` — `AppConfig` dataclass + `config.json` 读写。**region 必须还原为 `Region` 对象**（controller 依赖 `is_set()`，dict 会 AttributeError——曾因此导致"点击开始无反应"）
  - `capture.py` — `RegionSelector` 全屏遮罩拖拽框选；`grab_region` 截取选区
  - `ocr_engine.py` — RapidOCR 封装（v3 API + v1 fallback），按源语言懒加载模型
  - `translator.py` — DeepSeek 翻译（OpenAI 兼容客户端）+ LRU 缓存（相同文本命中缓存零 API 调用）
  - `controller.py` — 流程调度核心（见线程模型）
  - `overlay.py` — 置顶悬浮译文窗（QTextBrowser 富文本，历史累积最多 2 条，四角可缩放）
  - `region_frame.py` — 常驻区域框（选区边框 + 顶部工具条：开始/停止/关闭，四角缩放）
  - `hotkey.py` — Ctrl+1 全局热键（RegisterHotKey + nativeEventFilter）
  - `main_window.py` — 主窗口（初音 QSS 主题），装配所有模块

## 关键架构决策（改代码前必读）

**线程模型**：截图必须在 GUI 线程（`QScreen.grabWindow` 是平台 API）；OCR + AI 翻译在工作线程（秒级，不能卡 UI）。controller 用 `QTimer`（GUI 线程）触发 `_tick` → 截图 → 经 `Signal(object)` 队列连接发给 worker。worker 完成后发 `done` 信号，主线程立即进入下一周期（不等心跳）。`_on_done` 与 timer 双触发由 `worker.busy` 标志防堆积。

**PySide6 坑**：`Signal` 必须是类属性（在 `__init__` 里创建实例属性会报 `'Signal' object has no attribute 'connect'`）。

**截图像素对齐**：QImage 行字节数有 4 字节 padding，必须用 `img.bytesPerLine()` 而不是 `width*3`，否则 reshape 崩溃（曾致"无翻译"）。

**DPI 缩放**：Windows 150% 缩放常见。Qt 坐标是逻辑像素，`grabWindow` 返回物理像素——区域尺寸换算不要求严格一致（OCR 只吃像素），但选区/悬浮窗定位必须用全局坐标 + `screenAt` 换算（支持多屏）。

**OCR 性能**：`Det.limit_side_len=480`（默认 736）把推理从 ~930ms 压到 ~690ms。tiny 模型不支持日文（`PP_OCRV6_TINY_LANGS` 排除 japan），日文只能用 v6 small。识别结果按文本框中心 y 排序（同高度组按 x）。

**翻译性能**：API 延迟 ~1-1.5s（v4-flash 模型生成速度，服务端决定，软件内无法再压）。已用 `max_tokens=1024` + 极简 system prompt。指纹去重（OCR 文本 hash 不变不调 API）+ LRU 缓存控制成本。

**配置**：`config.json` 含 API Key 等敏感信息，已 gitignore，绝不提交。

## 交互流程

主窗口/框选 → `RegionSelector` 遮罩 → 松手 → `RegionFrame` 常驻框（选区边框+工具条）→ 工具条"▶ 开始翻译"或主窗口按钮 → `controller.start()` → 循环截图→OCR→翻译 → `overlay.add_translation` 追加显示。`RegionFrame` 拖动/缩放经 `region_changed` 信号同步配置并重定位悬浮窗；`overlay` 四角缩放经 `resize_done` 持久化尺寸。
