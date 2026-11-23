"""
Paper search — Semantic Scholar primary, arXiv fallback.
Zero dependency when both sources are unavailable.
"""

import hashlib
import logging
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

import requests

logger = logging.getLogger(__name__)

S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_URL = "http://export.arxiv.org/api/query"

STOPWORDS_EN = {"the", "of", "and", "a", "an", "in", "to", "for", "on", "with", "is", "are", "was", "were", "by", "from", "this", "that", "these", "those", "be", "has", "have", "it", "as", "or", "at", "not", "but", "we", "our", "their"}
STOPWORDS_ZH = {
    "基于", "本文", "研究", "一个", "一种", "这个", "这种", "方面", "通过", "进行", "使用",
    "以及", "及其", "提出", "方法", "结果", "分析", "模型", "领域", "主导", "架构", "采用",
    "机制", "并行", "捕捉", "关系", "克服", "限制", "已经", "成为", "能够", "有效", "实现",
    "为了", "对于", "同时", "并且", "但是", "因此", "所以", "从而", "以及", "主要", "相关",
    "问题", "系统", "功能", "设计", "工具", "辅助", "场景", "价值", "提升", "显著", "深度",
    "论文", "摘要", "关键词", "引言", "结论", "实验", "数据", "处理", "自然", "语言", "语言",
}

# 学术领域高频词，直接保留作为检索锚点（中文→英文映射）
# 覆盖计算机/AI/金融/医学/生物/物理/化学/材料等常见论文主题
DOMAIN_TERMS = {
    # AI / 机器学习
    "transformer": "transformer",
    "注意力机制": "attention mechanism",
    "自注意力": "self-attention",
    "自然语言处理": "natural language processing",
    "机器学习": "machine learning",
    "深度学习": "deep learning",
    "神经网络": "neural network",
    "预训练": "pre-training",
    "大语言模型": "large language model",
    "词元": "token",
    "知识图谱": "knowledge graph",
    "强化学习": "reinforcement learning",
    "计算机视觉": "computer vision",
    "图像识别": "image recognition",
    "语音识别": "speech recognition",
    "情感分析": "sentiment analysis",
    "文本分类": "text classification",
    "机器翻译": "machine translation",
    "问答系统": "question answering",
    "信息检索": "information retrieval",
    "推荐系统": "recommender system",
    "生成对抗网络": "generative adversarial network",
    "扩散模型": "diffusion model",
    "图神经网络": "graph neural network",
    "联邦学习": "federated learning",
    "迁移学习": "transfer learning",
    "零样本": "zero-shot",
    "少样本": "few-shot",
    "提示学习": "prompt learning",
    "语义理解": "semantic understanding",
    # 通用 AI 概念
    "人工智能": "artificial intelligence",
    "智能体": "agent",
    "多智能体": "multi-agent",
    "卷积神经网络": "convolutional neural network",
    "循环神经网络": "recurrent neural network",
    "长短期记忆": "long short-term memory",
    "词向量": "word embedding",
    "嵌入": "embedding",
    "微调": "fine-tuning",
    "检索增强": "retrieval-augmented generation",
    "推理": "reasoning",
    "对齐": "alignment",
    # 计算机 / 软件
    "区块链": "blockchain",
    "云计算": "cloud computing",
    "边缘计算": "edge computing",
    "物联网": "internet of things",
    "大数据": "big data",
    "数据挖掘": "data mining",
    "隐私保护": "privacy preserving",
    "联邦学习": "federated learning",
    "网络安全": "cybersecurity",
    "密码学": "cryptography",
    "计算机视觉": "computer vision",
    "目标检测": "object detection",
    "图像分割": "image segmentation",
    "语义分割": "semantic segmentation",
    "自动驾驶": "autonomous driving",
    "机器人": "robotics",
    "无人机": "unmanned aerial vehicle",
    # 金融 / 经济
    "金融": "finance",
    "风险预测": "risk prediction",
    "股价预测": "stock prediction",
    "量化交易": "quantitative trading",
    "投资组合": "portfolio",
    "信用评分": "credit scoring",
    "时间序列": "time series",
    "预测": "forecasting",
    # 医学 / 生物
    "医学图像": "medical imaging",
    "医学影像": "medical imaging",
    "疾病诊断": "disease diagnosis",
    "癌症": "cancer",
    "肿瘤": "tumor",
    "药物发现": "drug discovery",
    "蛋白质": "protein",
    "基因": "gene",
    "基因组": "genome",
    "生物信息学": "bioinformatics",
    "脑机接口": "brain-computer interface",
    "医疗": "healthcare",
    # 物理 / 化学 / 材料
    "量子计算": "quantum computing",
    "量子": "quantum",
    "材料": "materials",
    "纳米": "nanomaterial",
    "催化": "catalysis",
    "电池": "battery",
    "能源": "energy",
    "太阳能": "solar energy",
    # 其他常见
    "优化": "optimization",
    "算法": "algorithm",
    "模型": "model",
    "仿真": "simulation",
    "控制": "control",
    "信号处理": "signal processing",
    "图像处理": "image processing",
    # ===== 计算机学科（计科类重点补充）=====
    # 系统 / 架构
    "操作系统": "operating system",
    "分布式系统": "distributed system",
    "分布式计算": "distributed computing",
    "并行计算": "parallel computing",
    "高性能计算": "high performance computing",
    "计算机体系结构": "computer architecture",
    "芯片": "chip",
    "处理器": "processor",
    "存储": "storage",
    "内存": "memory",
    "缓存": "cache",
    "调度": "scheduling",
    "虚拟化": "virtualization",
    "容器": "container",
    "微服务": "microservice",
    "内核": "kernel",
    "编译器": "compiler",
    "编译优化": "compiler optimization",
    "程序语言": "programming language",
    "编程语言": "programming language",
    "静态分析": "static analysis",
    "形式化验证": "formal verification",
    "类型系统": "type system",
    # 网络
    "计算机网络": "computer network",
    "网络协议": "network protocol",
    "路由": "routing",
    "拥塞控制": "congestion control",
    "软件定义网络": "software-defined networking",
    "网络功能虚拟化": "network function virtualization",
    "5G": "5G",
    "无线网络": "wireless network",
    "移动边缘计算": "mobile edge computing",
    "分布式缓存": "distributed cache",
    # 数据库 / 数据
    "数据库": "database",
    "分布式数据库": "distributed database",
    "查询优化": "query optimization",
    "事务": "transaction",
    "索引": "index",
    "键值存储": "key-value store",
    "图数据库": "graph database",
    "向量数据库": "vector database",
    "数据仓库": "data warehouse",
    "流处理": "stream processing",
    "数据清洗": "data cleaning",
    "数据集成": "data integration",
    # 软件工程
    "软件工程": "software engineering",
    "软件测试": "software testing",
    "代码生成": "code generation",
    "程序分析": "program analysis",
    "缺陷预测": "bug prediction",
    "代码修复": "program repair",
    "重构": "refactoring",
    "持续集成": "continuous integration",
    "软件开发": "software development",
    "需求工程": "requirements engineering",
    # 安全 / 隐私
    "安全": "security",
    "入侵检测": "intrusion detection",
    "恶意软件": "malware",
    "漏洞": "vulnerability",
    "差分隐私": "differential privacy",
    "同态加密": "homomorphic encryption",
    "安全多方计算": "secure multi-party computation",
    "可信执行环境": "trusted execution environment",
    "认证": "authentication",
    "访问控制": "access control",
    # 算法 / 理论
    "数据结构": "data structure",
    "图论": "graph theory",
    "组合优化": "combinatorial optimization",
    "近似算法": "approximation algorithm",
    "在线算法": "online algorithm",
    "复杂度": "complexity",
    "计算理论": "theory of computation",
    "密码协议": "cryptographic protocol",
    "随机算法": "randomized algorithm",
    "哈希": "hash",
    "排序": "sorting",
    "搜索算法": "search algorithm",
    "动态规划": "dynamic programming",
    "贪心算法": "greedy algorithm",
    # 应用方向
    "推荐算法": "recommendation algorithm",
    "搜索引擎": "search engine",
    "知识表示": "knowledge representation",
    "对话系统": "dialogue system",
    "多模态": "multimodal",
    "生成模型": "generative model",
    "对比学习": "contrastive learning",
    "自监督学习": "self-supervised learning",
    "元学习": "meta-learning",
    "因果推断": "causal inference",
    "可解释性": "explainability",
    "模型压缩": "model compression",
    "知识蒸馏": "knowledge distillation",
    "剪枝": "pruning",
    "量化": "quantization",
    "分布式训练": "distributed training",
    "推理加速": "inference acceleration",
    # 人机交互 / 其他
    "人机交互": "human-computer interaction",
    "推荐": "recommendation",
    "虚拟现实": "virtual reality",
    "增强现实": "augmented reality",
    "数字孪生": "digital twin",
    "联邦": "federation",
    "集群": "cluster",
    "负载均衡": "load balancing",
    "故障恢复": "fault tolerance",
    "容错": "fault-tolerant",
    "一致性": "consistency",
    "共识算法": "consensus algorithm",
    "图计算": "graph computing",
    "大数据处理": "big data processing",
    "数据可视化": "data visualization",
}

X_BLACKLIST = {"赋能", "闭环", "抓手", "打法", "颗粒度", "底层逻辑", "对齐", "拉通", "倒逼"}

# in-memory cache
_cache: dict[str, tuple[float, dict]] = {}
_last_request = 0.0
_request_interval = 1.0  # seconds


def is_available() -> bool:
    return True  # arXiv always available


def has_s2_key() -> bool:
    return bool(os.getenv("SEMANTIC_SCHOLAR_KEY"))


def search(text: str, limit: int = 5, source: str = "auto") -> dict:
    """
    Search for papers related to text.
    Returns {keywords, source_used, elapsed_ms, results}.
    """
    global _last_request

    t0 = time.perf_counter()

    # check cache
    cache_key = _cache_key(text, limit)
    if cache_key in _cache:
        ts, cached = _cache[cache_key]
        if time.time() - ts < 3600:
            cached["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
            return cached

    # extract keywords
    keywords = _extract_keywords(text)
    if not keywords:
        return _empty_result(keywords, int((time.perf_counter() - t0) * 1000))

    # rate limit
    elapsed = time.time() - _last_request
    if elapsed < _request_interval:
        time.sleep(_request_interval - elapsed)

    # try S2 first — ONLY when a key is configured; unauthenticated S2 is rate-limited
    # to the point of near-uselessness (429 on almost every call), so skip it entirely
    # without a key and go straight to arXiv (stable, no auth).
    if source in ("auto", "s2") and has_s2_key():
        result = _search_s2(keywords, limit)
        if result and result.get("results"):
            _last_request = time.time()
            result["source_used"] = "Semantic Scholar"
            result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
            result["keywords"] = keywords
            _cache[cache_key] = (time.time(), result)
            return result

    # fallback to arXiv
    _last_request = time.time()
    try:
        result = _search_arxiv(keywords, limit)
        result["source_used"] = "arXiv"
    except Exception as e:
        logger.warning(f"arXiv search failed: {e}")
        result = _empty_result(keywords, 0)
        result["source_used"] = "none"

    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    result["keywords"] = keywords
    if result.get("results"):
        _cache[cache_key] = (time.time(), result)
    return result


def _cache_key(text: str, limit: int) -> str:
    return hashlib.md5(f"{text}|{limit}".encode()).hexdigest()


def _extract_keywords(text: str) -> list[str]:
    """Extract English keywords for arXiv/S2 search.

    Priority: ① domain terms (中英对照表) → ② English TF-IDF → ③ Chinese→English translation.
    """
    keywords: list[str] = []

    # ① 领域词表直接命中（中文输入也先扫一遍，这是最准的锚点）
    lower_text = text.lower()
    for zh_term, en_term in DOMAIN_TERMS.items():
        if zh_term.lower() in lower_text:
            keywords.append(en_term)

    # ② 英文 TF-IDF（对英文输入有效）
    en_kws = _extract_en_keywords(text)
    for kw in en_kws:
        if kw not in keywords:
            keywords.append(kw)

    # ③ 中文输入 → 英译兜底
    has_zh = bool(re.search(r"[一-鿿]", text))
    if has_zh and not keywords:
        keywords = _translate_zh_keywords(text)

    # 去重保序，最多 5 个
    seen = set()
    out = []
    for kw in keywords:
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(kw)
        if len(out) >= 5:
            break
    return out


def _translate_zh_keywords(text: str) -> list[str]:
    """Fallback: translate Chinese keywords via Baidu API when no domain term matched.

    先按标点/空格切成短语，再用滑窗提取 2-4 字的中文词，过滤停用词后取高频词英译。
    """
    # 先按标点切分，避免把整句当成一个长串
    segments = re.split(r"[，。；、：！？\s,.!?;:]+", text)
    segments = [s.strip() for s in segments if s.strip()]

    # 对每个片段做滑窗提取中文词（2-4 字）
    candidates = []
    for seg in segments:
        # 只保留连续中文
        zh_chunks = re.findall(r"[一-鿿]{2,}", seg)
        for chunk in zh_chunks:
            # 滑窗 2-4 字
            for width in (4, 3, 2):
                for i in range(len(chunk) - width + 1):
                    candidates.append(chunk[i:i + width])

    # 过滤停用词和纯函数词
    filtered = []
    for w in candidates:
        if w in STOPWORDS_ZH or w in X_BLACKLIST:
            continue
        # 过滤掉明显是虚词/助词的组合（含"了/的/是/在/和/与/对"等）
        if any(c in w for c in "的了是在和与对就都也很被把从向到于"):
            continue
        filtered.append(w)

    # 按出现次数 + 长度粗排，取 top4
    counter = {}
    for w in filtered:
        counter[w] = counter.get(w, 0) + 1
    # 长度优先（更长的词更可能是专业术语），其次频率
    top = [w for w, _ in sorted(counter.items(), key=lambda x: (-len(x[0]), -x[1]))[:4]]
    if not top:
        return []

    # 尝试用百度翻译英译
    try:
        from translator import translate  # 复用翻译模块
        translated = []
        for w in top:
            r = translate(w, "zh", "en")
            if r and r.get("translated"):
                t = r["translated"].strip()
                # 过滤掉翻译后仍是中文或明显无意义的
                if t and not re.search(r"[一-鿿]", t):
                    translated.append(t)
        return [t for t in translated if t][:3]
    except Exception:
        return top[:3]  # 翻译失败就用中文原文兜底



def _extract_en_keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    # remove stopwords + X-level blacklist
    filtered = [w for w in words if w not in STOPWORDS_EN and w.lower() not in {x.lower() for x in X_BLACKLIST}]
    # TF
    tf = {}
    for w in filtered:
        tf[w] = tf.get(w, 0) + 1
    total = max(sum(tf.values()), 1)
    # prefer longer words (IDF-like)
    scored = [(w, (c / total) * (1 + math.log(len(w)))) for w, c in tf.items()]
    scored.sort(key=lambda x: -x[1])
    return [w for w, _ in scored[:5]]


def _extract_zh_keywords(text: str) -> list[str]:
    """Extract Chinese keywords — simpler approach."""
    candidates = re.findall(r"[一-鿿]{2,6}", text)
    filtered = [w for w in candidates if w not in STOPWORDS_ZH and w not in X_BLACKLIST]
    counter = {}
    for w in filtered:
        counter[w] = counter.get(w, 0) + 1
    sorted_w = sorted(counter.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_w[:5]]


def _search_s2(keywords: list[str], limit: int) -> dict | None:
    """Search Semantic Scholar."""
    key = os.getenv("SEMANTIC_SCHOLAR_KEY", "")
    query = " ".join(keywords)
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,authors,year,citationCount,url,openAccessPdf,externalIds"
    }
    headers = {"x-api-key": key} if key else {}
    for attempt in range(3):
        try:
            resp = requests.get(S2_URL, params=params, headers=headers, timeout=8)
            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return None
            data = resp.json()
            papers = data.get("data", [])
            max_cite = max((p.get("citationCount", 0) for p in papers), default=1)
            return {
                "results": [_format_s2_paper(p, max_cite, keywords) for p in papers]
            }
        except Exception:
            return None
    return None


def _format_s2_paper(paper: dict, max_cite: int, keywords: list[str]) -> dict:
    title = paper.get("title", "")
    abstract = paper.get("abstract", "") or ""
    authors = [a.get("name", "") for a in paper.get("authors", [])]
    year = paper.get("year", 0)
    citations = paper.get("citationCount", 0)
    url = paper.get("url", "")
    pdf = paper.get("openAccessPdf", {}).get("url", "") if paper.get("openAccessPdf") else ""
    venue = paper.get("venue", "")

    # scoring
    kw_coverage = sum(1 for kw in keywords if kw.lower() in (title + abstract).lower()) / max(len(keywords), 1)
    title_hit = sum(1 for kw in keywords if kw.lower() in title.lower())
    title_score = title_hit / max(len(keywords), 1) if title_hit else 0.1 * sum(1 for kw in keywords if kw.lower() in abstract.lower()) / max(len(keywords), 1)
    cite_score = math.log(1 + citations) / math.log(1 + max_cite) if max_cite > 0 else 0
    year_score = min(max((year - 2015) / 11, 0), 1) if year else 0.5
    score = round(0.40 * kw_coverage + 0.25 * title_score + 0.20 * cite_score + 0.15 * year_score, 2)

    # relevance reason
    if title_hit >= 2 and citations > 100:
        reason = f"标题命中关键词{','.join(keywords[:3])}，被引{citations}次"
    elif title_hit >= 1:
        reason = f"与查询中「{keywords[0] if keywords else '关键词'}」直接相关"
        if year:
            reason += f"，{year}年发表"
    elif citations > 100:
        reason = f"高被引经典（{citations}+），适合做相关工作综述"
    else:
        reason = f"摘要与查询关键词部分匹配"

    return {
        "paper_id": paper.get("paperId", ""),
        "title": title,
        "abstract": abstract[:300],
        "authors": authors[:5],
        "year": year,
        "venue": venue or "—",
        "citations": citations,
        "url": url,
        "open_access_pdf": pdf,
        "score": score,
        "relevance_reason": reason
    }


def _search_arxiv(keywords: list[str], limit: int) -> dict:
    """Search arXiv API (no auth required). Uses ElementTree for robust XML parsing."""
    query = " AND ".join(f'all:"{kw}"' for kw in keywords[:3])
    params = {
        "search_query": query,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    url = f"{ARXIV_URL}?{urlencode(params)}"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return _empty_result(keywords, 0)

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results = []
    try:
        root = ET.fromstring(resp.text)
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").strip()
            summary = (entry.findtext("atom:summary", "", ns) or "")[:300]
            authors = [
                (a.findtext("atom:name", "", ns) or "").strip()
                for a in entry.findall("atom:author", ns)
            ]
            published = entry.findtext("atom:published", "", ns) or ""
            year_m = re.search(r"(\d{4})", published)
            year = int(year_m.group(1)) if year_m else 0

            link = ""
            for l in entry.findall("atom:link", ns):
                href = l.get("href", "")
                if "arxiv.org" in href and "/abs/" in href:
                    link = href
                    break
            pdf = link.replace("/abs/", "/pdf/") + ".pdf" if "/abs/" in link else ""

            score = round(
                0.7 * (sum(1 for kw in keywords if kw.lower() in (title + summary).lower()) / max(len(keywords), 1))
                + 0.3 * min(max((year - 2015) / 11, 0), 1),
                2
            )

            entry_id = entry.findtext("atom:id", "", ns) or ""
            paper_id = entry_id.split("/")[-1] if entry_id else hashlib.md5(title.encode()).hexdigest()[:8]

            results.append({
                "paper_id": paper_id,
                "title": title,
                "abstract": summary.strip()[:300],
                "authors": authors[:5],
                "year": year,
                "venue": "arXiv",
                "citations": 0,
                "url": link,
                "open_access_pdf": pdf,
                "score": score,
                "relevance_reason": (
                    "arXiv预印本，标题匹配关键词"
                    if any(kw.lower() in title.lower() for kw in keywords)
                    else "arXiv预印本"
                )
            })
    except ET.ParseError:
        return _empty_result(keywords, 0)

    return {"results": results[:limit]}


def _empty_result(keywords: list[str], elapsed_ms: int) -> dict:
    return {"keywords": keywords, "source_used": "none", "elapsed_ms": elapsed_ms, "results": []}