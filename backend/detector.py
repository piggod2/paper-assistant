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
_CODE_QUOTE = re.compile(r"^(?:>|    )")
_LIST = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.、)])\s")


def _hanzi(s: str) -> int:
    return len(re.findall(r"[一-鿿]", s))


def _split_sents(para: str) -> list:
    return [p.strip() for p in re.split(r"[。！？；]", para) if len(p.strip()) >= 4]


def _paragraph_blocks(text: str) -> list:
    """Split text into (kind, block_text, first_line_no) blocks."""
    blocks, cur, cur_kind = [], [], None
    for no, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            cur.append(line); continue
        if not line.strip():
            if cur:
                blocks.append((cur_kind or "prose", "\n".join(cur), len(blocks) + 1))
                cur, cur_kind = [], None
            continue
        cur.append(line)
        if _HEADING.match(line):
            cur_kind = "heading" if cur_kind is None else cur_kind
        elif _LIST.match(line):
            cur_kind = "list" if cur_kind is None else cur_kind
        elif _CODE_QUOTE.match(line):
            cur_kind = "quote" if cur_kind is None else cur_kind
    if cur:
        blocks.append((cur_kind or "prose", "\n".join(cur), len(blocks) + 1))
    return blocks


def _sentence_signature(sent: str) -> tuple:
    """Structural fingerprint of a sentence."""
    return (sent.count("，"), "：" in sent or ":" in sent, len(sent) // 15)


# ── detection ──

def detect(text: str) -> dict:
    """Run full detection. Returns structured report."""
    rr = rule_loader.get_rules()
    total_han = _hanzi(text)
    kk = total_han / 1000 if total_han > 0 else 1
    blocks = _paragraph_blocks(text)
    prose_blocks = [(b, n) for k, b, n in blocks if k == "prose"]

    hits: dict[str, list] = {r["id"]: [] for r in rr if r.get("pattern")}
    line_map = _build_line_map(text)

    # ── regex-based rules (A,B,X,H) ──
    for rule in rr:
        pat = rule.get("pattern")
        if not pat:
            continue
        rid = rule["id"]
        level = rule["level"]
        for m in re.finditer(pat, text, re.MULTILINE):
            line_no = line_map.get(m.start(), 1)
            hits[rid].append({
                "rule": rid, "level": level, "strategy": rule["strategy"],
                "match": m.group(0), "span": [m.start(), m.end()],
                "line": line_no,
                "evidence": rule.get("evidence", ""),
                "action": "report" if level in ("X", "H") else "rewrite"
            })
        # process variants for A1
        for v in rule.get("variants", []):
            for m in re.finditer(v["pattern"], text):
                line_no = line_map.get(m.start(), 1)
                hits[rid].append({
                    "rule": rid, "level": level, "strategy": f'{rule["strategy"]}·{v["name"]}',
                    "match": m.group(0), "span": [m.start(), m.end()],
                    "line": line_no,
                    "evidence": rule.get("evidence", ""),
                    "action": "rewrite" if level == "A" else "report"
                })

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
        "F3": text.count('"') + text.count('"'),
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
            "chars": len(text), "hanzi": total_han, "k_chars": round(kk, 2),
            "paragraphs": len(prose_blocks), "blocks_total": len(blocks)
        },
        "summary": summary,
        "hits": {k: v for k, v in hits.items() if v},
        "f_metrics": f_metrics,
        "metrics": metrics["struct"],
        "actionable_total": actionable
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


def _detect_b1_de_density(text: str, existing: list, line_map: dict):
    """Detect B1 via consecutive 的 pattern (≥2 的 in one noun phrase)."""
    pattern = re.compile(r"[一-鿿]{2,10}的[一-鿿]{2,10}的[一-鿿]{2,10}")
    for m in pattern.finditer(text):
        existing.append({
            "rule": "B1", "level": "B", "strategy": "过长前置定语·连续de",
            "match": m.group(0), "span": [m.start(), m.end()],
            "line": line_map.get(m.start(), 1),
            "evidence": "配对复测前置定语长 GPT δ+0.48 / Opus δ+0.54",
            "action": "rewrite"
        })


def _mark_b2_exemptions(text: str, hits: list):
    """Mark B2 hits that fall under exemption categories."""
    exempt_keywords = ["功能", "配置", "法规", "术语", "环节", "步骤", "模块", "维度"]
    for h in hits:
        m = h["match"]
        if any(kw in m for kw in exempt_keywords):
            h["action"] = "exempt"
            h["exempt_reason"] = "完整列举"


def _detect_b6_isomorphic(text: str, hits: list, prose_blocks: list, line_map: dict):
    """Detect structurally identical adjacent sentences (B6)."""
    for _, body, _ in prose_blocks:
        sents = [s for s in _split_sents(body) if len(s) > 10]
        for i in range(len(sents) - 1):
            sig_a = _sentence_signature(sents[i])
            sig_b = _sentence_signature(sents[i + 1])
            if sig_a == sig_b and sig_a[0] >= 1:
                hits.append({
                    "rule": "B6", "level": "B", "strategy": "相邻句结构同款",
                    "match": f"{sents[i][:30]}… ‖ {sents[i+1][:30]}…",
                    "span": [-1, -1],
                    "line": 0, "evidence": "第一轮每百段 AI 9.41 vs 人类 4.81",
                    "action": "rewrite"
                })
                break  # one per paragraph


def _compute_metrics(text: str, blocks: list, prose_blocks: list, total_han: int) -> dict:
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
    struct["headings_per_kk"] = round(n_head / (total_han / 1000), 3) if total_han > 500 else None

    # MTLD rough estimate (bigrams)
    all_bigrams = []
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        for i in range(len(body) - 1):
            if _hanzi(body[i:i + 2]) == 2:
                all_bigrams.append(body[i:i + 2])
    struct["mtld_rough"] = _mtld_estimate(all_bigrams) if len(all_bigrams) > 20 else None

    # isomorphic count
    iso2_total = 0
    for item in prose_blocks:
        body = item[0] if len(item) >= 1 else ""
        sents = [s for s in _split_sents(body) if len(s) > 10]
        for i in range(len(sents) - 1):
            if _sentence_signature(sents[i]) == _sentence_signature(sents[i + 1]) and _sentence_signature(sents[i])[0] >= 1:
                iso2_total += 1
    struct["isomorphic_per_100paras"] = round(iso2_total / len(prose_blocks) * 100, 2) if prose_blocks else None

    return {
        "struct": struct,
        "C_counts": {
            "sentence_cv_prompt": struct["sentence_cv"],
            "mtld_prompt": struct["mtld_rough"],
            "isomorphic_prompt": struct["isomorphic_per_100paras"]
        }
    }


def _mtld_estimate(tokens: list, threshold: float = 0.72, min_len: int = 10) -> float:
    """Rough MTLD estimate using Chinese bigrams as pseudo-tokens."""
    if len(tokens) < min_len * 4:
        return 0

    def factors(seq):
        fac, types_seen, count = 0.0, set(), 0
        for t in seq:
            count += 1; types_seen.add(t)
            if count >= min_len and len(types_seen) / count <= threshold:
                fac += 1; types_seen, count = set(), 0
        if count:
            fac += (1 - len(types_seen) / count) / (1 - threshold)
        return max(fac, 1e-9)

    f, r = factors(tokens), factors(tokens[::-1])
    return round(len(tokens) / 2 * (1 / f + 1 / r))