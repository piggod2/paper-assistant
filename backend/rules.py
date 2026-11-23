"""Load and validate polish rules from JSON. Central rule store for detector + rewriter."""

import json
from pathlib import Path
from typing import Optional

RULES_PATH = Path(__file__).parent.parent / "data" / "polish-rules.json"

_cache: Optional[dict] = None


def load_rules() -> dict:
    """Load full rules database (cached)."""
    global _cache
    if _cache is None:
        with open(RULES_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
        _validate(_cache)
    return _cache


def _validate(data: dict):
    """Basic sanity check on loaded rules."""
    rules = data.get("rules", [])
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        dupes = [rid for rid in set(ids) if ids.count(rid) > 1]
        raise ValueError(f"Duplicate rule IDs: {dupes}")
    for r in rules:
        if not all(k in r for k in ("id", "level", "strategy")):
            raise ValueError(f"Rule missing required fields (id/level/strategy): {r}")


def get_rules() -> list:
    return load_rules()["rules"]


def get_rule_by_id(rule_id: str) -> Optional[dict]:
    for r in get_rules():
        if r["id"] == rule_id:
            return r
    return None


def get_rules_by_level(level: str) -> list:
    return [r for r in get_rules() if r["level"] == level]


def get_active_rules(levels: list) -> list:
    """Return rules whose level is in `levels` AND have a usable pattern/replacement."""
    active = []
    for r in get_rules():
        if r["level"] not in levels:
            continue
        if r.get("pattern") or r.get("level") in ("C", "F"):
            active.append(r)
    return active


def get_grades() -> dict:
    return load_rules()["grades"]


def get_meta() -> dict:
    return load_rules()["meta"]