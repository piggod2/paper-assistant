"""
论文智助 — Agent 编排层（单轮 · 规则路由，无大模型依赖）

职责：把已有的 detect / rewrite / translate / search 五个工具，
用一个自然语言对话入口串起来。核心不是"意图识别"（工具自带关键词锚点），
而是"从用户一句话里判断：贴了新文本，还是对上一段文本做操作"。

回复原则（区别于 ChatGPT 套壳的差异化）：
   每句回复要么带证据，要么带"为什么没改"。尤其要主动展示 X 级"永不修改"机制。
"""

import re
import time

try:
    from . import detector, rewriter, translator, searcher
except ImportError:
    import detector, rewriter, translator, searcher


# ── 操作关键词（规则路由，不需要 LLM）──

DETECT_KW = ["检测", "看看", "有没有ai味", "有没有ai", "ai味", "ai痕迹", "机器味", "是不是ai", "像不像ai", "帮我看看", "查一下"]
POLISH_KW = ["改", "润色", "去掉", "去除", "自然", "去ai", "去模板", "精简", "帮我改", "修一下", "优化", "别那么ai"]
TRANSLATE_ZH2EN_KW = ["翻译成英文", "译成英文", "翻成英文", "英文翻译", "中译英", "translate"]
TRANSLATE_EN2ZH_KW = ["翻译成中文", "译成中文", "翻成中文", "中文翻译", "英译中"]
SEARCH_KW = ["找文献", "找论文", "找相关", "相关文献", "相关论文", "搜论文", "搜文献", "推荐文献", "推荐论文", "reference", "paper", "检索文献", "检索论文", "找一下", "搜一下"]
PIPELINE_KW = ["全流程", "一条龙", "全部", "都处理", "都跑", "一键", "全部处理", "完整处理", "都做"]
EXPLAIN_KW = ["为什么", "解释", "凭什么", "依据", "证据", "原理"]


def chat(message: str, history: list | None = None) -> dict:
    """
    单轮 Agent 入口。
    返回 { reply, tool_calls, results, context_updated }
    """
    msg = (message or "").strip()
    if not msg:
        return _reply("请把要处理的论文段落贴给我，或者说一句指令，例如「帮我看看有没有 AI 味」。", [], {})

    # ── 第一步：判断这是"贴了新文本"还是"对文本做操作" ──
    # 规则：无操作关键词、且长度较长 → 视为贴了文本
    has_action = _has_action(msg)
    is_text_input = (not has_action) and len(msg) >= 20

    tool_calls = []
    results = {}

    # ── 第二步：匹配工具（顺序 = 优先级：先改/检测，再翻译，再检索，最后全流程）──

    # 解释类优先（用户问"为什么改这里"）—— 最高优先级
    if _match_any(msg, EXPLAIN_KW):
        return _reply_explain()

    # 润色（含检测，因为润色前必先检测）—— 优先级最高，因为"改/润色"最明确
    if _match_any(msg, POLISH_KW):
        return _run_polish(msg)

    # 仅检测
    if _match_any(msg, DETECT_KW):
        return _run_detect(msg)

    # 翻译（方向判断）
    if _match_any(msg, TRANSLATE_ZH2EN_KW):
        return _run_translate(msg, "zh", "en")
    if _match_any(msg, TRANSLATE_EN2ZH_KW):
        return _run_translate(msg, "en", "zh")

    # 检索
    if _match_any(msg, SEARCH_KW) and not is_text_input:
        return _run_search(msg)

    # 全流程（放最后，避免"全部/都"误伤其他指令）
    if _match_any(msg, PIPELINE_KW):
        return _run_pipeline(msg)

    # 贴了文本但没说干啥 → 默认先检测，给个引导
    if is_text_input:
        return _run_detect_on_new_text(msg)

    # 兜底：没识别出意图 → 交给前端免密钥大模型做自由问答
    # fallback: true 告诉前端「这问题规则引擎管不了，交给 LLM 回答」
    return {
        "reply": "规则引擎未识别到具体指令，已切换 AI 问答。",
        "tool_calls": [],
        "results": {},
        "fallback": True,
    }


# ── 意图判断辅助 ──

def _has_action(msg: str) -> bool:
    all_kw = (DETECT_KW + POLISH_KW + TRANSLATE_ZH2EN_KW + TRANSLATE_EN2ZH_KW
              + SEARCH_KW + PIPELINE_KW + EXPLAIN_KW)
    return _match_any(msg, all_kw)


def _match_any(msg: str, keywords: list[str]) -> bool:
    low = msg.lower()
    return any(kw in low for kw in keywords)


def _extract_body(msg: str) -> str:
    """从指令中剥离操作词，尽量还原用户想处理的文本主体。

    策略：若消息含冒号/逗号且前半段是短指令（<12字），取后半段为正文；
    否则取操作词之前的文本。
    """
    body = msg

    # 1. 「短指令：正文」结构 —— 冒号/逗号前是短指令就剥掉
    for sep in ["：", ":", "，", ","]:
        if sep in msg:
            head, tail = msg.split(sep, 1)
            # 头部去掉指令助词后仍很短，说明是纯指令
            head_clean = re.sub(r"帮我|请|麻烦|来|给我|一下|一遍", "", head).strip()
            if len(head_clean) <= 12 and len(tail.strip()) >= 3:
                body = tail.strip()
                break

    body = body.strip("「」《》\"'‘’“” \n")

    # 2. 兜底：若剥离后仍过短，取操作词之前的文本
    if len(body) < 5:
        for kw in (PIPELINE_KW + TRANSLATE_ZH2EN_KW + TRANSLATE_EN2ZH_KW + POLISH_KW + DETECT_KW + SEARCH_KW):
            idx = msg.lower().find(kw)
            if idx > 0:
                candidate = msg[:idx].strip("「」《》\"'‘’“” \n：:，,。")
                if len(candidate) >= 5:
                    return candidate
    return body


# ── 各工具执行 ──

def _run_detect(msg: str) -> dict:
    text = _extract_body(msg)
    if len(text) < 5:
        return _reply("要检测的文本太短了，把论文段落贴给我，再说「帮我看看有没有 AI 味」。", ["detect"], {})
    report = detector.detect(text)
    return _format_detect_reply(text, report)


def _run_detect_on_new_text(text: str) -> dict:
    report = detector.detect(text)
    return _format_detect_reply(text, report)


def _format_detect_reply(text: str, report: dict) -> dict:
    summary = report.get("summary", {})
    actionable = report.get("actionable_total", 0)
    hits = report.get("hits", {})
    x_hits = {k: v for k, v in hits.items() if k.startswith("X")}
    h_hits = {k: v for k, v in hits.items() if k.startswith("H")}

    parts = []
    if actionable:
        parts.append(f"🔍 检测完成，共发现 {actionable} 处 AI 味特征。")
    else:
        parts.append("🔍 检测完成，这段文本基本没有明显的 AI 味特征。")

    # 分级摘要
    grade_lines = []
    for grade, label in [("A", "机械改"), ("B", "建议改"), ("F", "指纹"), ("C", "只报告")]:
        cnt = sum(len(v) for k, v in hits.items() if k.startswith(grade))
        if cnt:
            grade_lines.append(f"· {grade}级（{label}）×{cnt}")
    if grade_lines:
        parts.append("\n".join(grade_lines))

    # X 级：主动强调"故意没动"
    if x_hits:
        x_cnt = sum(len(v) for v in x_hits.values())
        parts.append(
            f"\n⚠️ 另有 {x_cnt} 处特征我【故意不标为问题】——它们经 270 对配对复测后方向反转，"
            "被证明是人类反而更常用的写法（如序数词「首先」、「这意味着」、「赋能」）。"
        )

    if h_hits:
        h_cnt = sum(len(v) for v in h_hits.values())
        parts.append(f"\n还有 {h_cnt} 处比喻类需要人审，系统不给意见。")

    parts.append("\n要我把可改的地方润色掉吗？直接说「帮我改」即可。")

    return _reply("\n".join(parts), ["detect"], {"detect_report": report})


def _run_polish(msg: str) -> dict:
    text = _extract_body(msg)
    if len(text) < 5:
        return _reply("要润色的文本太短了，把论文段落贴给我，再说「帮我改」或「帮我润色」。", ["polish"], {})
    report = detector.detect(text)
    result = rewriter.rewrite(text, report)
    return _format_polish_reply(result, report)


def _format_polish_reply(result: dict, report: dict) -> dict:
    n = result.get("total_changes", 0)
    n_fail = result.get("total_failures", 0)
    changes = result.get("changes", [])
    polished = result.get("polished", "")

    parts = []
    if n:
        parts.append(f"✅ 改好了，一共动了 {n} 处。")
    else:
        parts.append("✅ 检测完成，这段没有需要机械修改的地方。")

    # 改动明细（前 5 处）
    if changes:
        parts.append("\n【已修改】")
        for c in changes[:5]:
            rule = c.get("rule", "?")
            orig = c.get("original", "")[:20]
            parts.append(f"· {rule}：「{orig}…」")

    # X 级保护
    x_hits = {k: v for k, v in report.get("hits", {}).items() if k.startswith("X")}
    if x_hits:
        x_cnt = sum(len(v) for v in x_hits.values())
        parts.append(
            f"\n【故意没改 · {x_cnt} 处】"
        )
        parts.append("配对复测显示这些特征人类用得比 AI 还多，改了反而假：")
        for k, vs in list(x_hits.items())[:3]:
            if vs:
                parts.append(f"· {vs[0].get('match', k)[:20]}")

    # 安全回退
    if n_fail:
        parts.append(f"\n⚠️ {n_fail} 处安全检查未通过，已保留原文。")

    parts.append("\n\n——润色后——")
    parts.append(polished[:500])
    if len(polished) > 500:
        parts.append("…")

    parts.append("\n\n想逐条看每处为什么这么改吗？说「为什么改这里」。")

    return _reply("\n".join(parts), ["detect", "polish"], {
        "polished": polished,
        "changes": changes,
        "report": report
    })


def _run_translate(msg: str, from_lang: str, to_lang: str) -> dict:
    text = _extract_body(msg)
    if len(text) < 3:
        return _reply("要翻译的内容太短了，把英文/中文文本贴给我，再说「翻译成中文/英文」。", ["translate"], {})
    if not translator.is_available():
        return _reply("翻译功能未配置（缺少百度翻译密钥），但检测和润色完全可用。", ["translate"], {"unavailable": True})
    r = translator.translate(text, from_lang, to_lang)
    if "error" in r:
        return _reply(f"翻译失败：{r.get('detail', '未知错误')}", ["translate"], {})
    direction = "英文→中文" if to_lang == "zh" else "中文→英文"
    parts = [
        f"🌐 翻译完成（{direction}，{r.get('segments', 1)} 段）：",
        "",
        r.get("translated", "")
    ]
    return _reply("\n".join(parts), ["translate"], {"translated": r.get("translated", "")})


def _run_search(msg: str) -> dict:
    text = _extract_body(msg)
    if len(text) < 3:
        return _reply("请把论文摘要或主题贴给我，再说「找相关文献」。", ["search"], {})
    r = searcher.search(text, limit=5)
    papers = r.get("results", [])
    source = r.get("source_used", "none")

    if not papers:
        return _reply("没检索到相关文献，建议换更具体的关键词试试。", ["search"], {"results": []})

    parts = [f"📄 找到 {len(papers)} 篇相关文献（来源：{source}）：", ""]
    for i, p in enumerate(papers[:5], 1):
        parts.append(f"{i}. {p.get('title', '')}")
        parts.append(f"   {p.get('authors', [])[:2]} · {p.get('year', '?')}年 · 相关度 {p.get('score', 0)}")
        if p.get('relevance_reason'):
            parts.append(f"   理由：{p.get('relevance_reason')}")
        if p.get('url'):
            parts.append(f"   {p.get('url')}")
        parts.append("")

    parts.append("（说明：当前使用 arXiv 免费源，Semantic Scholar 的 key 获批后将支持更精准的语义推荐）")
    return _reply("\n".join(parts), ["search"], {"results": papers})


def _run_pipeline(msg: str) -> dict:
    text = _extract_body(msg)
    if len(text) < 5:
        return _reply("要处理的内容太短了，把论文段落贴给我，再说「帮我全流程处理」。", ["pipeline"], {})

    steps = []
    # 1 检测
    t0 = time.perf_counter()
    report = detector.detect(text)
    steps.append({"step": "detect", "status": "ok", "elapsed_ms": int((time.perf_counter()-t0)*1000),
                  "message": f"检测 {report.get('actionable_total', 0)} 处特征"})

    # 2 润色（核心）
    t0 = time.perf_counter()
    result = rewriter.rewrite(text, report)
    steps.append({"step": "polish", "status": "ok", "elapsed_ms": int((time.perf_counter()-t0)*1000),
                  "message": f"改写 {result.get('total_changes', 0)} 处"})

    # 3 检索（可选，失败不中断）
    t0 = time.perf_counter()
    sr = searcher.search(text[:300], 3)
    papers = sr.get("results", [])
    steps.append({"step": "search", "status": "ok" if papers else "empty",
                  "elapsed_ms": int((time.perf_counter()-t0)*1000),
                  "message": f"{sr.get('source_used', 'none')}：{len(papers)} 篇"})

    # 4 翻译（可选，失败不中断）
    if translator.is_available():
        t0 = time.perf_counter()
        tr = translator.translate(text, "zh", "en")
        if "error" not in tr:
            steps.append({"step": "translate", "status": "ok", "elapsed_ms": int((time.perf_counter()-t0)*1000),
                          "message": "已生成英文稿"})
        else:
            steps.append({"step": "translate", "status": "skipped", "elapsed_ms": 0, "message": "翻译失败，跳过"})
    else:
        steps.append({"step": "translate", "status": "skipped", "elapsed_ms": 0, "message": "未配置，跳过"})

    parts = ["📄 全流程完成，各步骤：", ""]
    for s in steps:
        icon = "✅" if s["status"] == "ok" else ("⚠️" if s["status"] == "skipped" else "—")
        parts.append(f"{icon} {s['step']}：{s['message']}（{s['elapsed_ms']}ms）")

    parts.append("\n——润色结果——")
    parts.append(result.get("polished", "")[:500])

    if papers:
        parts.append("\n\n——相关文献——")
        for p in papers[:3]:
            parts.append(f"· {p.get('title', '')}（{p.get('year', '?')}）")

    return _reply("\n".join(parts), ["detect", "polish", "search", "translate"], {
        "polished": result.get("polished", ""),
        "papers": papers,
        "steps": steps
    })


def _reply_explain() -> dict:
    return _reply(
        "我的每次改写都基于结构化规则（lieflat-less-ai-tone，CC BY-NC 4.0），每条规则带实测证据。\n\n"
        "比如「不是…而是…」翻案腔，配对复测显示 GPT δ+0.88 / Opus δ+0.72，是证据最强的纯写作信号，所以我改。\n\n"
        "而「首先」「这意味着」「赋能」这些，配对复测后方向反转（人类反而更常用），所以我【故意不改】。\n\n"
        "完整规则和证据在左侧「检测级别」面板或 /api/rules 里都能看到。",
        ["explain"], {}
    )


def _reply(reply_text: str, tool_calls: list, results: dict) -> dict:
    return {
        "reply": reply_text,
        "tool_calls": tool_calls,
        "results": results,
    }
