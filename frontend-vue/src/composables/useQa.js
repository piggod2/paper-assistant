import { ref, nextTick } from 'vue';
import { CONFIG } from './useCore.js';

export function useQa(state) {
  const qaOpen = ref(false);
  const qaMessages = ref([]);
  const qaInput = ref('');
  const qaLoading = ref(false);
  const qaChatBox = ref(null);
  const qaPanel = ref(null);
  const resizing = ref(false);
  const qaModel = ref('deepseek-v4-flash'); // 可选模型，前端可切换
  const qaModels = [
    { id: 'deepseek-v4-flash', label: '快速（Flash）' },
    { id: 'deepseek-v4-pro', label: '深度（Pro）' },
  ];
  // 问答模式：auto=自动识别 | chat=自由问答 | polish=强制润色 | detect=强制检测
  const qaMode = ref('auto');
  const qaModes = [
    { id: 'auto', label: '自动' },
    { id: 'chat', label: '自由问答' },
    { id: 'polish', label: '润色' },
    { id: 'detect', label: '检测' },
  ];

  // 语义精判（源库语义层 12/13：结论提示冒号、高度同构三连）
  const judgeResults = ref([]);   // [{task, verdict, suggestions, reason}]
  const judgeLoading = ref(false);
  const judgeError = ref('');
  let resizeStartY = 0;
  let resizeStartH = 0;

  function toggleQa() {
    qaOpen.value = !qaOpen.value;
  }

  function qaScrollBottom() {
    nextTick(() => {
      if (qaChatBox.value) qaChatBox.value.scrollTop = qaChatBox.value.scrollHeight;
    });
  }

  // 语义精判：对当前正文跑两条语义层判读，只出建议、不改写
  async function runJudge(text) {
    const t = (text || '').trim();
    if (!t) return;
    judgeLoading.value = true;
    judgeError.value = '';
    judgeResults.value = [];
    const tasks = [
      { id: 'conclusion_colon', label: '结论提示冒号（规则12）' },
      { id: 'isomorphic_triple', label: '高度同构三连（规则13）' },
    ];
    try {
      for (const task of tasks) {
        const resp = await fetch(CONFIG.API_BASE + '/api/judge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: t, task: task.id }),
        });
        const json = await resp.json();
        const d = json.data || {};
        judgeResults.value.push({
          task: task.id,
          label: task.label,
          ok: d.ok,
          verdict: d.verdict || '',
          suggestions: d.suggestions || [],
          reason: d.reason || '',
          error: d.error || '',
        });
      }
    } catch (e) {
      judgeError.value = '语义精判失败，请确认后端已启动且已配置 DEEPSEEK_API_KEY。';
    } finally {
      judgeLoading.value = false;
    }
  }

  function startResize(e) {
    resizeStartY = e.clientY;
    resizeStartH = qaPanel.value ? qaPanel.value.offsetHeight : 420;
    resizing.value = true;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ns-resize';
  }

  function onResizeMove(e) {
    if (!resizing.value) return;
    const dy = e.clientY - resizeStartY;
    let h = resizeStartH + dy;
    h = Math.max(140, Math.min(h, window.innerHeight * 0.9));
    if (qaPanel.value) qaPanel.value.style.height = h + 'px';
  }

  function endResize() {
    if (!resizing.value) return;
    resizing.value = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    // 拖拽结束把高度写回数据态，避免下次拖拽以旧 offsetHeight 为基准
    if (qaPanel.value) {
      const h = qaPanel.value.offsetHeight;
      qaPanel.value.style.height = Math.max(140, h) + 'px';
    }
  }

  function onTouchMove(e) {
    if (!resizing.value) return;
    e.preventDefault();
    const t = e.touches[0];
    const dy = t.clientY - resizeStartY;
    let h = resizeStartH + dy;
    h = Math.max(140, Math.min(h, window.innerHeight * 0.9));
    if (qaPanel.value) qaPanel.value.style.height = h + 'px';
  }

  function bindResize() {
    window.addEventListener('mousemove', onResizeMove);
    window.addEventListener('mouseup', endResize);
    window.addEventListener('touchmove', onTouchMove, { passive: false });
    window.addEventListener('touchend', endResize);
  }

  function unbindResize() {
    window.removeEventListener('mousemove', onResizeMove);
    window.removeEventListener('mouseup', endResize);
    window.removeEventListener('touchmove', onTouchMove);
    window.removeEventListener('touchend', endResize);
  }

  // 流式读取后端 /api/qa/chat 的 SSE 响应，逐段追加到 msg.text
  async function streamLlm(t, msg) {
    const resp = await fetch(CONFIG.API_BASE + '/api/qa/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: t, history: [], model: qaModel.value, user_name: state.userName.value || '', custom_prompt: state.customPrompt.value || '' }),
    });
    if (!resp.ok) {
      if (resp.status === 503) {
        msg.text = '（大模型问答未配置：请在 .env 里填入 DEEPSEEK_API_KEY 后重启后端。当前仅支持规则问答。）';
      } else {
        msg.text = `（大模型调用失败：HTTP ${resp.status}）`;
      }
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // 按行解析 SSE
      const lines = buf.split('\n');
      buf = lines.pop(); // 保留不完整的最后一行
      for (const line of lines) {
        const s = line.trim();
        if (!s.startsWith('data:')) continue;
        const payload = s.slice(5).trim();
        if (payload === '[DONE]') continue;
        try {
          const obj = JSON.parse(payload);
          if (obj.delta) {
            msg.text += obj.delta;
            qaScrollBottom();
          } else if (obj.error) {
            msg.text += `\n（出错了：${obj.error}）`;
          }
        } catch (e) { /* 忽略解析失败的片段 */ }
      }
    }
  }

  async function qaSend() {
    const t = qaInput.value.trim();
    if (!t || qaLoading.value) return;
    qaMessages.value.push({ role: 'user', text: t });
    qaInput.value = '';
    qaLoading.value = true;
    qaScrollBottom();
    try {
      const resp = await fetch(CONFIG.API_BASE + '/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: t, history: [], mode: qaMode.value })
      });
      const json = await resp.json();
      const data = json.data || {};
      if (data.fallback) {
        const msg = { role: 'assistant', text: '', tools: [] };
        qaMessages.value.push(msg);
        try {
          await streamLlm(t, msg);
        } catch (e) {
          if (!msg.text.trim()) msg.text = '（大模型调用失败，请稍后重试。）';
        }
        if (!msg.text.trim()) {
          msg.text = '（没有可用的大模型回答。当前仅规则引擎可用，可试试「帮我润色」「找相关文献」这类指令。）';
        }
      } else {
        qaMessages.value.push({
          role: 'assistant',
          text: data.reply || '（无回复）',
          tools: data.tool_calls || []
        });
      }
    } catch (err) {
      qaMessages.value.push({ role: 'assistant', text: '后端未连接，请确认服务已启动。' });
    } finally {
      qaLoading.value = false;
      qaScrollBottom();
    }
  }

  return {
    qaOpen, qaMessages, qaInput, qaLoading, qaChatBox, qaPanel, resizing,
    qaModel, qaModels, qaMode, qaModes,
    judgeResults, judgeLoading, judgeError, runJudge,
    qaSend, toggleQa, startResize, bindResize, unbindResize,
  };
}
