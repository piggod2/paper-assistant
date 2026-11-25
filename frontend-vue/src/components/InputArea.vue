<script setup>
import { ref } from 'vue';

const props = defineProps({
  text: Object,
  loading: Object,
  handleDrop: Function,
  handleFileSelect: Function,
  doDetect: Function,
  doPolish: Function,
  doPipeline: Function,
  doTranslateOnly: Function,
  doSearchOnly: Function,
});

const fileInput = ref(null);
const textareaHeight = ref(180); // px，初始高度

// ── 自定义拖拽把手（替代浏览器原生 resize，避免与父容器滚动冲突）──
let resizeStartY = 0;
let resizeStartH = 0;
let resizing = false;

function startResize(e) {
  resizing = true;
  resizeStartY = e.clientY;
  resizeStartH = textareaHeight.value;
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'ns-resize';
  window.addEventListener('mousemove', onResizeMove);
  window.addEventListener('mouseup', endResize);
}

function onResizeMove(e) {
  if (!resizing) return;
  const dy = e.clientY - resizeStartY;
  textareaHeight.value = Math.max(120, resizeStartH + dy);
}

function endResize() {
  resizing = false;
  document.body.style.userSelect = '';
  document.body.style.cursor = '';
  window.removeEventListener('mousemove', onResizeMove);
  window.removeEventListener('mouseup', endResize);
}
</script>

<template>
  <div class="input-wrapper">
    <textarea class="input-area" v-model="text.value"
      placeholder="把论文段落粘贴进来，中英文都行&#10;支持拖入 .txt / .md 文件"
      :style="{ height: textareaHeight + 'px' }"
      @drop.prevent="handleDrop" @dragover.prevent></textarea>
    <div class="input-resize-handle" @mousedown.prevent="startResize"></div>
  </div>

  <div class="btn-row">
    <input type="file" accept=".txt,.md" @change="handleFileSelect" ref="fileInput" style="display:none">
    <button class="btn btn-secondary" @click="fileInput.click()" style="font-size:var(--fs-caption)">📁 选择文件</button>
    <button class="btn btn-primary" @click="doPolish" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'polish'"></span>✨ 检测并润色
    </button>
    <button class="btn btn-secondary" @click="doDetect" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'detect'"></span>🔍 只检测
    </button>
    <button class="btn btn-secondary" @click="doPipeline" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'pipeline'"></span>🚀 一键全流程
    </button>
    <button class="btn btn-secondary" @click="doTranslateOnly" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'translate'"></span>🌐 中英互译
    </button>
    <button class="btn btn-secondary" @click="doSearchOnly" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'search'"></span>📚 找相关文献
    </button>
  </div>
  <div style="font-size:var(--fs-caption);color:#888;margin-top:6px">
    <span v-if="!text.value.trim()">⚠️ 输入框还空着，先粘贴文字按钮才会亮</span>
    <span v-else>✅ 已就绪（{{ text.value.trim().length }} 字），可点击上方按钮</span>
  </div>
</template>