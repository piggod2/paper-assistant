"""
论文智助 — FastAPI 入口
所有接口：/api/health /api/rules /api/detect /api/polish /api/judge /api/translate /api/search /api/pipeline /api/share
"""

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()

try:
    from . import detector, rewriter, translator, searcher, agent, qa
    from .rules import get_rules, get_meta
except ImportError:
    import detector, rewriter, translator, searcher, agent, qa
    from rules import get_rules, get_meta

app = FastAPI(title="论文智助 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── middleware ──


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["X-Process-Time"] = f"{int((time.perf_counter() - t0) * 1000)}ms"
    # 页面与前端脚本不缓存：避免浏览器拿着旧版前端继续跑（新版已改走后端大模型）
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


# 旧版（legacy）已停用：文件保留在磁盘上，但不再对外提供访问，
# 避免与新版 frontend-vue 共用同一静态目录时被误访问而参与进程。
LEGACY_PATHS = (
    "/legacy",
    "/agent.html",
    "/vue.global.prod.js",
    "/workbuddy-cloud-sdk.js",
    "/config.js",
)


@app.middleware("http")
async def block_legacy(request: Request, call_next):
    path = request.url.path
    if any(path == p or path.startswith(p + "/") for p in LEGACY_PATHS):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "旧版页面已停用，请访问 /"}, status_code=404)
    return await call_next(request)


# ── models ──


class TextRequest(BaseModel):
    # 请求体长度上限：防止恶意/误操作超长文本放大检测正则的耗时，也作一层防滥用保护
    text: str = Field(..., max_length=50000)


class PolishRequest(BaseModel):
    text: str = Field(..., max_length=50000)
    options: Optional[dict] = None


class JudgeRequest(BaseModel):
    text: str = Field(..., max_length=50000)
    task: str = ""  # conclusion_colon | isomorphic_triple


class SearchRequest(BaseModel):
    text: str = Field(..., max_length=50000)
    limit: int = Field(default=5, ge=1, le=50)
    source: str = "auto"


class PipelineRequest(BaseModel):
    text: str = Field(..., max_length=50000)
    run_translate: bool = True
    run_search: bool = True
    run_polish: bool = True
    limit: int = Field(default=5, ge=1, le=50)
    options: Optional[dict] = None


class ShareRequest(BaseModel):
    text: str = Field(..., max_length=50000)
    detect_report: Optional[dict] = None
    polished: Optional[str] = None
    changes: Optional[list] = None


class AgentRequest(BaseModel):
    message: str = Field(..., max_length=50000)
    history: Optional[list] = None
    # 意图模式：auto=自动识别（默认）| chat=强制自由问答 | polish=强制润色 | detect=强制检测
    mode: Optional[str] = "auto"


class QaChatRequest(BaseModel):
    message: str = Field(..., max_length=50000)
    history: Optional[list] = None
    model: Optional[str] = ""
    user_name: Optional[str] = ""
    custom_prompt: Optional[str] = ""


# ── in-memory share store ──

_share_store: dict[str, dict] = {}

# 分享存储上限：超过则按创建时间 FIFO 淘汰最旧条目，防止长时间运行内存只增不减
MAX_SHARE = 200
# 分享有效期（秒）：过期自动失效，读取时惰性清理
SHARE_TTL = 7 * 24 * 3600


def _prune_share_store() -> None:
    """清理过期分享；超上限时按创建顺序 FIFO 淘汰最旧条目。"""
    now = time.time()
    expired = [
        code
        for code, item in _share_store.items()
        if now - item.get("_ts", now) > SHARE_TTL
    ]
    for code in expired:
        _share_store.pop(code, None)
    # 仍超上限（多为未过期但积压）时，按 _ts 升序淘汰最旧的
    if len(_share_store) > MAX_SHARE:
        oldest = sorted(
            _share_store.items(), key=lambda kv: kv[1].get("_ts", 0)
        )[: len(_share_store) - MAX_SHARE]
        for code, _ in oldest:
            _share_store.pop(code, None)


# ── endpoints ──


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "论文智助",
        "version": "1.0",
        "modules": {
            "detect": True,
            "polish": True,
            "translate": translator.is_available(),
            "search": searcher.is_available(),
            "pipeline": True,
        },
    }


@app.get("/api/rules")
async def api_rules():
    """Return full polish-rules.json with attribution."""
    data = {
        "meta": get_meta(),
        "grades": {
            "A": "机械改",
            "B": "建议改",
            "C": "只报告",
            "F": "指纹",
            "X": "永不修改",
            "H": "人审区",
        },
        "rules": get_rules(),
    }
    return data


def _polish_sync(text: str, options: dict | None) -> dict:
    """同步执行「检测 → 润色」（英文额外先翻译再检测润色）。

    抽成独立同步函数，由接口用 asyncio.to_thread 调度，避免 CPU 密集计算阻塞事件循环。
    """
    report = detector.detect(text)
    result = rewriter.rewrite(text, report, options)

    # 英文输入：先翻译成中文再润色（检测/改写引擎针对中文 AI 腔调，
    # 对英文原文基本无效，直接返回英文会让用户困惑「润色了还是英文」）
    translated_from = ""
    if not re.search(r"[一-鿿]", text) and translator.is_available():
        tr = translator.translate(text, "en", "zh")
        if "error" not in tr and tr.get("translated", "").strip():
            translated = tr["translated"]
            report = detector.detect(translated)
            result = rewriter.rewrite(translated, report, options)
            translated_from = "en"

    return {
        "polished": result["polished"],
        "original": result["original"],
        "changes": result["changes"],
        "safety_failures": result["safety_failures"],
        "total_changes": result["total_changes"],
        "translated_from": translated_from,
        "report": {
            "summary": report["summary"],
            "hits": report["hits"],
            "metrics": report["metrics"],
            "f_metrics": report["f_metrics"],
        },
    }


@app.post("/api/detect")
async def api_detect(req: TextRequest):
    if not req.text.strip():
        return {"success": True, "data": {"hits": {}, "summary": {}, "metrics": {}}}
    report = await asyncio.to_thread(detector.detect, req.text)
    return {"success": True, "data": report}


@app.post("/api/polish")
async def api_polish(req: PolishRequest):
    if not req.text.strip():
        return {
            "success": True,
            "data": {
                "polished": "",
                "original": "",
                "changes": [],
                "safety_failures": [],
                "total_changes": 0,
                "report": {},
            },
        }
    data = await asyncio.to_thread(_polish_sync, req.text, req.options)
    return {"success": True, "data": data}


@app.post("/api/judge")
async def api_judge(req: JudgeRequest):
    """语义层封闭判读接口：对一段文本按指定规则做「只出建议、不自动改写」的精判。

    task 取值：
      conclusion_colon  → 源库规则12（结论提示冒号）
      isomorphic_triple → 源库规则13（高度同构三连）
    """
    if not req.text.strip():
        return {"success": True, "data": {"ok": False, "error": "文本为空"}}
    if not qa.is_available():
        return {
            "success": True,
            "data": {"ok": False, "error": "未配置 DEEPSEEK_API_KEY，无法做语义判读"},
        }
    result = await asyncio.to_thread(
        qa.judge_semantic, req.task or "conclusion_colon", req.text
    )
    return {"success": True, "data": result}


@app.post("/api/translate")
async def api_translate(req: TextRequest):
    if not translator.is_available():
        raise HTTPException(
            503, detail="翻译未配置，请在 .env 设置 BAIDU_APPID / BAIDU_SECRET"
        )
    # 自动方向：含中文→zh→en，否则 en→zh（中英互译）
    result = await asyncio.to_thread(translator.translate, req.text, "auto")
    if "error" in result:
        raise HTTPException(502, detail=result["detail"])
    return {"success": True, "data": result}


@app.post("/api/search")
async def api_search(req: SearchRequest):
    result = await asyncio.to_thread(searcher.search, req.text, req.limit, req.source)
    return {"success": True, "data": result}


def _run_pipeline(text: str, req: PipelineRequest) -> dict:
    steps = []
    translation = ""
    papers = []
    detect_report = None
    polished = ""
    changes = []

    # step 1: translate
    if req.run_translate and translator.is_available():
        t0 = time.perf_counter()
        tr = translator.translate(text, "auto")
        elapsed = int((time.perf_counter() - t0) * 1000)
        if "error" not in tr:
            translation = tr.get("translated", "")
            steps.append(
                {
                    "step": "translate",
                    "status": "ok",
                    "elapsed_ms": elapsed,
                    "message": f"翻译完成，{tr.get('segments',1)}段",
                }
            )
        else:
            steps.append(
                {
                    "step": "translate",
                    "status": "skipped",
                    "elapsed_ms": elapsed,
                    "message": tr.get("detail", "翻译失败"),
                }
            )
    else:
        steps.append(
            {
                "step": "translate",
                "status": "skipped",
                "elapsed_ms": 0,
                "message": "翻译未配置或未启用",
            }
        )

    # step 2: search
    # arXiv / Semantic Scholar 都是英文库：原文含英文时直接用原文检索，
    # 避免拿「中译后」的文本抽词导致关键词跑偏（如只抽到 model）
    if re.search(r"[a-zA-Z]{3,}", text):
        text_for_search = text
    else:
        text_for_search = translation or text
    if req.run_search:
        t0 = time.perf_counter()
        sr = searcher.search(text_for_search[:300], req.limit)
        elapsed = int((time.perf_counter() - t0) * 1000)
        papers = sr.get("results", [])
        source = sr.get("source_used", "none")
        steps.append(
            {
                "step": "search",
                "status": "ok" if papers else "empty",
                "elapsed_ms": elapsed,
                "message": f"{source}：{len(papers)}篇",
            }
        )
    else:
        steps.append(
            {
                "step": "search",
                "status": "skipped",
                "elapsed_ms": 0,
                "message": "未启用",
            }
        )

    # step 3: polish (core — always runs)
    if req.run_polish:
        t0 = time.perf_counter()
        # 检测/改写是针对中文 AI 腔调的：原文本身是中文就润色原文，
        # 否则（英文论文）才退回译文，避免把中文论文润成英文译文
        text_for_polish = text if re.search(r"[一-鿿]", text) else (translation or text)
        detect_report = detector.detect(text_for_polish)
        rw = rewriter.rewrite(text_for_polish, detect_report, req.options)
        polished = rw["polished"]
        changes = rw["changes"]
        elapsed = int((time.perf_counter() - t0) * 1000)
        n = rw["total_changes"]
        n_fail = rw["total_failures"]
        msg = f"检测{detect_report['actionable_total']}处，改写{n}处"
        if n_fail:
            msg += f"，{n_fail}处安全检查未通过"
        steps.append(
            {"step": "polish", "status": "ok", "elapsed_ms": elapsed, "message": msg}
        )
    else:
        steps.append(
            {
                "step": "polish",
                "status": "skipped",
                "elapsed_ms": 0,
                "message": "未启用",
            }
        )

    return {
        "success": True,
        "data": {
            "translation": translation,
            "papers": papers,
            "detect_report": detect_report["summary"] if detect_report else {},
            "polished_text": polished,
            "changes": changes,
            "steps": steps,
        },
    }


@app.post("/api/pipeline")
async def api_pipeline(req: PipelineRequest):
    return await asyncio.to_thread(_run_pipeline, req.text, req)


@app.post("/api/share")
async def api_share(req: ShareRequest):
    code = uuid.uuid4().hex[:8]
    _prune_share_store()
    _share_store[code] = {
        "text": req.text,
        "detect_report": req.detect_report,
        "polished": req.polished,
        "changes": req.changes,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_ts": time.time(),
    }
    return {"success": True, "data": {"sharecode": code, "url": f"/?sharecode={code}"}}


@app.get("/api/share/{code}")
async def api_get_share(code: str):
    _prune_share_store()
    data = _share_store.get(code)
    if not data:
        raise HTTPException(404, detail="分享不存在或已过期")
    # 内部字段 _ts 不外泄，返回前剥离
    return {"success": True, "data": {k: v for k, v in data.items() if k != "_ts"}}


@app.post("/api/agent/chat")
async def api_agent_chat(req: AgentRequest):
    """Agent 单轮对话入口。规则路由，无大模型，离线可跑。"""
    if not req.message.strip():
        return {
            "success": True,
            "data": {
                "reply": "请说点什么，或把论文段落贴给我。",
                "tool_calls": [],
                "results": {},
            },
        }
    result = await asyncio.to_thread(agent.chat, req.message, req.history, req.mode)
    return {"success": True, "data": result}


@app.post("/api/qa/chat")
async def api_qa_chat(req: QaChatRequest):
    """大模型兜底问答（SSE 流式）。未配置 DEEPSEEK_API_KEY 时返回 503。"""
    if not qa.is_available():
        raise HTTPException(
            503, detail="大模型问答未配置，请在 .env 设置 DEEPSEEK_API_KEY"
        )

    # 组装消息：system + 可选历史 + 当前问题
    system_content = qa.SYSTEM_PROMPT
    # 用户设置了称呼时，注入到 system prompt，让回复自然带上称呼
    name = (req.user_name or "").strip()
    if name:
        system_content += (
            f"\n\n用户已设置自己的称呼为「{name}」。"
            "回复时可在开头或合适位置自然称呼对方（如「{name}，…」），但不要每句都重复，"
            "也不要编造称呼。称呼只用于拉近对话感，不改变回答内容。"
        )
    # 用户自定义的补充提示词：追加到内置规则集之后，不覆盖核心能力
    custom = (req.custom_prompt or "").strip()
    if custom:
        system_content += (
            "\n\n【用户的补充要求】\n" + custom + "\n"
            "以上是用户自己写的补充要求。在不违背「去AI味」铁律和事实准确的前提下尽量满足；"
            "若与核心规则冲突，以核心规则为准。"
        )
    messages = [{"role": "system", "content": system_content}]
    if req.history:
        for h in req.history:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": h.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    def gen():
        try:
            for piece in qa.stream_chat(messages, model=req.model or ""):
                yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── mount frontend (must be last) ──
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


# ── entry ──

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=True)
