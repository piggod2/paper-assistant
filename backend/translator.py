"""
Baidu Translate API integration.
API key from BAIDU_APPID / BAIDU_SECRET env vars.
"""

import hashlib
import os
import random
import re
import time
from urllib import parse

import requests

BAIDU_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"


def is_available() -> bool:
    return bool(os.getenv("BAIDU_APPID") and os.getenv("BAIDU_SECRET"))


def _sign(q: str, salt: str) -> str:
    appid = os.getenv("BAIDU_APPID", "")
    secret = os.getenv("BAIDU_SECRET", "")
    raw = appid + q + salt + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def translate(text: str, from_lang: str = "en", to_lang: str = "zh") -> dict:
    """
    Translate text via Baidu Translate API.
    Returns {translated, segments, elapsed_ms, source_lang, target_lang}
    or {error, detail} on failure.
    """
    if not is_available():
        return {"error": "翻译未配置", "detail": "请在 .env 设置 BAIDU_APPID / BAIDU_SECRET"}

    if not text.strip():
        return {"translated": "", "segments": 0, "elapsed_ms": 0, "source_lang": from_lang, "target_lang": to_lang}

    plan = os.getenv("BAIDU_PLAN", "advanced")
    max_chars = 6000 if plan == "advanced" else 1000
    t0 = time.perf_counter()

    # split into segments if needed
    segments = _segment_text(text, max_chars)

    results = []
    for i, seg in enumerate(segments):
        salt = str(random.randint(32768, 65536))
        sign = _sign(seg, salt)
        appid = os.getenv("BAIDU_APPID", "")

        params = {
            "q": seg,
            "from": from_lang,
            "to": to_lang,
            "appid": appid,
            "salt": salt,
            "sign": sign,
        }

        try:
            resp = requests.post(BAIDU_URL, data=params, timeout=10)
            data = resp.json()
        except requests.RequestException as e:
            return {"error": "翻译请求失败", "detail": str(e)}
        except ValueError:
            return {"error": "翻译响应解析失败", "detail": f"Status {resp.status_code}"}

        if "error_code" in data:
            code = data["error_code"]
            messages = {
                "54001": "签名错误——q 参与签名时不得预先 URL encode",
                "54003": "访问频率受限",
                "54005": "单次请求过长",
                "52001": "请求超时",
                "52002": "系统错误",
            }
            return {"error": f"翻译失败 (code {code})", "detail": messages.get(code, data.get("error_msg", "未知错误"))}

        trans_result = data.get("trans_result", [])
        for t in trans_result:
            results.append(t.get("dst", ""))

        if i < len(segments) - 1:
            time.sleep(0.15)

    elapsed = int((time.perf_counter() - t0) * 1000)
    return {
        "translated": "\n".join(results),
        "segments": len(segments),
        "elapsed_ms": elapsed,
        "source_lang": from_lang,
        "target_lang": to_lang
    }


def _segment_text(text: str, max_chars: int) -> list[str]:
    """Split text into segments along sentence boundaries, not mid-word."""
    if len(text) <= max_chars:
        return [text]

    segments = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            segments.append(remaining)
            break
        cut = max_chars
        # try to find sentence boundary
        for sep in ["\n\n", "\n", "。", "！", "？", ".", "!", "?"]:
            idx = remaining[:cut].rfind(sep)
            if idx > max_chars * 0.6:
                cut = idx + len(sep)
                break
        segments.append(remaining[:cut])
        remaining = remaining[cut:].strip()
    return [s for s in segments if s.strip()]