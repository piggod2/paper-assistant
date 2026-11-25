"""
Rewrite engine — applies detection hits with safety checks.
Follows lieflat-less-ai-tone rewrite principles: minimal change, info conservation.
"""

import re

try:
    from . import rules as rule_loader
except ImportError:
    import rules as rule_loader

# A1 补系词判定（BUG-11）：
# 「不是A，而是B」正面直陈为「B」时，B 若为名词性短语必须补「是」，
# 否则会产出「核心痛点生成内容里那种…」这类病句。
# 能直接作谓语的动词头（情态/轻动词 + 动宾结构明确的词），不补「是」。
_PREDICATIVE_HEAD = re.compile(
    r"^(?:需要|面临|具有|能够|可以|会|将|应|该|必须|应当|属于|位于|源于|来自|"
    r"存在|包括|涵盖|包含|涉及|取决于|关系到|使得|使|让|导致|带来|造成|是|有|无)"
)
# 情态动词开头即使带「的」也是谓语（如「需要更多的预算」），不补「是」。
_MODAL_HEAD = re.compile(r"^(?:需要|能够|可以|会|将|应|该|必须|应当)")
# 任何动词后接体标记「了/着/过」→ 确定为谓语（如「提供了更多配置」「提升了效率」）
_VERB_ASPECT = re.compile(
    r"^(?:生成|产生|形成|构成|建立|构建|搭建|影响|体现|反映|表现|呈现|展现|提高|减少|"
    r"增加|改善|优化|解决|处理|应对|适应|满足|符合|达到|超越|超过|维持|保持|改变|转变|"
    r"转换|提升|降低|提供|采用|提出|实现|拥有|具备|缺乏|缺少|导致|带来|造成|使得|使|让|"
    r"需要|面临|具有|能够|可以|会|将|应|该|是|有|无|属于|位于|源于|来自|存在|包括|涵盖|"
    r"包含|涉及|取决于|关系到)(?:了|着|过)"
)
# A 段承载「做不到」这类能力否定时，删掉 A 会把否定反转成肯定（BUG-12），只报告不改写。
_A_CAPABILITY_NEG = re.compile(
    r"(?:不出来|不了|不到|不成|不能|不会|无法|难以|没法|不可能|不行)"
)
# A 段是「删掉/去掉某物」这类动作否定时，删掉 A 同样会反转语义，只报告不改写。
_A_ACTION_HEAD = re.compile(r"^(?:删掉|删除|去掉|砍掉|放弃|减少|降低|避免|省略|回避)")


def rewrite(text: str, detect_report: dict, options: dict | None = None) -> dict:
    """Apply rewrites based on detection report. Returns {polished, changes, safety_failures}."""
    opts = options or {}
    enabled_levels = _resolve_levels(opts)

    # collect actionable hits
    all_hits = []
    hits_dict = detect_report.get("hits", {})
    for rid, hlist in hits_dict.items():
        rule = rule_loader.get_rule_by_id(rid)
        if not rule:
            continue
        if rule["level"] not in enabled_levels:
            continue
        for h in hlist:
            if h.get("action") != "rewrite":
                continue
            span = h.get("span", [-1, -1])
            if span[0] < 0 or span[1] <= span[0]:
                continue
            all_hits.append({**h, "rule_obj": rule})

    # sort by position descending, longest match first for overlaps
    all_hits.sort(key=lambda h: (h["span"][0], -(h["span"][1] - h["span"][0])))

    # resolve overlaps: for overlapping spans, keep the one that starts first (longest at that position)
    resolved = []
    used_until = -1
    for h in all_hits:
        start, end = h["span"]
        if start < used_until:
            continue  # overlaps with already-resolved hit
        resolved.append(h)
        used_until = end

    # sort by position descending for safe in-place replacement
    resolved.sort(key=lambda h: h["span"][0], reverse=True)

    changed_text = text
    changes = []
    safety_failures = []

    for h in resolved:
        start, end = h["span"]
        rule = h["rule_obj"]
        rid = rule["id"]
        level = rule["level"]
        original_segment = text[start:end]

        # skip if text has shifted (shouldn't happen with descending order)
        if changed_text[start:end] != original_segment:
            continue

        replacement = _compute_replacement(h, original_segment, changed_text, start)
        if replacement is None or replacement == original_segment:
            continue

        # safety checks
        if not _safety_check(
            changed_text, start, start + len(original_segment), replacement
        ):
            safety_failures.append(
                {
                    "rule": rid,
                    "level": level,
                    "strategy": rule["strategy"],
                    "original": original_segment,
                    "attempted": replacement,
                    "reason": "安全检查未通过，已保留原文",
                }
            )
            continue

        # apply
        changed_text = changed_text[:start] + replacement + changed_text[end:]
        changes.append(
            {
                "rule": rid,
                "level": level,
                "strategy": rule["strategy"],
                "original": original_segment,
                "replacement": replacement,
                "span": [start, start + len(replacement)],
                "action": "rewrite",
            }
        )

    return {
        "original": text,
        "polished": changed_text,
        "changes": changes,
        "safety_failures": safety_failures,
        "total_changes": len(changes),
        "total_failures": len(safety_failures),
    }


def _resolve_levels(opts: dict) -> list:
    intensity = opts.get("intensity", "standard")
    intensities = rule_loader.load_rules().get("rewriteIntensities", {})
    cfg = intensities.get(
        intensity, intensities.get("standard", {"levels": ["A", "B", "F"]})
    )
    levels = list(cfg["levels"])
    if opts.get("defluff", True) and "B6" in cfg.get("extra", []):
        if "B6" not in levels:
            levels.append("B6")
    return levels


def _compute_replacement(
    hit: dict, match: str, full_text: str, match_start: int
) -> str | None:
    rid = hit["rule"]
    rule = hit.get("rule_obj", {})

    if rid == "A1":
        # Main pattern: 并不是X，而是Y → 是Y
        # Variants: 看似X，实则Y → Y ; 你以为X，其实Y → Y ; X不重要，重要的是Y → Y
        strat = hit.get("strategy", "")
        if "看似" in strat:
            m = re.search(
                r"(?:看似|表面上|表面)([^，。；！？]+)[，,]\s*(?:实则|实际上|其实)\s*([^，。；！？]+)",
                match,
            )
            return m.group(2) if m else None
        if "你以为" in strat:
            m = re.search(
                r"(?:你以为|大家以为|很多人以为)([^，。；！？]+)[，,]\s*其实\s*([^，。；！？]+)",
                match,
            )
            return m.group(2) if m else None
        if "不重要" in strat:
            m = re.search(
                r"[^，。；！？]+不重要[，,]\s*(?:重要的是|真正重要的是|关键是)\s*([^，。；！？]+)",
                match,
            )
            return m.group(1) if m else None
        # main pattern（对齐源库：并不是/并非/不在于/不是/与其说 … 而是/而在于/不如说）
        # 引导词按「长词优先」排列，避免「并不是」被切成「并」+「不是」导致「并」残留。
        # B 段排除「；：」，避免一个命中跨分句吞掉后文。
        m = re.search(
            r"(?:并不是|并非|不在于|不是|与其说)([^，。！？；：\n]{1,20})[，]?(?:而是|而在于|不如说)([^，。！？；：\n]{1,30})",
            match,
        )
        if not m:
            return None
        a_part = m.group(1).strip()
        pred = m.group(2).strip()
        if not pred:
            return None
        # 只替换 m 覆盖的部分，命中段两端的残留（如冒号后的列表）必须原样保留
        prefix = match[: m.start()]
        suffix = match[m.end() :]
        real_start = match_start + m.start()
        # BUG-12：A 是否定「能做到」或「删掉某物」，删掉 A 会把语义整个反转，只报告不改写。
        if _A_CAPABILITY_NEG.search(a_part) or _A_ACTION_HEAD.match(a_part):
            return None
        # 句首/标点后命中（前面无主语）时，直接给 B，不补「是」。
        preceding_char = full_text[real_start - 1] if real_start > 0 else ""
        if real_start == 0 or preceding_char in "。——！？\n\r\u2014；":
            return prefix + pred + suffix
        # BUG-11：B 以动词开头（体标记 了/着/过，或情态/轻动词）时可作谓语，不补「是」；
        # 「生成内容」「产生的影响」这类名词化短语则必须补「是」。
        if _VERB_ASPECT.match(pred):
            return prefix + pred + suffix
        if _PREDICATIVE_HEAD.match(pred) and (
            "的" not in pred or _MODAL_HEAD.match(pred)
        ):
            return prefix + pred + suffix
        # 「之所以…，并不是A，而是B」→「之所以…，是因为B」（否则缺「因为」不通）
        seg_start = max(full_text.rfind(ch, 0, real_start) for ch in "。！？\n") + 1
        if "之所以" in full_text[seg_start:real_start]:
            return prefix + f"是因为{pred}" + suffix
        return prefix + f"是{pred}" + suffix

    elif rid == "A2":
        # 提示语冒号：preserve sentence boundary if present
        boundary = ""
        match_text = match
        if match and match[0] in "。！？":
            boundary = match[0]
            match_text = match[1:]
        m = re.match(r"^(.+?)[：:](.*)", match_text, re.DOTALL)
        if m and m.group(2).strip():
            return boundary + m.group(2).strip()
        return boundary

    elif rid == "A3":
        # 说白了，X → X (preserve preceding sentence boundary)
        boundary = ""
        match_text = match
        if match and match[0] in "。！？":
            boundary = match[0]
            match_text = match[1:]
        m = re.match(r"^\s*(?:说白了|说穿了|先说结论|综上所述)[，,]\s*(.*)", match_text)
        return boundary + (m.group(1) if m else "")

    elif rid == "B3":
        # 对于X来说/对X而言/就X而言/在X方面， → 删除话题壳（保留前置 。！？）
        # 规则豁免：删壳后主语模糊 / 范围限定丢失时不能改。
        # 判定：只有后句主语明确回指该对象（对象原样出现，或用代词回指）才删。
        boundary = match[0] if match and match[0] in "。！？" else ""
        shell = re.search(
            r"(?:对于|对|就|在)([^，。]{2,15})(?:来说|而言|方面)[，,]", match
        )
        obj = shell.group(1).strip() if shell else ""
        tail = full_text[match_start + len(match) :].lstrip()
        head = tail[:14]
        if obj and (
            obj in head or re.match(r"(?:他们|她们|它们|其|该|此|我们|我|你)", head)
        ):
            # BUG-13：match 里含段落边界「\n\n」时，只删壳子、保留全部标点与换行，
            # 否则两段会被合并成一段。
            if "\n" in match:
                return re.sub(
                    r"(?:对于|对|就|在)[^，。]{2,15}(?:来说|而言|方面)[，,]", "", match
                )
            return boundary
        return None

    elif rid == "B4":
        # 当X时， → X，（不命中「当…的时候」）
        m = re.match(r"当([^，。]{2,20})(?<!的时候)时[，,]", match)
        return f"{m.group(1)}，" if m else None

    elif rid == "B5":
        # 句首连接词（然而/因此/此外/总而言之…）作路标。
        # 源库改法：移到主语后，或换「不过/其实」——本质是保留前后句的衔接关系。
        # 简单删除会把「A。然而，B」拆成「A。B」，断句生硬（用户反馈"该用逗号却用了句号"）。
        # 正确做法：前面的句号「。」改成逗号「，」，让 A、B 合成一个连贯句。
        # 例外（不能改逗号，只删连接词、保留原标点）：
        #   · 前面是「！？」强语气，改逗号会破坏语气；
        #   · 前面含「\n」段落边界（新段开头），动标点会把两段合并。
        if "\n" in match:
            # 段落边界：仅删除连接词本身，保留「。\n\n」等所有标点换行
            return re.sub(r"(然而|因此|此外|与此同时|换言之|总而言之)[，、]", "", match)
        first = match[0] if match else ""
        if first == "。":
            return "，"
        return first if first in "！？\n" else ""

    elif rid == "B1":
        # 过长前置定语：detection only, auto-rewrite too risky
        return None

    elif rid == "B2":
        # 顿号罗列过密：源库改法是「能概括就概括 / 改变其中一项句法」，属语义操作，
        # 不是「换和」能机械完成的。源库脚本层只检测、改写交模型。此处同样只检测不改写，
        # 避免「功能、配置、权限」术语并列被误换成「功能、配置和权限」这类过度机械化。
        return None

    elif rid == "F1":
        # 破折号 → comma
        return "，"

    elif rid == "F2":
        # 分号 → period (context-dependent, simplified)
        return "。"

    else:
        return None


def _safety_check(text: str, old_start: int, old_end: int, replacement: str) -> bool:
    """Safety checks: no orphans, bracket balance, no consecutive punctuation, length sanity."""
    # build hypothetical result
    result = text[:old_start] + replacement + text[old_end:]

    # 1. No orphan 并/而 before 是/有/在 — only flag if NEWLY created by replacement
    orphan_pattern = re.compile(r"\b(并|而)\s*(?:是|有|在|能|会|可|将|把|被|让|使)")
    before = text[max(0, old_start - 5) : old_start]
    after = text[old_end : old_end + 5]
    new_junction = before + replacement + after
    old_junction = text[max(0, old_start - 5) : old_end + 5]
    if orphan_pattern.search(new_junction) and not orphan_pattern.search(old_junction):
        return False

    # 2. Bracket/quotation pairing
    for pair in [
        ("(", ")"),
        ("（", "）"),
        ("\u201c", "\u201d"),
        ("\u2018", "\u2019"),
        ("「", "」"),
    ]:
        if result.count(pair[0]) != result.count(pair[1]):
            return False

    # 3. No consecutive punctuation
    if re.search(r"[，。！？；、]{3,}", result):
        return False
    if re.search(r"[，。！？；、]\s*[，。！？；、]\s*[，。！？；、]", result):
        return False

    # 4. Length sanity: replacement shouldn't be >3x original
    orig_len = old_end - old_start
    if len(replacement) > orig_len * 3 + 50:
        return False

    # 5. No empty string as replacement for meaningful text
    if not replacement.strip() and orig_len > 10:
        # deleting too much context
        return False

    # 6. 不制造「的和」这类断链组合（原文没有、改写后冒出来，说明割裂了定语/并列结构）
    if "的和" in result and "的和" not in text:
        return False

    return True
