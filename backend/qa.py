"""
论文智助 — 大模型问答代理（DeepSeek / OpenAI 兼容接口）

用于规则引擎兜底：当 agent.chat 返回 fallback=True 时，
前端调用 /api/qa/chat 走这里，由后端代理转发到 DeepSeek 等
OpenAI 兼容服务，避免前端暴露 API Key、也绕开登录墙。

配置（.env）：
    DEEPSEEK_API_KEY   必填，否则返回 503
    DEEPSEEK_BASE_URL  可选，默认 https://api.deepseek.com
    DEEPSEEK_MODEL     可选，默认 deepseek-chat
"""

import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


# 允许的模型白名单（防止任意模型名注入，也兼容旧别名）
MODELS = {
    "deepseek-v4-flash": "deepseek-v4-flash",   # 主力：便宜快速，非思考模式（默认）
    "deepseek-v4-pro": "deepseek-v4-pro",       # 旗舰：强推理，贵约 3 倍
    "deepseek-chat": "deepseek-chat",           # 旧别名（兼容，映射 flash 非思考）
    "deepseek-reasoner": "deepseek-reasoner",   # 旧别名（兼容，映射 flash 思考）
}


def resolve_model(requested: str) -> str:
    """把前端传来的模型名解析为合法模型名，非法则回退默认。"""
    if requested in MODELS:
        return MODELS[requested]
    return MODELS[MODEL] if MODEL in MODELS else "deepseek-v4-flash"

SYSTEM_PROMPT = (
    "你是「论文智助」的智能问答助手，服务于写论文的学生。\n"
    "职责两类：1) 回答工具使用问题（检测AI味/润色/中英翻译/找文献）；2) 给学术写作建议。\n"
    "工具背景：检测/润色基于结构化规则集，只改有实证支撑的AI味信号；翻译走百度，检索走arXiv。\n"
    "你同时要遵守下面的「去AI味」核心规则（源自 lieflat-less-ai-tone，CC BY-NC 4.0，"
    "基于629篇对照+270对配对复测）。给润色建议时按这些规则判断，不要凭直觉乱改。\n"
    "\n"
    "【可改的AI味信号（有实证支撑）】\n"
    "- 翻案腔：'不是A而是B'『并非…而是』『与其说…不如说』『看似…实则』『你以为…其实』『A不重要，重要的是B』→ 正面直陈。\n"
    "- 提示语冒号：'一句话总结：''核心是：''关键在于：'→ 不承担信息就删提示语，冒号换句号。\n"
    "- 起手式：'说白了''说穿了''先说结论'→ 删。\n"
    "- 过长前置定语：中心词前修饰>15字 或 连续'的'≥2 → 拆两句。\n"
    "- 前置话题壳：'对于…来说''就…而言''在…方面'→ 后句主语明确时删壳。\n"
    "- '当…时'前置从句：删'当''时'。\n"
    "- 句首连接词当路标：'然而/因此/此外/总之'句首 → 移到主语后。\n"
    "- 密集顿号并列：一句≥3项同质罗列 → 能概括就概括。\n"
    "\n"
    "【永不修改（X级，经复测方向反转或净零，是人类正常写法）】\n"
    "序数词小标题（一二三）、'这意味着'复述、空转句引列表（'几种场景：'+列表）、概括替代具体信息、"
    "精确数字堆砌、漂亮词（赋能/闭环/抓手）、名词化/明喻/设问/模糊量词/首先其次总之、'其'字。"
    "这些不能当AI味去改，用户问起要说明是有意为之。\n"
    "\n"
    "【铁律：宁漏报不误报】\n"
    "1. 最小改动：只改必需部分。2. 信息守恒：每个实词都能指出原文出处，'可能'改'一定'=篡改。\n"
    "3. 不制造参差：不为节奏改句长。4. 结构不动：标题层级/段落顺序/列表/表格/引用/代码块不动。\n"
    "5. 有风格参考先读参考。6. 改完能对应规则编号、实词有出处、复测清零。\n"
    "拿不准就不改，宁可漏报，不可误改用户正文。\n"
    "\n"
    "要求：中文、简洁、像靠谱学长；不编造；给可执行步骤；控制在300字内。"
)


def is_available() -> bool:
    return bool(_api_key())


# ── 语义层封闭判读 ──
# 源库三层分工中的「语义层」：需理解句意才能判定的规则（10-13），
# 脚本层无法安全完成，改由模型按封闭判据输出结构化建议。
# 只出「建议 + 理由」，绝不自动改写正文；改写仍需用户确认。


def chat_once(messages: list, model: str = "", temperature: float = 0.0) -> str:
    """非流式单次调用，返回完整文本。异常时抛出 RuntimeError。

    公开导出：供 searcher 等模块复用来做 LLM 辅助（如中文查询提炼英文检索词）。
    """
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": resolve_model(model),
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    resp = requests.post(_chat_url(), headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        try:
            body = resp.json()
            msg = body.get("error", {}).get("message", "未知错误")
        except Exception:
            msg = resp.text[:200]
        raise RuntimeError(f"DeepSeek 返回 {resp.status_code}: {msg}")
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek 未返回有效结果")
    return (choices[0].get("message") or {}).get("content", "").strip()


# 兼容旧调用点（judge_semantic 内部仍用 _chat_once 这个旧名）
_chat_once = chat_once


_SEMANTIC_TASKS = {
    # 源库规则 12：结论提示冒号（唯一真信号档）
    "conclusion_colon": {
        "判据": "冒号前是一句结论性判断（给结论/定性），冒号后展开论证或解释。只有这种「结论在前、论证在后」的冒号才是AI味信号；"
                "引出人物原话、小标题里的冒号、列表项内部、网址/代码里的冒号、总说分说都不算。",
        "豁免": "冒号只起分隔列举作用、不构成「结论→论证」关系的，一律不算。",
    },
    # 源库规则 13：高度同构三连
    "isomorphic_triple": {
        "判据": "连续三句的句法骨架逐字复刻（主语位置/谓语结构/逗号位置/收尾方式完全一样）。只有这种「高度同构」档才是信号；"
                "宽口径排比、清单式列举、文学排比、叙事推进不构成AI味。",
        "豁免": "清单式段落、对话引语、文学排比、叙事推进、故意排比，一律不算。",
    },
}


def judge_semantic(task: str, context: str, model: str = "") -> dict:
    """对一段文本做封闭判读，返回结构化建议。只出建议，不自动改写。

    task 必须是 _SEMANTIC_TASKS 的键，context 是要判读的原文片段。
    返回 {"ok": bool, "verdict": str, "suggestions": [...], "error": str|None}。
    """
    if not is_available():
        return {"ok": False, "verdict": "", "suggestions": [], "error": "未配置 DEEPSEEK_API_KEY"}
    spec = _SEMANTIC_TASKS.get(task)
    if not spec:
        return {"ok": False, "verdict": "", "suggestions": [], "error": f"未知判读任务: {task}"}

    user_prompt = (
        f"你是「去AI味」规则集的语义层判读器。请只按下面的封闭判据判断，不要引入判据以外的标准，"
        f"拿不准就判「否」，宁可漏报不可误报。\n\n"
        f"【判据】{spec['判据']}\n"
        f"【豁免】{spec['豁免']}\n\n"
        f"【待判读原文】\n{context}\n\n"
        f"请只输出一个 JSON 对象，不要输出任何其他文字，格式：\n"
        f'{{"verdict": "是"或"否", "suggestions": ["若判定为是，给出具体、最小改动的建议句，每条独立；若否则空数组"], "reason": "一句话说明判据命中或豁免原因"}}'
    )
    messages = [
        {"role": "system", "content": "你是去AI味规则集的语义层判读器，只按封闭判据输出JSON。"},
        {"role": "user", "content": user_prompt},
    ]
    try:
        raw = _chat_once(messages, model=model, temperature=0.0)
    except RuntimeError as e:
        return {"ok": False, "verdict": "", "suggestions": [], "error": str(e)}

    # 提取 JSON：模型可能包在 ```json ... ``` 里
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "verdict": "", "suggestions": [], "error": f"判读结果解析失败: {raw[:200]}"}
    return {
        "ok": True,
        "verdict": obj.get("verdict", ""),
        "suggestions": obj.get("suggestions", []) or [],
        "reason": obj.get("reason", ""),
        "error": None,
    }


def _chat_url() -> str:
    return f"{BASE_URL}/chat/completions"


def stream_chat(messages: list, model: str = ""):
    """流式调用 DeepSeek，逐段 yield 文本。异常时抛出。"""
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": resolve_model(model),
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    with requests.post(
        _chat_url(), headers=headers, json=payload, stream=True, timeout=60
    ) as resp:
        if resp.status_code != 200:
            # 读取错误信息，抛出带 detail 的异常
            try:
                body = resp.json()
                msg = body.get("error", {}).get("message", "未知错误")
            except Exception:
                msg = resp.text[:200]
            raise RuntimeError(f"DeepSeek 返回 {resp.status_code}: {msg}")
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content
