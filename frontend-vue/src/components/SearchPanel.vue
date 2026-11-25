<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  papers: Object,
  searchSort: Object,
  searchOpenOnly: Object,
  searchLimit: Object,
  searchText: Object,
  toggleSavePaper: Function,
  isPaperSaved: Function,
});

// 跳转知网/万方搜索（把当前检索词带过去）
const cnkiUrl = computed(() => {
  const q = encodeURIComponent(props.searchText?.value || '');
  return `https://kns.cnki.net/kns8/defaultresult/index?kw=${q}`;
});
const wanfangUrl = computed(() => {
  const q = encodeURIComponent(props.searchText?.value || '');
  return `https://s.wanfangdata.com.cn/paper?q=${q}`;
});

const expanded = ref(new Set());

function toggleExpand(id) {
  const s = new Set(expanded.value);
  if (s.has(id)) s.delete(id);
  else s.add(id);
  expanded.value = s;
}

// 排序 + 筛选（纯前端，对已返回结果操作，离线可用）
const displayPapers = computed(() => {
  let list = [...props.papers.value];
  if (props.searchOpenOnly.value) {
    list = list.filter(p => p.open_access_pdf);
  }
  const sort = props.searchSort.value;
  if (sort === 'citations') {
    list.sort((a, b) => (b.citations || 0) - (a.citations || 0));
  } else if (sort === 'year') {
    list.sort((a, b) => (b.year || 0) - (a.year || 0));
  } else {
    list.sort((a, b) => (b.score || 0) - (a.score || 0));
  }
  return list;
});
</script>

<template>
  <div v-if="papers.value.length">
    <div class="search-toolbar" v-if="papers.value.length > 1">
      <label class="search-ctrl">排序
        <select v-model="searchSort.value">
          <option value="relevance">相关度</option>
          <option value="citations">引用数</option>
          <option value="year">发表年份</option>
        </select>
      </label>
      <label class="search-ctrl">篇数
        <select v-model="searchLimit.value" @change="$emit('refetch')">
          <option :value="5">5 篇</option>
          <option :value="10">10 篇</option>
          <option :value="20">20 篇</option>
          <option :value="50">50 篇</option>
        </select>
      </label>
      <label class="search-ctrl search-check">
        <input type="checkbox" v-model="searchOpenOnly.value"> 只看开放获取 PDF
      </label>
      <span class="search-count">共 {{ displayPapers.length }} 篇</span>
    </div>

    <div class="paper-card" v-for="p in displayPapers" :key="p.paper_id">
      <div class="p-title">
        <a :href="p.url || '#'" target="_blank">{{ p.title }}</a>
        <button type="button" class="p-save-btn" :class="{ saved: isPaperSaved(p) }"
          :title="isPaperSaved(p) ? '取消收藏' : '收藏到右侧栏'"
          @click="toggleSavePaper(p)">{{ isPaperSaved(p) ? '★' : '☆' }}</button>
      </div>
      <div class="p-meta">
        {{ p.authors.join(', ') }} · {{ p.year }}
        <span v-if="p.venue && p.venue !== 'arXiv'"> · {{ p.venue }}</span>
        <span v-if="p.citations"> · 引用 {{ p.citations }}</span>
      </div>
      <div class="p-abstract" v-if="p.abstract">
        <template v-if="!expanded.has(p.paper_id)">
          {{ p.abstract }}{{ p.abstract.length >= 300 ? '…' : '' }}
        </template>
        <template v-else>{{ p.abstract }}</template>
        <button v-if="p.abstract.length >= 300" class="p-expand" @click="toggleExpand(p.paper_id)">
          {{ expanded.has(p.paper_id) ? '收起' : '展开全文' }}
        </button>
      </div>
      <div class="p-score">
        <span style="font-size:var(--fs-caption)">相关度 {{ (p.score * 10).toFixed(1) }}/10</span>
        <div class="p-score-bar">
          <div class="p-score-fill" :style="{ width: p.score * 100 + '%' }"></div>
        </div>
        <a v-if="p.open_access_pdf" :href="p.open_access_pdf" target="_blank" title="下载 PDF">📄 PDF</a>
      </div>
      <div class="p-reason">{{ p.relevance_reason }}</div>
    </div>

    <div class="search-tip">
      <span>提示：当前检索 arXiv 英文预印本。中文文献可直接跳转：</span>
      <a :href="cnkiUrl" target="_blank" rel="noopener">知网搜「{{ searchText?.value || '关键词' }}」</a>
      <span class="tip-sep">·</span>
      <a :href="wanfangUrl" target="_blank" rel="noopener">万方搜「{{ searchText?.value || '关键词' }}」</a>
    </div>
  </div>
</template>
