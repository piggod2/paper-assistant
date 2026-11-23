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
});

const fileInput = ref(null);
</script>

<template>
  <textarea class="input-area" v-model="text.value" placeholder="把论文段落粘贴进来，中英文都行&#10;支持拖入 .txt / .md 文件"
    @drop.prevent="handleDrop" @dragover.prevent></textarea>
  <div style="display:flex;justify-content:flex-end;margin-top:-12px;position:relative;z-index:1">
    <input type="file" accept=".txt,.md" @change="handleFileSelect" ref="fileInput" style="display:none">
    <button class="btn btn-secondary" @click="fileInput.click()" style="font-size:0.786rem">📁 选择文件</button>
  </div>

  <div class="btn-row">
    <button class="btn btn-secondary" @click="doDetect" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'detect'"></span>🔍 只检测
    </button>
    <button class="btn btn-primary" @click="doPolish" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'polish'"></span>✨ 检测并润色
    </button>
    <button class="btn btn-primary" @click="doPipeline" :disabled="!text.value.trim()">
      <span class="loading" v-if="loading.value == 'pipeline'"></span>📄 一键全流程
    </button>
  </div>
  <div style="font-size:0.786rem;color:#888;margin-top:6px">
    <span v-if="!text.value.trim()">⚠️ 输入框还空着，先粘贴文字按钮才会亮</span>
    <span v-else>✅ 已就绪（{{ text.value.trim().length }} 字），可点击上方按钮</span>
  </div>
</template>
