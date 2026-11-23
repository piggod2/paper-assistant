# 论文智助

> **不替你改写，替你揪出 AI 味**  
> 江苏大学「星光杯」AI 应用创新专项赛 参赛作品

## 功能

| 模块 | 能力 | 离线可用 |
|---|---|---|
| 🔍 去AI味检测 | 六级分级检测 (A/B/C/F/X/H)，基于两轮对照研究 | ✅ |
| ✨ 智能润色 | A级机械改 + 安全校验，改写后每个实词可溯源 | ✅ |
| 🌐 论文翻译 | 百度翻译 API，英→中，超长文本自动分段 | ❌ |
| 📚 论文推荐 | Semantic Scholar → arXiv 双源降级，带匹配度评分 | ❌ |
| 🚀 一键全流程 | 翻译→检索→润色 pipeline，失败步骤自动降级 | 部分 |

## 启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置密钥（可选，翻译/检索需要）
cp .env.example .env
# 编辑 .env 填入 BAIDU_APPID / BAIDU_SECRET / SEMANTIC_SCHOLAR_KEY

# 3. 启动后端
cd backend && python server.py

# 4. 打开前端
# 直接双击 frontend/index.html 即可本地使用
# 润色功能完全离线可用
```

## 目录

```
paper-assistant/
├── backend/
│   ├── server.py          FastAPI 入口 (8 接口 + pipeline)
│   ├── detector.py        检测引擎 (六级分级，正则+结构指标)
│   ├── rewriter.py        改写引擎 (倒序替换+安全检查)
│   ├── rules.py           规则加载器
│   ├── translator.py      百度翻译 (appid/sign, 分段防QPS)
│   └── searcher.py        论文检索 (S2→arXiv双源降级)
├── frontend/
│   ├── index.html         Vue 3 CDN 单文件 SPA (三栏布局)
│   └── config.js          配置 (API_BASE)
├── data/
│   └── polish-rules.json  规则数据库 (25条，含变体+证据)
├── .env.example
├── .env
├── requirements.txt
└── README.md
```

## API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 服务状态 + 模块可用性 |
| `/api/rules` | GET | 规则数据库（含归属声明） |
| `/api/detect` | POST | 只检测不改写 |
| `/api/polish` | POST | 检测+改写 |
| `/api/translate` | POST | 英→中翻译 (需密钥) |
| `/api/search` | POST | 论文检索 (S2→arXiv，免鉴权可用) |
| `/api/pipeline` | POST | 翻译→检索→润色 全流程 |
| `/api/share` | POST | 生成分享短码 |
| `/api/share/{code}` | GET | 获取分享内容 |

## 测试

```bash
cd backend && python -c "
from detector import detect
from rewriter import rewrite

# 测试 1: A1 翻案腔 无残留
text = '说白了，核心痛点并不是X，而是Y。一句话总结：需要的是Z。'
r = detect(text)
w = rewrite(text, r)
assert '并是' not in w['polished']

# 测试 2: B1 不长误报
text = '质量管理是从0到1阶段最容易被忽视的问题。'
assert len(detect(text)['hits'].get('B1',[])) == 0

# 测试 4: X级隔离
text = '首先，数据清洗。这意味着后续稳定。'
w = rewrite(text, detect(text))
assert '首先' in w['polished'] and '这意味着' in w['polished']

print('All tests passed')
"
```

## 归因

去 AI 味规则集基于 [lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone)（CC BY-NC 4.0），数据源自两轮对照研究：629 篇不配对对照 + 270 对同题同事实配对复测（GPT-5.6 135篇 + Opus 4.6 135篇，分开统计），脚本层配对 Wilcoxon + Cliff's δ，语义层约 43 万次封闭判读。本项目为非商业教学演示用途。

## 已知限制

- 中文文献检索仅限 arXiv 预印本，知网/万方/维普无公开 API
- 百度翻译需要个人实名认证获取密钥
- B1/B2/B6 级改写需人工判断，自动改写已禁用（避免误改）
- 分享短码存储在内存中，重启后失效