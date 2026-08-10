# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Miku 屏幕翻译：Windows 桌面 OCR 实时翻译工具（初音未来风格 UI）。流程：Ctrl+1 全局热键框选屏幕区域 → 本地 RapidOCR 识别（日/中/英）→ DeepSeek API 翻译 → 置顶悬浮窗展示译文（历史累积 2 条）。最终交付形态是 **PyInstaller 单文件 exe**，用户通过桌面快捷方式使用（快捷方式指向项目根目录的 `Miku屏幕翻译.exe`）。

## 常用命令（均在项目根目录）

```bash
# 开发运行（依赖在 .venv，Python 3.13）
.venv/Scripts/python.exe main.py

# 打包 exe（用户验收前必须重新打包；约 80 秒）
.venv/Scripts/pyinstaller.exe --noconfirm --onefile --windowed --name "Miku屏幕翻译" \
  --icon assets/miku.ico --add-data "assets;assets" --collect-all rapidocr main.py
# 打包后需复制 dist/Miku屏幕翻译.exe 到项目根目录（用户双击运行的是根目录这份）
cp dist/Miku屏幕翻译.exe ./Miku屏幕翻译.exe

# 语法检查
.venv/Scripts/python.exe -m py_compile main.py app/*.py

# 安装依赖（国内镜像）
.venv/Scripts/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

无正式测试框架：验证方式是写一次性临时脚本，offscreen 平台（`QT_QPA_PLATFORM=offscreen`）下构建 UI 断言布局，或真实平台启动验证。注意：
- **终端是 GBK 编码**——脚本 print 任何非 ASCII 字符（中文、▶♪ 等符号）会 UnicodeEncodeError；断言结果写文件或转 ASCII 输出
- **Python 是 Windows 进程**——临时脚本路径不要用 Git Bash 的 `/tmp`，用项目内相对路径
- 脚本里会残留测试副作用（如改 config.json 的 hotkey），测试后检查并恢复

## 架构（app/ 包，共 11 个模块 + main.py）

- `main.py` — 入口，设置应用名/窗口图标（`asset_path("miku.png")`）
- `paths.py` — **路径体系核心**：`resource_dir()`（frozen 时 `sys._MEIPASS`）/ `writable_dir()`（frozen 时 exe 同目录）/ `asset_path(name)`。所有资源引用必须走 `asset_path()`，config.json 走 `writable_dir()`
- `config.py` — `AppConfig` dataclass + `config.json` 读写。**region 字段必须还原为 `Region` 对象**（`is_set()` 方法；dict 会 AttributeError——曾致"点击开始无反应"）。含 `LANGS`（语言→OCR 模型映射）
- `capture.py` — `RegionSelector` 全屏遮罩拖拽框选（多屏支持）；`grab_region` 截取选区
- `ocr_engine.py` — RapidOCR 封装：v3（`rapidocr` 包，`params={"Rec.lang_type":..., "Det.lang_type":..., "Det.limit_side_len": 480}`，结果走 `.txts/.boxes`）+ v1 fallback（`rapidocr-onnxruntime`，元组结果）。按行排序识别结果
- `translator.py` — DeepSeek 翻译（OpenAI 兼容客户端）+ LRU 缓存 + 指纹去重。SYSTEM_PROMPT 为"母语级翻译专家"风格
- `controller.py` — 调度核心（线程模型见下）
- `overlay.py` — 置顶悬浮译文窗（QTextBrowser 富文本、历史 2 条、四角/边缘缩放、标题栏 × 只关输出框）
- `region_frame.py` — 常驻区域框（青色边框 + 顶部悬停工具条，含 40px 热区）
- `hotkey.py` — 全局热键（RegisterHotKey + nativeEventFilter），`PRESET_HOTKEYS` 预设组合
- `settings.py` — 设置对话框（快捷键配置，改后重注册热键）
- `main_window.py` — 主窗口（518 行）：无边框、壁纸背景 paintEvent、自定义标题栏、MikuArt 立绘、分区表单布局

## 关键架构决策（改代码前必读）

**线程模型**：截图必须在 GUI 线程（`QScreen.grabWindow` 是平台 API）；OCR + AI 翻译在工作线程。controller 用 `QTimer`（GUI 线程）触发 `_tick` → 截图 → 经类属性 `Signal(object)` 队列连接发给 worker；worker 完成发 `done` 信号回主线程立即进下一周期。`worker.busy` 标志防堆积。`_on_done` 里的"完成即下一周期" + timer 双触发由此防住。

**PySide6 已知坑**（都踩过）：
- `Signal` 必须是**类属性**，`__init__` 里创建实例属性报 `'Signal' object has no attribute 'connect'`
- QImage 行字节有 4 字节 padding，截图像素必须 `img.bytesPerLine()` 而非 `width*3`（reshape 崩溃致"无翻译"）
- `drawPixmap` 三参重载的 sourceRect 必须传 `QRect`（QRectF 重载解析失败，paintEvent 抛异常会**跳过整个绘制**——立绘消失的根因）
- `Qt.AspectRatioMode` 没有 `KeepAspectRatioByCrop`，铺满裁剪用 `KeepAspectRatioByExpanding`

**UI 主题与字体**（用户反复迭代的敏感区）：
- 字体族回退链：标题/按钮 `"STHupo","SimHei","Microsoft YaHei"`（华文琥珀→黑体→雅黑），正文幼圆 `"YouYuan","Microsoft YaHei"`
- **禁用 emoji 和稀有符号**（📌✦☰⚙ 等在粗体字体缺失显示为方块），只用 ▶ ■ ★ ♪ ≧▽≦ 等全字体支持符号
- 左列标语 QLabel **必须限宽**（`setMaximumWidth(250)` + `setWordWrap(False)`）：文本 16px 琥珀 ≈ 244px，超宽会把左列撑宽挤压右侧卡片（按钮从 101px 被压到 84px 的根因）
- QSS 用 f-string 生成时**所有花括号必须双写** `{{ }}`；`border:1.5px` 无效（Qt QSS 不支持小数）
- QComboBox 深色主题下系统箭头不可见，用 CSS 三角形（`border-left/right: transparent; border-top: 7px solid`）重绘

**窗口/输出框行为约定**（用户明确要求）：
- 主窗口无边框，自定义标题栏：左标题 + 设置/最小化/关闭按钮，标题栏可拖动（mousePress y<42）
- **输出框位置独立**：首次框选定位一次（`_ensure_overlay_placed`），之后位置只由用户拖动；区域框拖动/重新框选均不移动它；只在应用退出或输出框标题栏 × 时关闭
- 区域框一次只存在一个；工具条默认隐藏、悬停显示（含上方 40px 热区）
- 主窗口 720×540 固定；卡片分区布局（♪ 翻译设置 / ♪ 操作）；按钮固定 122px 等宽三列

**OCR 性能**：`Det.limit_side_len=480`（默认 736 → 930ms 压到 ~690ms）。tiny 模型不支持日文（`PP_OCRV6_TINY_LANGS` 排除 japan），日文只能用 v6 small。API 延迟 ~1.1s（deepseek-v4-flash 模型速度，服务端决定）——`max_tokens=1024` + 指纹去重 + LRU 缓存已是最优。

## Git 与交付注意

- 仓库 `github.com/ChiShangying/miku-api-`（public），SSH 认证（`~/.ssh/id_ed25519`，443 端口经 `ssh.github.com`）
- **`.gitignore` 必须包含**：`config.json`（含 API Key）、`/Miku屏幕翻译.exe`、`dist/ build/ *.spec`——exe 157MB 曾误入历史导致 push 失败（GitHub 单文件上限 100MB），已清理过一次
- git 身份已配置（local）：ChiShangying / chi-shangying@users.noreply.github.com
- 桌面快捷方式指向项目根目录 exe，config.json 在项目根目录（exe 同目录自动读取）——不要把 config/exe 复制到桌面

## 用户偏好（交互时）

- 语言：中文；界面风格：初音青色系（#39C5BB / #7FF4E8），深色背景
- 交付节奏：界面改动**用户满意后才打包 exe**（不要一改就打包）；改完 exe 需同步复制到项目根目录
- 数据隐私敏感：已确认架构为"截图不上传、只发 OCR 文本给 API"，需向用户明确
