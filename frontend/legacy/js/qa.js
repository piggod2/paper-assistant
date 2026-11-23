PA.useQa = function () {
    const { ref, nextTick } = Vue;

    let qaCloud = null;
    let qaLlmModel = null;
    try {
        if (window.WorkBuddyCloud && PA.CONFIG.CLOUD_ENDPOINT && PA.CONFIG.CLOUD_PUBLISHABLE_KEY) {
            qaCloud = WorkBuddyCloud.createWorkBuddyCloud({
                endpoint: PA.CONFIG.CLOUD_ENDPOINT,
                oauthRelayBaseUrl: PA.CONFIG.CLOUD_OAUTH_RELAY,
                publishableKey: PA.CONFIG.CLOUD_PUBLISHABLE_KEY,
            });
        }
    } catch (e) {
        qaCloud = null;
    }

    const QA_SYSTEM_PROMPT = [
        '你是「论文智助」的智能问答助手，服务于写论文的学生。',
        '职责两类：1) 回答工具使用问题（检测AI味/润色/中英翻译/找文献）；2) 给学术写作建议。',
        '工具背景：检测/润色基于结构化规则集，只改有实证支撑的AI味信号；「首先」「这意味着」等经复测被标为永不修改（X级），是有意为之。翻译走百度，检索走arXiv。',
        '要求：中文、简洁、像靠谱学长；不编造；给可执行步骤；控制在300字内。',
    ].join('\n');

    async function qaPickModel() {
        if (!qaCloud || qaLlmModel) return qaLlmModel;
        try {
            const models = await qaCloud.llm.models.list();
            const m = models.find((x) => x.disabled !== true) || models[0];
            qaLlmModel = m ? m.id : null;
        } catch (e) {
            qaLlmModel = null;
        }
        return qaLlmModel;
    }

    async function* qaAskLLM(prompt) {
        const model = await qaPickModel();
        if (!qaCloud || !model) {
            yield '';
            return;
        }
        const controller = new AbortController();
        try {
            const stream = qaCloud.llm.chat.completions.create({
                model,
                messages: [
                    { role: 'system', content: QA_SYSTEM_PROMPT },
                    { role: 'user', content: prompt },
                ],
                stream: true,
                signal: controller.signal,
            });
            for await (const chunk of stream) {
                const delta = chunk.choices && chunk.choices[0] && chunk.choices[0].delta;
                if (delta && delta.content) yield delta.content;
            }
        } catch (e) {
            yield '';
        }
    }

    const qaOpen = ref(false);
    const qaMessages = ref([]);
    const qaInput = ref('');
    const qaLoading = ref(false);
    const qaChatBox = ref(null);
    const qaPanel = ref(null);
    const resizing = ref(false);
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
        h = Math.max(160, Math.min(h, window.innerHeight * 0.8));
        if (qaPanel.value) qaPanel.value.style.height = h + 'px';
    }

    function endResize() {
        if (!resizing.value) return;
        resizing.value = false;
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
    }

    function onTouchMove(e) {
        if (!resizing.value) return;
        e.preventDefault();
        const t = e.touches[0];
        const dy = t.clientY - resizeStartY;
        let h = resizeStartH + dy;
        h = Math.max(160, Math.min(h, window.innerHeight * 0.8));
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

    async function qaSend() {
        const t = qaInput.value.trim();
        if (!t || qaLoading.value) return;
        qaMessages.value.push({ role: 'user', text: t });
        qaInput.value = '';
        qaLoading.value = true;
        qaScrollBottom();
        try {
            const resp = await fetch(PA.CONFIG.API_BASE + '/api/agent/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: t, history: [] })
            });
            const json = await resp.json();
            const data = json.data || {};
            if (data.fallback) {
                const msg = { role: 'assistant', text: '', tools: [] };
                qaMessages.value.push(msg);
                if (!qaCloud) {
                    msg.text = '（AI 问答暂不可用：免密钥大模型组件未加载。请确认网络可访问 WorkBuddy，且已通过线上链接打开本页，而不是本地 localhost。）';
                } else {
                    try {
                        for await (const piece of qaAskLLM(t)) {
                            msg.text += piece;
                            qaScrollBottom();
                        }
                    } catch (e) { }
                    if (!msg.text.trim()) {
                        msg.text = '（AI 问答调用失败：本地 localhost 环境受 Origin 限制无法调用免密钥大模型。请通过线上分享链接打开，或检查网络。）';
                    }
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
        qaSend, toggleQa, startResize, bindResize, unbindResize,
    };
};