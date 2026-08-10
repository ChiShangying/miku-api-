# 🎤 Miku 屏幕翻译（实时 OCR 翻译）

初音未来风格的屏幕实时翻译小工具：框选屏幕区域 → 本地 OCR 识别 → DeepSeek AI 翻译 → 悬浮窗展示译文。

## 功能

- 📌 **区域框选**：全屏遮罩，鼠标拖拽框选要翻译的区域（支持多显示器）
- 🖼 **本地 OCR**：RapidOCR（PP-OCRv6），免费离线，支持 日文/中文/英文
- 🤖 **AI 翻译**：DeepSeek API（OpenAI 兼容），可换任意兼容服务
- 🔄 **实时循环**：自动检测区域文字变化，只翻译变化的内容（省 token）
- 🪟 **悬浮译文窗**：置顶半透明，原文灰 + 译文初音青，可拖拽，右键退出

## 快速开始

```bash
# 1. 创建虚拟环境并安装依赖（已安装可跳过）
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 运行
.venv\Scripts\python main.py
```

## 使用步骤

1. 首次运行：填入 DeepSeek API Key（开放平台 https://platform.deepseek.com 申请）
2. 点击「📌 框选区域」，在屏幕上拖拽框住要翻译的内容，松开确认
3. 选择源语言/目标语言（默认 日文→中文），点击「▶ 开始翻译」
4. 译文悬浮窗出现在选区下方，自动跟随内容变化
5. 悬浮窗可拖动；右键 → 退出

## 配置说明（config.json）

| 字段 | 说明 |
|---|---|
| `api_key` | DeepSeek API Key |
| `base_url` | OpenAI 兼容地址（默认 DeepSeek） |
| `model` | 模型名（默认 deepseek-v4-flash） |
| `source_lang` | 源语言：`zh`/`en`/`ja` |
| `target_lang` | 目标语言：`zh`/`en`/`ja` |
| `interval_ms` | 轮询间隔（默认 1500ms） |
| `font_size` | 悬浮窗译文字号 |
| `region` | 上次框选的区域坐标 |

## 技术要点

- 截图必须在 GUI 线程（Qt 平台 API），OCR + AI 请求在工作线程，UI 不卡顿
- 文本指纹去重：识别结果未变化时不调翻译 API
- 翻译 LRU 缓存：相同句子重复出现直接命中，零成本
- 首次运行 RapidOCR 会自动下载模型（需联网，约几十 MB，仅一次）
