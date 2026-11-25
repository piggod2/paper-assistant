# 论文智助（去 AI 味检测）

> **不替你改写，替你揪出 AI 味** —— 一个帮你识别并消除论文里"机器味"的写作辅助工具。

江苏大学「星光杯」AI 应用创新专项赛参赛作品。

---

## 这是什么

论文里那些"翻案腔""说白了""一句话总结"式的表达，往往是 AI 生成文本的指纹。论文智助用一套**基于实证研究的规则引擎**（而非黑盒大模型）逐条检测这些特征，分级报告，并对安全的条目自动改写。它的定位不是"替你写"，而是"帮你把 AI 味挑出来、改掉"。

核心特点：

- **规则引擎优先，可解释** —— 每条检测/改写都能对应到具体规则编号和出处，不是"模型觉得像"
- **分级处理** —— A（机械改）/ B（建议改）/ C（只报告）/ F（指纹）/ X（永不改）/ H（人审区），改动风险从低到高
- **改写可溯源** —— 每个改动的实词都能在原文找到出处，"可能"绝不会被改成"一定"
- **离线可用** —— 检测和润色完全本地运行，不需要任何外部 API

## 功能

| 模块 | 能力 | 离线可用 |
|---|---|---|
| 🔍 去 AI 味检测 | 六级分级检测（A/B/C/F/X/H），基于两轮对照研究 | ✅ |
| ✨ 智能润色 | A 级机械改 + 6 道安全校验，改写后每个实词可溯源 | ✅ |
| 🌐 论文翻译 | 百度翻译 API，英→中，超长文本自动分段 | ❌ |
| 📚 论文推荐 | Semantic Scholar → arXiv 双源降级，带匹配度评分 | ❌ |
| 🚀 一键全流程 | 翻译 → 检索 → 润色 pipeline，失败步骤自动降级 | 部分 |
| 💬 智能体问答 | 规则路由对话 + DeepSeek 大模型兜底 | 部分 |

## 快速开始

### 方式一：Windows 一键启动（推荐）

双击项目根目录的 `一键启动.bat`。脚本会自动完成：创建虚拟环境 → 安装依赖 → 清理旧进程 → 启动服务 → 打开浏览器。

### 方式二：手动启动

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv venv
venv\Scripts\activate            # Windows；Linux/macOS 用 source venv/bin/activate
pip install -r requirements.txt

# 2. 配置密钥（可选，翻译/检索/问答需要）
cp .env.example .env
# 编辑 .env 填入 BAIDU_APPID / BAIDU_SECRET / DEEPSEEK_API_KEY 等

# 3. 启动服务
python start.py                  # 会自动打开浏览器

# 或直接用 uvicorn
python -m uvicorn server:app --app-dir backend --port 8000
```

启动后访问 <http://127.0.0.1:8000>。检测和润色功能无需任何密钥即可离线使用。

## 目录结构

```
paper-assistant/
├── backend/                 # FastAPI 后端
│   ├── server.py            # 入口（12 接口 + 中间件 + 静态托管）
│   ├── detector.py          # 检测引擎（六级分级，正则 + 结构指标）
│   ├── rewriter.py          # 改写引擎（倒序替换 + 安全检查）
│   ├── rules.py             # 规则加载器
│   ├── translator.py        # 百度翻译（MD5 签名 + 分段）
│   ├── searcher.py          # 论文检索（S2 → arXiv 双源降级）
│   ├── agent.py             # 规则路由对话（离线）
│   └── qa.py                # DeepSeek 大模型兜底（SSE 流式）
├── data/
│   └── polish-rules.json    # 规则数据库（27 条，单一事实来源）
├── frontend-vue/            # 前端源码（Vue 3 + Vite）
│   └── src/
│       ├── components/      # 9 个组件
│       └── composables/     # 5 个组合式函数
├── frontend/                # 构建产物（后端静态托管，勿手改）
├── 使用手册.md              # 面向使用者的操作手册
├── 开发者手册.md            # 面向开发者的架构/调试手册
├── 一键启动.bat             # Windows 一键启动
├── start.py                 # 本地启动脚本
└── requirements.txt
```

> 完整目录说明、架构设计、接口契约见 [`开发者手册.md`](开发者手册.md)。

## API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 服务状态 + 模块可用性 |
| `/api/rules` | GET | 规则数据库（含归属声明） |
| `/api/detect` | POST | 只检测不改写 |
| `/api/polish` | POST | 检测 + 改写 |
| `/api/judge` | POST | 语义层封闭判读 |
| `/api/translate` | POST | 英→中翻译（需密钥） |
| `/api/search` | POST | 论文检索（S2→arXiv，免鉴权可用） |
| `/api/pipeline` | POST | 翻译 → 检索 → 润色 全流程 |
| `/api/share` | POST | 生成分享短码 |
| `/api/share/{code}` | GET | 获取分享内容 |
| `/api/agent/chat` | POST | 规则路由对话（离线） |
| `/api/qa/chat` | POST | 大模型问答（SSE 流式，需密钥） |

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `BAIDU_APPID` / `BAIDU_SECRET` | 翻译时需要 | 百度翻译 API 密钥 |
| `BAIDU_PLAN` | 否 | 翻译套餐（`advanced` / `standard`） |
| `SEMANTIC_SCHOLAR_KEY` | 否 | Semantic Scholar 密钥，缺省自动降级 arXiv |
| `DEEPSEEK_API_KEY` | 问答时需要 | DeepSeek 大模型密钥 |
| `DEEPSEEK_MODEL` | 否 | 大模型名称，默认 `deepseek-v4-flash` |
| `PORT` | 否 | 服务端口，默认 `8000` |

## 归因

去 AI 味规则集基于 [lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone)（CC BY-NC 4.0），数据源自两轮对照研究：629 篇不配对对照 + 270 对同题同事实配对复测（GPT-5.6 135 篇 + Opus 4.6 135 篇，分开统计），脚本层配对 Wilcoxon + Cliff's δ，语义层约 43 万次封闭判读。本项目为非商业教学演示用途。

## 已知限制

- 中文文献检索仅限 arXiv 预印本，知网/万方/维普无公开 API
- 百度翻译需要个人实名认证获取密钥
- B1/B2/B6 级改写需人工判断，自动改写已禁用（避免误改）
- 分享短码存储在内存中，服务重启后失效
