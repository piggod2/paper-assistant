"""
论文智助 — FastAPI 入口
所有接口：/api/health /api/rules /api/detect /api/polish /api/translate /api/search /api/pipeline /api/share
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

load_dotenv()

try:
    from . import detector, rewriter, translator, searcher, agent
    from .rules import get_rules, get_meta
except ImportError:
    import detector, rewriter, translator, searcher, agent
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
    return resp


# ── models ──

class TextRequest(BaseModel):
    text: str


class PolishRequest(BaseModel):
    text: str
    options: Optional[dict] = None


class SearchRequest(BaseModel):
    text: str
    limit: int = 5
    source: str = "auto"


class PipelineRequest(BaseModel):
    text: str
    run_translate: bool = True
    run_search: bool = True
    run_polish: bool = True
    limit: int = 5
    options: Optional[dict] = None


class ShareRequest(BaseModel):
    text: str
    detect_report: Optional[dict] = None
    polished: Optional[str] = None
    changes: Optional[list] = None


class AgentRequest(BaseModel):
    message: str
    history: Optional[list] = None


# ── in-memory share store ──

_share_store: dict[str, dict] = {}


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
            "pipeline": True
        }
    }


@app.get("/api/rules")
async def api_rules():
    """Return full polish-rules.json with attribution."""
    data = {
        "meta": get_meta(),
        "grades": {"A": "机械改", "B": "建议改", "C": "只报告", "F": "指纹", "X": "永不修改", "H": "人审区"},
        "rules": get_rules()
    }
    return data


@app.post("/api/detect")
async def api_detect(req: TextRequest):
    if not req.text.strip():
        return {"success": True, "data": {"hits": {}, "summary": {}, "metrics": {}}}
    report = detector.detect(req.text)
    return {"success": True, "data": report}


@app.post("/api/polish")
async def api_polish(req: PolishRequest):
    if not req.text.strip():
        return {"success": True, "data": {"polished": "", "original": "", "changes": [], "report": {}}}
    report = detector.detect(req.text)
    result = rewriter.rewrite(req.text, report, req.options)
    return {
        "success": True,
        "data": {
            "polished": result["polished"],
            "original": result["original"],
            "changes": result["changes"],
            "safety_failures": result["safety_failures"],
            "total_changes": result["total_changes"],
            "report": {
                "summary": report["summary"],
                "hits": report["hits"],
                "metrics": report["metrics"],
                "f_metrics": report["f_metrics"]
            }
        }
    }


@app.post("/api/translate")
async def api_translate(req: TextRequest):
    if not translator.is_available():
        raise HTTPException(503, detail="翻译未配置，请在 .env 设置 BAIDU_APPID / BAIDU_SECRET")
    result = await asyncio.to_thread(translator.translate, req.text)
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
        tr = translator.translate(text)
        elapsed = int((time.perf_counter() - t0) * 1000)
        if "error" not in tr:
            translation = tr.get("translated", "")
            steps.append({"step": "translate", "status": "ok", "elapsed_ms": elapsed, "message": f"翻译完成，{tr.get('segments',1)}段"})
        else:
            steps.append({"step": "translate", "status": "skipped", "elapsed_ms": elapsed, "message": tr.get("detail", "翻译失败")})
    else:
        steps.append({"step": "translate", "status": "skipped", "elapsed_ms": 0, "message": "翻译未配置或未启用"})

    # step 2: search
    text_for_search = translation or text
    if req.run_search:
        t0 = time.perf_counter()
        sr = searcher.search(text_for_search[:300], req.limit)
        elapsed = int((time.perf_counter() - t0) * 1000)
        papers = sr.get("results", [])
        source = sr.get("source_used", "none")
        steps.append({"step": "search", "status": "ok" if papers else "empty", "elapsed_ms": elapsed, "message": f"{source}：{len(papers)}篇"})
    else:
        steps.append({"step": "search", "status": "skipped", "elapsed_ms": 0, "message": "未启用"})

    # step 3: polish (core — always runs)
    if req.run_polish:
        t0 = time.perf_counter()
        text_for_polish = translation or text
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
        steps.append({"step": "polish", "status": "ok", "elapsed_ms": elapsed, "message": msg})
    else:
        steps.append({"step": "polish", "status": "skipped", "elapsed_ms": 0, "message": "未启用"})

    return {
        "success": True,
        "data": {
            "translation": translation,
            "papers": papers,
            "detect_report": detect_report["summary"] if detect_report else {},
            "polished_text": polished,
            "changes": changes,
            "steps": steps
        }
    }


@app.post("/api/pipeline")
async def api_pipeline(req: PipelineRequest):
    return await asyncio.to_thread(_run_pipeline, req.text, req)


@app.post("/api/share")
async def api_share(req: ShareRequest):
    code = uuid.uuid4().hex[:8]
    _share_store[code] = {
        "text": req.text,
        "detect_report": req.detect_report,
        "polished": req.polished,
        "changes": req.changes,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return {"success": True, "data": {"sharecode": code, "url": f"/?sharecode={code}"}}


@app.get("/api/share/{code}")
async def api_get_share(code: str):
    data = _share_store.get(code)
    if not data:
        raise HTTPException(404, detail="分享不存在或已过期")
    return {"success": True, "data": data}


@app.post("/api/agent/chat")
async def api_agent_chat(req: AgentRequest):
    """Agent 单轮对话入口。规则路由，无大模型，离线可跑。"""
    if not req.message.strip():
        return {"success": True, "data": {"reply": "请说点什么，或把论文段落贴给我。", "tool_calls": [], "results": {}}}
    result = await asyncio.to_thread(agent.chat, req.message, req.history)
    return {"success": True, "data": result}


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