<script setup>
import { ref } from 'vue';

const props = defineProps({
  offline: Object,
  polished: Object,
  report: Object,
  quickUndo: Function,
  doShare: Function,
  savedPapers: Object,
  history: Object,
  removeSavedPaper: Function,
  removeHistory: Function,
  clearHistory: Function,
  loadHistory: Function,
});

const emit = defineEmits(['resize-start']);

// 历史记录条目展开状态（用唯一 id 索引；旧数据无 id 时回退到 at）
const expandedHistory = ref(null);

function fmtTime(ts) {
  const d = new Date(ts);
  const pad = n => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function hid(h) {
  return h.id || String(h.at);
}

function toggleHistory(h) {
  const key = hid(h);
  expandedHistory.value = expandedHistory.value === key ? null : key;
}
</script>

<template>
  <aside class="panel-right">
    <div class="resize-handle resize-right" @mousedown.prevent="emit('resize-start', 'right', $event)"></div>
    <div class="offline-banner" v-if="offline.value">离线模式：润色正常，翻译检索不可用</div>
    <div style="font-weight:600;font-size:var(--fs-sub);margin-bottom:4px">快捷操作</div>
    <button class="command-btn" @click="quickUndo" :disabled="!polished.value">↩ 撤销润色，恢复原文</button>
    <button class="command-btn" @click="doShare" :disabled="!polished.value && !report.value">🔗 生成分享链接</button>

    <!-- 收藏文献 -->
    <div class="right-section">
      <div class="right-section-head">
        <span>⭐ 收藏文献</span>
        <span class="right-section-count">{{ savedPapers.value.length }}</span>
      </div>
      <div v-if="!savedPapers.value.length" class="right-empty">检索结果里点「☆」即可收藏</div>
      <div v-else class="saved-list">
        <div class="saved-item" v-for="p in savedPapers.value" :key="p.paper_id || p.title">
          <a class="saved-title" :href="p.url || '#'" target="_blank" :title="p.title">{{ p.title }}</a>
          <div class="saved-meta">
            {{ (p.authors || []).slice(0, 2).join(', ') }}<span v-if="p.year"> · {{ p.year }}</span>
            <button type="button" class="saved-del" title="移除"
              @click="removeSavedPaper(p.paper_id || p.url || p.title)">✕</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史记录 -->
    <div class="right-section">
      <div class="right-section-head">
        <span>🕘 历史记录</span>
        <button type="button" class="saved-del" v-if="history.value.length" title="清空"
          @click="clearHistory">清空</button>
      </div>
      <div v-if="!history.value.length" class="right-empty">检测/润色后会自动记录</div>
      <div v-else class="history-list">
        <div class="history-item" v-for="(h, i) in history.value" :key="hid(h)">
          <div class="history-head" @click="toggleHistory(h)">
            <span class="history-type" :class="h.type">{{ h.type === 'polish' ? '润色' : '检测' }}</span>
            <span class="history-time">{{ fmtTime(h.at) }}</span>
            <span class="history-preview">{{ (h.text || '').slice(0, 18) }}…</span>
            <button type="button" class="saved-del" title="删除" @click.stop="removeHistory(i)">✕</button>
          </div>
          <div class="history-body" v-if="expandedHistory === hid(h)">
            <button type="button" class="history-load" @click="loadHistory(h)">载入到主区</button>
            <div class="history-text">
              <div class="history-label">原文</div>
              <div class="history-content">{{ h.text }}</div>
              <template v-if="h.polished">
                <div class="history-label">改文</div>
                <div class="history-content">{{ h.polished }}</div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="right-hint">
      <div style="font-weight:600;font-size:var(--fs-caption);margin-bottom:6px;color:var(--text2)">小提示</div>
      <div style="font-size:var(--fs-caption);color:var(--text3);line-height:1.7">
        粘贴文字后，主按钮区可一键「检测 / 润色 / 全流程 / 互译 / 找文献」。<br>
        润色只改有实证的 AI 味信号，不替你重写整篇。
      </div>
    </div>
  </aside>
</template>
