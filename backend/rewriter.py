"""
Rewrite engine — applies detection hits with safety checks.
Follows lieflat-less-ai-tone rewrite principles: minimal change, info conservation.
"""

import re
try:
    from . import rules as rule_loader
except ImportError:
    import rules as rule_loader


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
        if not _safety_check(changed_text, start, start + len(original_segment), replacement):
            safety_failures.append({
                "rule": rid, "level": level, "strategy": rule["strategy"],
                "original": original_segment, "attempted": replacement,
                "reason": "安全检查未通过，已保留原文"
            })
            continue

        # apply
        changed_text = changed_text[:start] + replacement + changed_text[end:]
        changes.append({
            "rule": rid, "level": level, "strategy": rule["strategy"],
            "original": original_segment, "replacement": replacement,
            "span": [start, start + len(replacement)],
            "action": "rewrite"
        })

    return {
        "original": text,
        "polished": changed_text,
        "changes": changes,
        "safety_failures": safety_failures,
        "total_changes": len(changes),
        "total_failures": len(safety_failures)
    }


def _resolve_levels(opts: dict) -> list:
    intensity = opts.get("intensity", "standard")
    intensities = rule_loader.load_rules().get("rewriteIntensities", {})
    cfg = intensities.get(intensity, intensities.get("standard", {"levels": ["A", "B", "F"]}))
    levels = list(cfg["levels"])
    if opts.get("defluff", True) and "B6" in cfg.get("extra", []):
        if "B6" not in levels:
            levels.append("B6")
    return levels


def _compute_replacement(hit: dict, match: str, full_text: str, match_start: int) -> str | None:
    rid = hit["rule"]
    rule = hit.get("rule_obj", {})

    if rid == "A1":
        # Main pattern: 并不是X，而是Y → 是Y
        # Variants: 看似X，实则Y → Y ; 你以为X，其实Y → Y ; X不重要，重要的是Y → Y
        strat = hit.get("strategy", "")
        if "看似" in strat:
            m = re.search(r"(?:看似|表面上|表面)([^，。；！？]+)[，,]\s*(?:实则|实际上|其实)\s*([^，。；！？]+)", match)
            return m.group(2) if m else None
        if "你以为" in strat:
            m = re.search(r"(?:你以为|大家以为|很多人以为)([^，。；！？]+)[，,]\s*其实\s*([^，。；！？]+)", match)
            return m.group(2) if m else None
        if "不重要" in strat:
            m = re.search(r"[^，。；！？]+不重要[，,]\s*(?:重要的是|真正重要的是|关键是)\s*([^，。；！？]+)", match)
            return m.group(1) if m else None
        # main pattern
        m = re.search(r"(?:并不是|并非|不是|与其说)([^，。；！？、]+)[，,]\s*(?:而是|不如说|其实是)\s*([^，。；！？]+)", match)
        if m:
            # If match follows a sentence boundary or dash, dropping "不是" ruins the subject;
            # the copula "是" would become a dangling fragment. Just return the predicate.
            preceding_char = full_text[match_start - 1] if match_start > 0 else ""
            if match_start == 0 or preceding_char in "。——！？\n\r\u2014；":
                return m.group(2)
            return f"是{m.group(2)}"
        return None

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
        # 对于X来说， → (remove, preserve preceding 。！？)
        boundary = match[0] if match and match[0] in "。！？" else ""
        return boundary

    elif rid == "B4":
        # 当X时， → X，
        m = re.match(r"当([^，。]{2,25})时[，,]", match)
        return f"{m.group(1)}，" if m else None

    elif rid == "B5":
        # 然而， → (remove, preserve preceding \n or 。！？)
        first = match[0] if match else ""
        return first if first in "。！？\n" else ""

    elif rid == "B1":
        # 过长前置定语：detection only, auto-rewrite too risky
        return None

    elif rid == "B2":
        # 顿号罗列过密：最后一个顿号换"和"，打破AI枚举感
        # 但如果后面紧接 "以及/及/与/和/或"，只删顿号不加"和"，避免"的和以及"等双连词
        positions = [i for i, c in enumerate(match) if c == "、"]
        if len(positions) >= 2:
            last = positions[-1]
            after_last = match[last + 1:]
            if re.match(r'^(?:以及|及|与|和|或)', after_last):
                return match[:last] + match[last + 1:]
            return match[:last] + "和" + match[last + 1:]
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
    before = text[max(0, old_start - 5):old_start]
    after = text[old_end:old_end + 5]
    new_junction = before + replacement + after
    old_junction = text[max(0, old_start - 5):old_end + 5]
    if orphan_pattern.search(new_junction) and not orphan_pattern.search(old_junction):
        return False

    # 2. Bracket/quotation pairing
    for pair in [("(", ")"), ("（", "）"), (""", """), (""", """)]:
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

    return True