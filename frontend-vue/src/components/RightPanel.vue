<script setup>
const props = defineProps({
  offline: Object,
  text: Object,
  polished: Object,
  report: Object,
  quickPolish: Function,
  doDetect: Function,
  quickUndo: Function,
  doSearchOnly: Function,
  doTranslateOnly: Function,
  doPipeline: Function,
  doShare: Function,
});
</script>

<template>
  <aside class="panel-right">
    <div class="offline-banner" v-if="offline.value">离线模式：润色正常，翻译检索不可用</div>
    <div style="font-weight:600;font-size:0.857rem;margin-bottom:4px">快速操作</div>
    <button class="command-btn" @click="quickPolish" :disabled="!text.value.trim()">✨ 这整段太AI了</button>
    <button class="command-btn" @click="doDetect" :disabled="!text.value.trim()">🔍 先看看哪里有问题</button>
    <button class="command-btn" @click="quickUndo" :disabled="!polished.value">↩ 这几处都不改</button>
    <button class="command-btn" @click="doSearchOnly" :disabled="!text.value.trim()">📚 找相关文献</button>
    <button class="command-btn" @click="doTranslateOnly" :disabled="!text.value.trim()">🌐 翻译成中文</button>
    <button class="command-btn" @click="doPipeline">🚀 帮我跑全流程</button>
    <button class="command-btn" @click="doShare" :disabled="!polished.value && !report.value">🔗 生成分享链接</button>
  </aside>
</template>
