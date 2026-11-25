<script setup>
import { onMounted, ref } from 'vue';
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
import FloatNav from './components/FloatNav.vue';
import ManualModal from './components/ManualModal.vue';

const state = createState();
const applySettings = useSettings(state);
const derived = useDerived(state);
const actions = useActions(state);
const qa = useQa(state);

// ── 使用手册弹窗 ──
const manualOpen = ref(false);

// ── 侧栏拖拽调整宽度 ──
// resizingSide: '' | 'left' | 'right'，记录当前正在拖哪一侧
let resizingSide = '';
let resizeStartX = 0;
let resizeStartW = 0;

function startResize(side, e) {
  if (side === 'left' && !state.showLeft.value) return; // 左栏折叠时不可拖
  resizingSide = side;
  resizeStartX = e.clientX;
  resizeStartW = side === 'left' ? state.leftWidth.value : state.rightWidth.value;
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'col-resize';
  document.body.classList.add('resizing-sidebar');
  window.addEventListener('mousemove', onResizeMove);
  window.addEventListener('mouseup', endResize);
}
function onResizeMove(e) {
  if (!resizingSide) return;
  const dx = e.clientX - resizeStartX;
  if (resizingSide === 'left') {
    const w = Math.min(420, Math.max(180, resizeStartW + dx));
    state.leftWidth.value = w;
  } else {
    const w = Math.min(400, Math.max(160, resizeStartW - dx));
    state.rightWidth.value = w;
  }
}
function endResize() {
  resizingSide = '';
  document.body.style.userSelect = '';
  document.body.style.cursor = '';
  document.body.classList.remove('resizing-sidebar');
  window.removeEventListener('mousemove', onResizeMove);
  window.removeEventListener('mouseup', endResize);
}

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
  <div class="layout" :style="{ '--left-w': state.leftWidth.value + 'px', '--right-w': state.rightWidth.value + 'px' }">
    <SidePanel :grades="derived.grades.value" :intensities="derived.intensities.value" :levels="state.levels"
      :intensity="state.intensity" :theme="state.theme" :font-size="state.fontSize" :title-font="state.titleFont"
      :user-name="state.userName" :ai-avatar="state.aiAvatar" :avatar-options="state.avatarOptions"
      :show-left="state.showLeft.value" :level-on="derived.levelOn" :toggle-level="derived.toggleLevel"
      @resize-start="startResize" />

    <div class="sidebar-toggle" :class="{ collapsed: !state.showLeft.value }"
      @click="state.showLeft.value = !state.showLeft.value">
      {{ state.showLeft.value ? '◀' : '▶' }}
    </div>

    <FloatNav :show-left="state.showLeft.value" :report="state.report" />

    <main class="panel-main">
      <div class="header-bar">
        <div>
          <h1>{{ CONFIG.APP_NAME }} <span class="badge"><i class="live-dot"></i>本地引擎就绪</span></h1>
          <p class="slogan">{{ CONFIG.SLOGAN }}</p>
        </div>
        <div class="header-actions">
          <button type="button" class="qa-toggle manual-toggle" @click="manualOpen = true">
            📖 使用手册
          </button>
          <button type="button" class="qa-toggle" @click="qa.toggleQa">
            {{ qa.qaOpen.value ? '✕ 收起智能体' : '💬 智能体问答' }}
          </button>
        </div>
      </div>

      <div class="share-banner" v-if="state.shareBanner.value">{{ state.shareBanner.value }}</div>

      <QaPanel v-if="qa.qaOpen.value" :qa="qa" :avatar="state.aiAvatar.value" :custom-prompt="state.customPrompt" />

      <div data-section="input">
        <InputArea :text="state.text" :loading="state.loading" :file-input="null" :handle-drop="actions.handleDrop"
          :handle-file-select="actions.handleFileSelect" :do-detect="actions.doDetect" :do-polish="actions.doPolish"
          :do-pipeline="actions.doPipeline" :do-translate-only="actions.doTranslateOnly"
          :do-search-only="actions.doSearchOnly" />
      </div>

      <div class="pipeline-steps" v-if="state.pipelineSteps.value.length">
        <span class="pipeline-step" v-for="s in state.pipelineSteps.value" :key="s.step" :class="s.status">
          {{ derived.icons[s.step] }} {{ s.step }} {{ s.elapsed_ms }}ms · {{ s.message }}
        </span>
      </div>

      <div class="result-card translate-result" v-if="state.translateResult.value" data-section="translate">
        <div class="p-meta">翻译完成 · {{ state.translateResult.value.segments }}段 · {{
          state.translateResult.value.elapsed_ms }}ms</div>
        <div class="segment" style="margin-top:8px;line-height:1.8;white-space:pre-wrap">
          {{ state.translateResult.value.translated }}
        </div>
      </div>

      <div data-section="search">
        <SearchPanel :papers="state.papers" :search-sort="state.searchSort" :search-open-only="state.searchOpenOnly"
          :search-limit="state.searchLimit" :search-text="state.text" :toggle-save-paper="actions.toggleSavePaper"
          :is-paper-saved="actions.isPaperSaved" @refetch="actions.doSearchOnly" />
      </div>

      <div data-section="report">
        <ReportPanel :report="state.report" :polished="state.polished" :changes="state.changes"
          :safety-failures="state.safetyFailures" :text="state.text" :total-level="derived.totalLevel"
          :summary-c="derived.summaryC" :c-items="derived.cItems" :x-rules="derived.xRules"
          :hit-badge-style="derived.hitBadgeStyle" :qa="qa" :collapsed="state.resultCollapsed"
          @toggle-collapse="state.resultCollapsed.value = !state.resultCollapsed.value" />
      </div>

      <div class="empty-state"
        v-if="!state.report.value && !state.loading.value && !state.text.value.trim() && !state.papers.value.length && !state.translateResult.value && !state.polished.value">
        <div class="empty-illustration">📝<span class="empty-spark">✨</span></div>
        <p class="empty-title">把论文段落粘贴进来</p>
        <p class="empty-desc">粘贴文字或拖入文件，然后点上方按钮开始「检测 / 润色」</p>
        <p class="empty-meta">支持 .txt / .md 拖入 · 润色完全离线可用 · 翻译和检索需要联网配置</p>
      </div>
      <div class="empty-state" v-if="state.errorMsg.value">
        <p style="color:var(--red)">{{ state.errorMsg.value }}</p>
        <button class="btn btn-secondary" @click="state.errorMsg.value = ''" style="margin-top:8px">关闭</button>
      </div>
    </main>

    <RightPanel :offline="state.offline" :polished="state.polished" :report="state.report"
      :quick-undo="actions.quickUndo" :do-share="actions.doShare" :saved-papers="state.savedPapers"
      :history="state.history" :remove-saved-paper="actions.removeSavedPaper" :remove-history="actions.removeHistory"
      :clear-history="actions.clearHistory" :load-history="actions.loadHistory" @resize-start="startResize" />
  </div>

  <footer class="footer">
    去 AI 味规则集基于 <a href="https://github.com/larashero3-dotcom/lieflat-less-ai-tone"
      target="_blank">lieflat-less-ai-tone</a>（CC BY-NC 4.0），数据源自两轮对照研究：629篇不配对对照 +
    270对同题同事实配对复测，约520万汉字、约50万次语义判断。本项目为非商业教学演示用途。
  </footer>

  <div class="toast" v-if="state.toast.value" @click="state.toast.value = ''">{{ state.toast.value }}</div>

  <ManualModal :open="manualOpen" @close="manualOpen = false" />
</template>