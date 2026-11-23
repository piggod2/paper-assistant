<script setup>
import { onMounted } from 'vue';
import { CONFIG } from './composables/useCore.js';
import { createState } from './composables/useState.js';
import { useSettings } from './composables/useSettings.js';
import { useDerived } from './composables/useDerived.js';
import { useActions } from './composables/useActions.js';
import { useQa } from './composables/useQa.js';

import SidePanel from './components/SidePanel.vue';
import QaPanel from './components/QaPanel.vue';
import InputArea from './components/InputArea.vue';
import ReportPanel from './components/ReportPanel.vue';
import SearchPanel from './components/SearchPanel.vue';
import RightPanel from './components/RightPanel.vue';

const state = createState();
const applySettings = useSettings(state);
const derived = useDerived(state);
const actions = useActions(state);
const qa = useQa();

onMounted(() => {
  applySettings();

  const p = new URLSearchParams(location.search);
  const s = p.get('s');
  if (s) {
    try {
      const d = JSON.parse(new TextDecoder().decode(
        Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
      ));
      state.text.value = d.text || '';
      state.polished.value = d.polished || '';
      state.shareBanner.value = d.from ? `${d.from}分享的一份检测结果 · ${d.date}` : '分享的检测结果';
    } catch (e) { }
  }

  state.shareCode.value = p.get('sharecode');
  if (state.shareCode.value) actions.fetchShare();

  window.addEventListener('online', () => { state.offline.value = false });
  window.addEventListener('offline', () => { state.offline.value = true });

  qa.bindResize();
});
</script>

<template>
  <div class="layout">
    <SidePanel
      :grades="derived.grades"
      :intensities="derived.intensities"
      :levels="state.levels"
      :intensity="state.intensity"
      :theme="state.theme"
      :font-size="state.fontSize"
      :user-name="state.userName"
      :show-left="state.showLeft"
      :level-on="derived.levelOn"
      :toggle-level="derived.toggleLevel"
    />

    <div class="sidebar-toggle" @click="state.showLeft = !state.showLeft">
      {{ state.showLeft ? '◀' : '▶' }}
    </div>

    <main class="panel-main">
      <div class="header-bar">
        <div>
          <h1>{{ CONFIG.APP_NAME }} <span class="badge">本地引擎就绪 · 离线可用</span></h1>
          <p class="slogan">{{ CONFIG.SLOGAN }}</p>
        </div>
        <button type="button" class="qa-toggle" @click="qa.toggleQa">
          {{ qa.qaOpen.value ? '✕ 收起智能体' : '💬 智能体问答' }}
        </button>
      </div>

      <div class="share-banner" v-if="state.shareBanner.value">{{ state.shareBanner.value }}</div>

      <QaPanel v-if="qa.qaOpen.value" :qa="qa" />

      <InputArea
        :text="state.text"
        :loading="state.loading"
        :file-input="null"
        :handle-drop="actions.handleDrop"
        :handle-file-select="actions.handleFileSelect"
        :do-detect="actions.doDetect"
        :do-polish="actions.doPolish"
        :do-pipeline="actions.doPipeline"
      />

      <div class="pipeline-steps" v-if="state.pipelineSteps.value.length">
        <span class="pipeline-step" v-for="s in state.pipelineSteps.value" :key="s.step" :class="s.status">
          {{ derived.icons[s.step] }} {{ s.step }} {{ s.elapsed_ms }}ms · {{ s.message }}
        </span>
      </div>

      <div class="result-card translate-result" v-if="state.translateResult.value">
        <div class="p-meta">翻译完成 · {{ state.translateResult.value.segments }}段 · {{ state.translateResult.value.elapsed_ms }}ms</div>
        <div class="segment" style="margin-top:8px;line-height:1.8;white-space:pre-wrap">
          {{ state.translateResult.value.translated }}
        </div>
      </div>

      <SearchPanel :papers="state.papers" />

      <ReportPanel
        :report="state.report"
        :polished="state.polished"
        :changes="state.changes"
        :safety-failures="state.safetyFailures"
        :text="state.text"
        :total-level="derived.totalLevel"
        :summary-c="derived.summaryC"
        :x-rules="derived.xRules"
        :hit-badge-style="derived.hitBadgeStyle"
      />

      <div class="empty-state" v-if="!state.report.value && !state.loading.value && !state.text.value.trim() && !state.papers.value.length && !state.translateResult.value && !state.polished.value">
        <p>把论文段落粘贴进来，选择功能按钮开始</p>
        <p style="font-size:0.857rem;margin-top:8px">支持 .txt / .md 拖入 · 润色完全离线可用 · 翻译和检索需要联网配置</p>
      </div>
      <div class="empty-state" v-if="state.errorMsg.value">
        <p style="color:var(--red)">{{ state.errorMsg.value }}</p>
        <button class="btn btn-secondary" @click="state.errorMsg.value = ''" style="margin-top:8px">关闭</button>
      </div>
    </main>

    <RightPanel
      :offline="state.offline"
      :text="state.text"
      :polished="state.polished"
      :report="state.report"
      :quick-polish="actions.quickPolish"
      :do-detect="actions.doDetect"
      :quick-undo="actions.quickUndo"
      :do-search-only="actions.doSearchOnly"
      :do-translate-only="actions.doTranslateOnly"
      :do-pipeline="actions.doPipeline"
      :do-share="actions.doShare"
    />
  </div>

  <footer class="footer">
    去 AI 味规则集基于 <a href="https://github.com/larashero3-dotcom/lieflat-less-ai-tone" target="_blank">lieflat-less-ai-tone</a>（CC BY-NC 4.0），数据源自两轮对照研究：629篇不配对对照 + 270对同题同事实配对复测，约520万汉字、约50万次语义判断。本项目为非商业教学演示用途。
  </footer>

  <div class="toast" v-if="state.toast.value" @click="state.toast.value = ''">{{ state.toast.value }}</div>
</template>
