import { api, CONFIG } from './useCore.js';

export function useActions(state) {
  const {
    text, report, polished, changes, safetyFailures, papers, translateResult,
    pipelineSteps, loading, errorMsg, shareBanner, shareCode, intensity, userName, showToast,
    searchLimit, savedPapers, history,
  } = state;

  async function doDetect() {
    loading.value = 'detect'; errorMsg.value = ''; report.value = null; polished.value = ''; changes.value = []; safetyFailures.value = [];
    try {
      const r = await api('/api/detect', { method: 'POST', body: JSON.stringify({ text: text.value }) });
      if (r.success) {
        report.value = r.data;
        pushHistory({ type: 'detect', text: text.value, polished: '', at: Date.now() });
      }
      else errorMsg.value = r.detail || '检测失败';
    } catch (e) { errorMsg.value = '后端未响应，请确认 python backend/server.py 已启动'; }
    loading.value = '';
  }

  async function doPolish() {
    loading.value = 'polish'; errorMsg.value = ''; report.value = null; polished.value = ''; changes.value = []; safetyFailures.value = [];
    try {
      const opts = { intensity: intensity.value };
      const r = await api('/api/polish', { method: 'POST', body: JSON.stringify({ text: text.value, options: opts }) });
      if (r.success) {
        report.value = r.data.report;
        polished.value = r.data.polished;
        changes.value = r.data.changes;
        safetyFailures.value = r.data.safety_failures || [];
        pushHistory({ type: 'polish', text: text.value, polished: r.data.polished, at: Date.now() });
      } else errorMsg.value = r.detail || '润色失败';
    } catch (e) { errorMsg.value = '后端未响应，请确认 python backend/server.py 已启动'; }
    loading.value = '';
  }

  async function doPipeline() {
    loading.value = 'pipeline'; errorMsg.value = ''; report.value = null; polished.value = ''; changes.value = []; papers.value = []; translateResult.value = null; pipelineSteps.value = [];
    try {
      const r = await api('/api/pipeline', { method: 'POST', body: JSON.stringify({ text: text.value, options: { intensity: intensity.value } }) });
      if (r.success) {
        pipelineSteps.value = r.data.steps;
        if (r.data.translation) translateResult.value = { translated: r.data.translation, segments: 0, elapsed_ms: 0 };
        papers.value = r.data.papers || [];
        report.value = { summary: r.data.detect_report, hits: {} };
        polished.value = r.data.polished_text;
        changes.value = r.data.changes || [];
      } else errorMsg.value = r.detail || '流水线失败';
    } catch (e) { errorMsg.value = '后端未响应'; }
    loading.value = '';
  }

  async function doTranslateOnly() {
    loading.value = 'translate'; errorMsg.value = '';
    try {
      const r = await api('/api/translate', { method: 'POST', body: JSON.stringify({ text: text.value }) });
      if (r.success) translateResult.value = r.data;
      else errorMsg.value = r.detail || '翻译失败';
    } catch (e) { errorMsg.value = '翻译服务不可用'; }
    loading.value = '';
  }

  async function doSearchOnly() {
    loading.value = 'search'; errorMsg.value = '';
    try {
      const r = await api('/api/search', { method: 'POST', body: JSON.stringify({ text: text.value, limit: searchLimit.value }) });
      if (r.success) papers.value = r.data.results || [];
      else errorMsg.value = r.detail || '检索失败';
    } catch (e) { errorMsg.value = '检索服务不可用'; }
    loading.value = '';
  }

  async function doShare() {
    try {
      const body = { text: text.value };
      if (report.value) body.detect_report = report.value;
      if (polished.value) { body.polished = polished.value; body.changes = changes.value }
      const r = await api('/api/share', { method: 'POST', body: JSON.stringify(body) });
      if (r.success) {
        const url = `${CONFIG.SHARE_URL_BASE}/?sharecode=${r.data.sharecode}`;
        shareBanner.value = `分享链接已生成：${url}`;
        try { navigator.clipboard.writeText(url); showToast('链接已复制') } catch (e) { }
      }
    } catch (e) {
      const payload = { text: text.value, polished: polished.value, from: userName.value, date: new Date().toLocaleDateString() };
      const b64 = (() => {
        const bytes = new TextEncoder().encode(JSON.stringify(payload));
        return btoa(Array.from(bytes, b => String.fromCharCode(b)).join(''));
      })().replace(/\+/g, '-').replace(/\//g, '_');
      const url = `${location.origin}${location.pathname}?s=${b64}`;
      shareBanner.value = `离线分享链接：${url}`;
      try { navigator.clipboard.writeText(url); showToast('离线链接已复制') } catch (e) { }
    }
  }

  async function fetchShare() {
    try {
      const r = await api('/api/share/' + shareCode.value);
      if (r.success) {
        const d = r.data;
        text.value = d.text || '';
        polished.value = d.polished || '';
        report.value = d.detect_report || null;
        shareBanner.value = `分享的检测结果 · ${d.created_at}`;
      }
    } catch (e) { }
  }

  function quickPolish() { doPolish() }

  // ── 收藏文献 ──
  function toggleSavePaper(paper) {
    if (!paper) return;
    const id = paper.paper_id || paper.url || paper.title;
    const idx = savedPapers.value.findIndex(p => (p.paper_id || p.url || p.title) === id);
    if (idx >= 0) {
      savedPapers.value.splice(idx, 1);
      showToast('已取消收藏');
    } else {
      // 存轻量字段，避免摘要撑爆 localStorage
      savedPapers.value.unshift({
        paper_id: paper.paper_id,
        title: paper.title,
        authors: paper.authors || [],
        year: paper.year,
        venue: paper.venue,
        citations: paper.citations,
        url: paper.url,
        open_access_pdf: paper.open_access_pdf,
        saved_at: Date.now(),
      });
      showToast('已收藏');
    }
  }
  function isPaperSaved(paper) {
    if (!paper) return false;
    const id = paper.paper_id || paper.url || paper.title;
    return savedPapers.value.some(p => (p.paper_id || p.url || p.title) === id);
  }
  function removeSavedPaper(id) {
    const idx = savedPapers.value.findIndex(p => (p.paper_id || p.url || p.title) === id);
    if (idx >= 0) savedPapers.value.splice(idx, 1);
  }

  // ── 历史记录 ──
  // 自增序号：保证同一毫秒内写入多条时 id 仍唯一（Date.now() 同毫秒会撞 key）
  let historySeq = 0;
  function pushHistory(entry) {
    historySeq += 1;
    entry.id = entry.at + '-' + historySeq;
    history.value.unshift(entry);
    if (history.value.length > 30) history.value.length = 30; // 最多保留 30 条，防撑爆
  }
  function removeHistory(idx) {
    history.value.splice(idx, 1);
  }
  function clearHistory() {
    history.value = [];
  }
  function loadHistory(entry) {
    if (!entry) return;
    text.value = entry.text || '';
    polished.value = entry.polished || '';
    report.value = null;
    changes.value = [];
    safetyFailures.value = [];
    showToast('已载入历史记录');
  }

  function quickUndo() {
    if (polished.value && confirm('恢复原文并清除检测结果？')) {
      polished.value = ''; changes.value = []; report.value = null; safetyFailures.value = [];
    }
  }

  function handleDrop(e) {
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { showToast('文件过大（限 10MB）'); return }
    const reader = new FileReader();
    reader.onload = ev => { text.value = ev.target.result; showToast('文件已加载 · ' + file.name) };
    reader.readAsText(file);
  }

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { showToast('文件过大（限 10MB）'); return }
    const reader = new FileReader();
    reader.onload = ev => { text.value = ev.target.result; showToast('文件已加载 · ' + file.name) };
    reader.readAsText(file); e.target.value = '';
  }

  return {
    doDetect, doPolish, doPipeline, doTranslateOnly, doSearchOnly, doShare,
    fetchShare, quickPolish, quickUndo, handleDrop, handleFileSelect,
    toggleSavePaper, isPaperSaved, removeSavedPaper,
    pushHistory, removeHistory, clearHistory, loadHistory,
  };
}
