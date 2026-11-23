<script setup>
const props = defineProps({
  papers: Object,
});
</script>

<template>
  <div v-if="papers.value.length">
    <div class="paper-card" v-for="p in papers.value" :key="p.paper_id">
      <div class="p-title"><a :href="p.url || '#'" target="_blank">{{ p.title }}</a></div>
      <div class="p-meta">{{ p.authors.join(', ') }} · {{ p.year }} · {{ p.venue }} · 引用 {{ p.citations }}</div>
      <div class="p-abstract" v-if="p.abstract">{{ p.abstract }}{{ p.abstract.length >= 300 ? '…' : '' }}</div>
      <div class="p-score">
        <span style="font-size:0.786rem">匹配度 {{ (p.score * 10).toFixed(1) }}/10</span>
        <div class="p-score-bar">
          <div class="p-score-fill" :style="{ width: p.score * 100 + '%' }"></div>
        </div>
        <a v-if="p.open_access_pdf" :href="p.open_access_pdf" target="_blank" title="PDF">📄</a>
      </div>
      <div class="p-reason">{{ p.relevance_reason }}</div>
    </div>
  </div>
</template>
