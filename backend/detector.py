"""
Detection engine — scans text against polish-rules.json, returns structured report.
Only detects; never modifies text.
"""

import re
import math
from collections import Counter

try:
    from . import rules as rule_loader
except ImportError:
    import rules as rule_loader

# ── text segmentation ──

_FENCE = re.compile(r"^```")
_HEADING = re.compile(r"^#{1,6}\s")
_QUOTE = re.compile(r"^>")
_TABLE = re.compile(r"^\|")
_CODE_INDENT = re.compile(r"^    ")
_LIST = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.、)])\s")


def _hanzi(s: str) -> int:
    return len(re.findall(r"[一-鿿]", s))


def _split_sents(para: str) -> list:
    return [p.strip() for p in re.split(r"[。！？；]", para) if len(p.strip()) >= 4]


def _paragraph_blocks(text: str) -> list:
    """按空行切块并分类，返回 [(kind, block_text, first_line_no)]。

    对齐源库 detect.py：识别 heading / list / quote / table / code 五类非正文块，
    其余归 prose。代码围栏用 in_fence 状态机处理，围栏内整段归 code。
    """
    blocks, cur, cur_kind, start = [], [], None, None
    in_fence = False
    for no, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            if not in_fence:
                start = no
            cur.append(line)
            cur_kind = "code"
            in_fence = not in_fence
            if not in_fence:
                blocks.append((cur_kind, "\n".join(cur), start or no))
                cur, cur_kind, start = [], None, None
            continue
        if in_fence:
            cur.append(line)
            continue
        if not line.strip():
            if cur:
                blocks.append((cur_kind or "prose", "\n".join(cur), start or no))
                cur, cur_kind, start = [], None, None
            continue
        if not cur:
            start = no
        cur.append(line)
        if _HEADING.match(line):
            cur_kind = "heading"
        elif _QUOTE.match(line):
            cur_kind = cur_kind or "quote"
        elif _TABLE.match(line):
            cur_kind = cur_kind or "table"
        elif _CODE_INDENT.match(line):
            cur_kind = cur_kind or "code"
        elif _LIST.match(line):
            cur_kind = cur_kind or "list"
    if cur:
        blocks.append((cur_kind or "prose", "\n".join(cur), start or 1))
    return blocks


def _non_prose_ranges(text: str, blocks: list) -> list:
    """返回所有非 prose 块在全文中的字符区间 [(start, end), ...]，用于正则命中时跳过。"""
    ranges = []
    offset = 0
    block_idx = 0
    # 用行定位：逐块找其正文在全文中对应的字符区间
    for kind, body, _first in blocks:
        if kind == "prose":
            continue
        # 找到 body 首行在全文中出现的位置（从 offset 之后搜索，避免重复匹配同内容）
        pos = text.find(body.splitlines()[0] if body else "", offset)
        if pos == -1:
            continue
        ranges.append((pos, pos + len(body)))
        offset = pos + len(body)
    return ranges


# ── 引语保护 ──
# 「某人说/认为/指出/写道，……」这类转述引语里常出现「不在于…而在于…」
# 等辩证句式（如马克思名言），但那是引用者原话，篡改即歪曲本意。
# 以下把转述引语的「引语正文」区间标记为保护区，检测/改写一律跳过。

_QUOTE_INTRO = re.compile(
    r"(?:马克思|毛泽东|恩格斯|列宁|孔子|孟子|老子|庄子|鲁迅|爱因斯坦|牛顿|达尔文|"
    r"古人|前人|俗话|老话|有人|人们|他|她|其|我们|我|你|"
    r"学者|专家|作者|笔者|老师|领导|前辈|同行|朋友|同事|母亲|妈妈|父亲|爸爸|"
    r"[一-鿿]{2,4})"
    r"(?:说|说道|说过|认为|觉得|指出|写道|讲到|提到|总结|概括|称|曰|云|所言|有言)"
    r"[，,:：]\s*"
)


def _quote_ranges(text: str) -> list:
    """返回转述引语正文的字符区间 [(start, end), ...]，用于检测/改写跳过。

    仅保护「转述动词 + 逗号/冒号」之后紧跟的一段话，到句末标点（。！？）或换行截止。
    多句连续引语只保护第一句，避免误吞整段正文。
    """
    ranges = []
    for m in _QUOTE_INTRO.finditer(text):
        start = m.end()
        if start >= len(text) or text[start] in "。！？；，、\n\r":
            continue
        end = len(text)
        for i in range(start, min(start + 120, len(text))):
            if text[i] in "。！？\n\r":
                end = i
                break
        if end - start < 2:
            continue
        ranges.append((start, end))
    return ranges


def _sentence_signature(sent: str) -> tuple:
    """句结构指纹：逗号数、有无冒号、有无括号、长度档（对齐源库 4 元组）。"""
    return (
        sent.count("，"),
        "：" in sent or ":" in sent,
        "（" in sent or "(" in sent,
        len(sent) // 15,
    )


# ── detection ──


def detect(text: str) -> dict:
    """Run full detection. Returns structured report."""
    rr = rule_loader.get_rules()
    total_han = _hanzi(text)
    kk = total_han / 1000 if total_han > 0 else 1
    blocks = _paragraph_blocks(text)
    prose_blocks = [(b, n) for k, b, n in blocks if k == "prose"]
    non_prose = _non_prose_ranges(text, blocks)

    hits: dict[str, list] = {
        r["id"]: [] for r in rr if r.get("pattern") or r["id"] == "B6"
    }
    line_map = _build_line_map(text)

    # 只检测、不自动改写的规则（脚本层无法安全完成，交给人/模型）：
    # B1 过长前置定语、B2 顿号罗列、B6 相邻句同构、以及 C/X/H 级。
    DETECT_ONLY = {
        "B1",
        "B2",
        "B6",
        "C1",
        "C2",
        "C3",
        "C4",
        "X1",
        "X2",
        "X3",
        "X4",
        "X5",
        "X6",
        "X7",
        "X8",
        "H1",
    }

    # 引语保护：转述引语（“马克思说，……”）正文不参与检测，避免翻案腔规则误改名人原话
    quote_ranges = _quote_ranges(text)

    def _in_non_prose(pos: int) -> bool:
        if any(a <= pos < b for a, b in non_prose):
            return True
        return any(a <= pos < b for a, b in quote_ranges)

    # ── regex-based rules (A,B,X,H) ──
    for rule in rr:
        pat = rule.get("pattern")
        if not pat:
            continue
        rid = rule["id"]
        level = rule["level"]
        for m in re.finditer(pat, text, re.MULTILINE):
            if _in_non_prose(m.start()):
                continue
            line_no = line_map.get(m.start(), 1)
            hits[rid].append(
                {
                    "rule": rid,
                    "level": level,
                    "strategy": rule["strategy"],
                    "match": m.group(0),
                    "span": [m.start(), m.end()],
                    "line": line_no,
                    "evidence": rule.get("evidence", ""),
                    "plain": rule.get("plain", ""),
                    "action": (
                        "rewrite"
                        if level not in ("X", "H") and rid not in DETECT_ONLY
                        else "report"
                    ),
                }
            )
        # process variants for A1
        for v in rule.get("variants", []):
            # 关键词预筛：变体里不出现触发词时直接跳过，避免长文本上做无谓的全量扫描。
            pre = v.get("prefilter")
            if pre and pre not in text:
                continue
            for m in re.finditer(v["pattern"], text):
                if _in_non_prose(m.start()):
                    continue
                line_no = line_map.get(m.start(), 1)
                hits[rid].append(
                    {
                        "rule": rid,
                        "level": level,
                        "strategy": f'{rule["strategy"]}·{v["name"]}',
                        "match": m.group(0),
                        "span": [m.start(), m.end()],
                        "line": line_no,
                        "evidence": rule.get("evidence", ""),
                        "plain": rule.get("plain", ""),
                        "action": "rewrite" if level == "A" else "report",
                    }
                )

    # ── B1 standalone: check for consecutive 的 in noun phrases ──
    if "B1" in hits:
        _detect_b1_de_density(text, hits["B1"], line_map)

    # ── B2 exemptions ──
    if "B2" in hits:
        _mark_b2_exemptions(text, hits["B2"])

    # ── B6: isomorphic adjacent sentences ──
    if "B6" in hits:
        _detect_b6_isomorphic(text, hits["B6"], prose_blocks, line_map)

    # ── structural metrics (C level) ──
    metrics = _compute_metrics(text, blocks, prose_blocks, total_han)

    # ── F level: character counts ──
    f_metrics = {
        "F1": text.count("——"),
        "F2": text.count("；"),
        "F3": text.count("\u201c") + text.count("\u201d"),
    }

    # ── summary ──
    summary = {}
    for rule in rr:
        rid = rule["id"]
        if rid in hits:
            count = len(hits[rid])
        elif rid in f_metrics:
            count = f_metrics[rid]
        else:
            count = 0
        lv = rule["level"]
        summary.setdefault(lv, {})[rid] = count
    summary["C"].update(metrics.get("C_counts", {}))

    # ── total actionable hits ──
    actionable = 0
    for rid, hlist in hits.items():
        actionable += sum(1 for h in hlist if h["action"] == "rewrite")

    return {
        "meta": {
            "chars": len(text),
            "hanzi": total_han,
            "k_chars": round(kk, 2),
            "paragraphs": len(prose_blocks),
            "blocks_total": len(blocks),
        },
        "summary": summary,
        "hits": {k: v for k, v in hits.items() if v},
        "f_metrics": f_metrics,
        "metrics": metrics["struct"],
        "actionable_total": actionable,
    }


def _build_line_map(text: str) -> dict:
    """Map character offset → line number (accounts for newline chars in full text)."""
    lm = {}
    offset = 0
    for no, line in enumerate(text.splitlines(), 1):
        for _ in line:
            lm[offset] = no
            offset += 1
        offset += 1  # skip the newline character after each line
    return lm


def _expand_left(text: str, start: int, limit: int = 6) -> int:
    """把命中起点向左扩到词边界，避免从半个词中间开始高亮（BUG-14）。

    只向左吞汉字，遇到标点/非汉字/已达上限即停。用于修正
    「识别并消除…」被切成「别并消除…」这类错位。
    """
    i = start
    moved = 0
    while i > 0 and moved < limit:
        ch = text[i - 1]
        if not re.match(r"[一-鿿]", ch):
            break
        i -= 1
        moved += 1
    return i


# 第二个「的」之后若直接是判断词，说明这是「主语+是+宾语」的主谓句，不是定语链。
_COPULA_AFTER_DE = re.compile(
    r"^(?:是|为|就是|在于|则|即|有|没有|能|会|可以|需要|必须)"
)


# 第二段（两个「的」之间）若出现判断词/否定词，说明它是「主语+谓语」小句而非修饰语。
_PRED_IN_MID = re.compile(r"(?:是|为|在于|则|即|有|没有|不|能|会|可以|需要|必须)")


def _detect_b1_de_density(text: str, existing: list, line_map: dict):
    """检测 B1 的「连续 de」形态：同一名词短语内连续「的」≥2。

    源库规则 4 判定之一即「『的』字连续两个以上」，脚本层未实现，此处补齐。
    豁免：正常的「领属链」三层定语（如「学生的作业的质量」「公司的产品的口碑」）
    是人类常见写法，不构成 AI 味。判定依据：中间项若以名词性领属收尾（人名/机构/人称/物名），
    视为领属链而非修饰链，豁免。真正要抓的是「修饰性长链」（如「能够显著提升效率的方法的核心」）。

    BUG-14 补充：若第三段以判断词开头（如「这类小标题的频率是人类的…」），
    说明整段是「主语+谓语」结构而非定语链，必须豁免，否则误报主谓句。
    """
    pattern = re.compile(r"[一-鿿]{2,12}的[一-鿿]{2,12}的[一-鿿]{2,12}")
    # 领属链常见中间项结尾：人称、机构、方位、抽象物名（作业/质量/口碑/性能/数据/结果…）
    for m in pattern.finditer(text):
        seg = m.group(0)
        # 切成 A的 B的 C
        parts = seg.split("的")
        if len(parts) != 3:
            continue
        mid = parts[1]
        tail = parts[2]
        # 第三段以判断词开头 → 主谓句（「…的是…」），不是定语链
        if _COPULA_AFTER_DE.match(tail):
            continue
        # 第二段含判断词/否定词 → 中间是小句（「…的频率是人类…」「…维度是连接词…」），不是定语链
        if _PRED_IN_MID.search(mid):
            continue
        # 中间项是领属链（名词性并列/领属）→ 豁免
        if len(mid) <= 3 or re.search(
            r"(?:生|者|人|公司|团队|部门|学校|老师|学生|的)$", mid
        ):
            continue
        start = _expand_left(text, m.start())
        end = m.end()
        existing.append(
            {
                "rule": "B1",
                "level": "B",
                "strategy": "过长前置定语·连续de",
                "match": text[start:end],
                "span": [start, end],
                "line": line_map.get(start, 1),
                "evidence": "配对复测前置定语长 GPT δ+0.48 / Opus δ+0.54",
                "plain": "中心词前面堆了太长一串修饰（超过15字），读起来累。拆成两个短句更顺。",
                "action": "report",
            }
        )


def _mark_b2_exemptions(text: str, hits: list):
    """标记 B2 命中中的豁免项（源库 SKILL.md 豁免：术语列表、专名并列、完整列举）。

    结构性判断：顿号连接的各项若为「同质、等长的名词/术语」，视为术语/专名并列，
    豁免不改；若各项是「能概括的杂项罗列」，才是真正的 AI 味顿号堆砌，保留改写。
    规则：三个并列项长度相近（最长/最短 ≤ 2 倍）且均 ≤ 8 字 → 术语并列，豁免。
    """
    for h in hits:
        m = h["match"]
        items = [x.strip() for x in m.split("、")]
        items = [x for x in items if x]
        if len(items) < 3:
            continue
        lengths = [len(x) for x in items]
        # 术语/专名并列：等长短词
        if max(lengths) <= 8 and max(lengths) <= min(lengths) * 2:
            h["action"] = "exempt"
            h["exempt_reason"] = "术语/专名并列"
            continue
        # 数字/序号枚举（1、2、3 / 一、二、三）不算并列
        if all(re.fullmatch(r"(?:第)?[0-9一二三四五六七八九十]+", x) for x in items):
            h["action"] = "exempt"
            h["exempt_reason"] = "序号枚举"


def _detect_b6_isomorphic(text: str, hits: list, prose_blocks: list, line_map: dict):
    """Detect structurally identical adjacent sentences (B6)."""
    for body, _ in prose_blocks:
        sents = [s for s in _split_sents(body) if len(s) > 10]
        for i in range(len(sents) - 1):
            sig_a = _sentence_signature(sents[i])
            sig_b = _sentence_signature(sents[i + 1])
            if sig_a == sig_b and sig_a[0] >= 1:
                hits.append(
                    {
                        "rule": "B6",
                        "level": "B",
                        "strategy": "相邻句结构同款",
                        "match": f"{sents[i][:30]}… ‖ {sents[i+1][:30]}…",
                        "span": [-1, -1],
                        "line": 0,
                        "evidence": "第一轮每百段 AI 9.41 vs 人类 4.81",
                        "plain": "相邻两句话法结构一模一样，像复制粘贴。打散其中一句。",
                        "action": "report",
                    }
                )
                break  # one per paragraph


def _compute_metrics(
    text: str, blocks: list, prose_blocks: list, total_han: int
) -> dict:
    """Compute C-level structural metrics."""
    sent_lens = []
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        for s in _split_sents(body):
            sent_lens.append(_hanzi(s) or 4)

    struct = {}
    if len(sent_lens) >= 3:
        mean = sum(sent_lens) / len(sent_lens)
        var = sum((x - mean) ** 2 for x in sent_lens) / len(sent_lens)
        struct["sentence_cv"] = round(math.sqrt(var) / mean, 3) if mean > 0 else None
    else:
        struct["sentence_cv"] = None

    # section CV
    sect_lens = []
    cur_len = 0
    for kind, body, _ in blocks:
        if kind == "heading":
            if cur_len > 0:
                sect_lens.append(cur_len)
            cur_len = 0
        elif kind == "prose":
            cur_len += len(body)
    if cur_len > 0:
        sect_lens.append(cur_len)
    if len(sect_lens) >= 3:
        mean = sum(sect_lens) / len(sect_lens)
        var = sum((x - mean) ** 2 for x in sect_lens) / len(sect_lens)
        struct["section_cv"] = round(math.sqrt(var) / mean, 3) if mean > 0 else None
    else:
        struct["section_cv"] = None

    # headings
    n_head = sum(1 for k, _, _ in blocks if k == "heading")
    struct["headings_per_kk"] = (
        round(n_head / (total_han / 1000), 3) if total_han > 500 else None
    )

    # MTLD rough estimate (bigrams)
    all_bigrams = []
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        for i in range(len(body) - 1):
            if _hanzi(body[i : i + 2]) == 2:
                all_bigrams.append(body[i : i + 2])
    struct["mtld_rough"] = (
        _mtld_estimate(all_bigrams) if len(all_bigrams) > 20 else None
    )

    # isomorphic count
    iso2_total = 0
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        sents = [s for s in _split_sents(body) if len(s) > 10]
        for i in range(len(sents) - 1):
            if (
                _sentence_signature(sents[i]) == _sentence_signature(sents[i + 1])
                and _sentence_signature(sents[i])[0] >= 1
            ):
                iso2_total += 1
    struct["isomorphic_per_100paras"] = (
        round(iso2_total / len(prose_blocks) * 100, 2) if prose_blocks else None
    )

    # B7 同义重命名：粗估「近义动词轮用」密度（脚本层只能做词面近义计数，不落具体句，仅供参考）
    # 词表：常见的「增强/提升/优化/改善/提高」互替组，同段内换用是源库规则10的疑似信号。
    _SYN_GROUPS = [
        {"优化", "增强", "提升", "改善", "提高"},
    ]
    syn_swap = 0
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        for grp in _SYN_GROUPS:
            found = [w for w in grp if w in body]
            if len(found) >= 2:
                syn_swap += 1
    struct["synonym_swap_paras"] = syn_swap

    # B8 衔接连环：粗估「段内连续明确承接词」最大连环长度（脚本层只能做连接词计数，仅供参考）
    _LINK_WORDS = (
        "此外",
        "然而",
        "因此",
        "而且",
        "同时",
        "另外",
        "总之",
        "换言之",
        "与此同时",
    )
    max_chain = 0
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        sents = _split_sents(body)
        chain = 0
        for s in sents:
            if any(s.startswith(w) for w in _LINK_WORDS):
                chain += 1
                max_chain = max(max_chain, chain)
            else:
                chain = 0
    struct["max_connect_chain"] = max_chain

    return {
        "struct": struct,
        "C_counts": {
            # C 级四条规则：用规则 id 作键，前端据此渲染「只报告」明细卡片
            "C1": struct["sentence_cv"],
            "C2": struct["section_cv"],
            "C3": struct["mtld_rough"],
            "C4": struct["max_connect_chain"],
            # 兼容旧前端：指标名键保留，值同源
            "sentence_cv_prompt": struct["sentence_cv"],
            "mtld_prompt": struct["mtld_rough"],
            "isomorphic_prompt": struct["isomorphic_per_100paras"],
            "synonym_swap": struct["synonym_swap_paras"],
            "max_connect_chain": struct["max_connect_chain"],
        },
    }


def _mtld_estimate(tokens: list, threshold: float = 0.72, min_len: int = 10) -> float:
    """Rough MTLD estimate using Chinese bigrams as pseudo-tokens."""
    if len(tokens) < min_len * 4:
        return 0

    def factors(seq):
        fac, types_seen, count = 0.0, set(), 0
        for t in seq:
            count += 1
            types_seen.add(t)
            if count >= min_len and len(types_seen) / count <= threshold:
                fac += 1
                types_seen, count = set(), 0
        if count:
            fac += (1 - len(types_seen) / count) / (1 - threshold)
        return max(fac, 1e-9)

    f, r = factors(tokens), factors(tokens[::-1])
    return round(len(tokens) / 2 * (1 / f + 1 / r))
