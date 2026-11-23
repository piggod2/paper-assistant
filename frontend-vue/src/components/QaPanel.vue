<script setup>
const props = defineProps({
  qa: Object,
});

// 把模板 DOM 元素绑定到 composable 里的 ref（供拖拽/滚动使用）
function setQaPanel(el) { if (el) props.qa.qaPanel.value = el; }
function setQaChatBox(el) { if (el) props.qa.qaChatBox.value = el; }
</script>

<template>
  <div class="qa-panel" :ref="setQaPanel">
    <div class="qa-head">
      💬 论文智助智能体
      <button type="button" class="qa-close" @click="qa.qaOpen.value = false" title="收起">✕</button>
    </div>
    <div class="qa-chat" :ref="setQaChatBox">
      <div class="qa-msg qa-assistant">
        <div class="qa-avatar">AI</div>
        <div class="qa-bubble">你好，我是论文智助智能体。你可以直接问我工具怎么用，也可以贴一段论文让我检测/润色/翻译/找文献。</div>
      </div>
      <div class="qa-msg" v-for="(m, i) in qa.qaMessages.value" :key="i" :class="'qa-' + m.role">
        <div class="qa-avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <div>
          <div class="qa-bubble">{{ m.text }}</div>
          <div class="qa-tools" v-if="m.role === 'assistant' && m.tools && m.tools.length">
            <span class="qa-tool" v-for="t in m.tools" :key="t">{{ t }}</span>
          </div>
        </div>
      </div>
      <div class="qa-msg qa-assistant" v-if="qa.qaLoading.value">
        <div class="qa-avatar">AI</div>
        <div class="qa-bubble"><span class="qa-typing"><i></i><i></i><i></i></span></div>
      </div>
    </div>
    <div class="qa-inputbar">
      <textarea v-model="qa.qaInput.value" placeholder="问我工具用法，或贴论文段落…"
        @keydown.enter.exact.prevent="qa.qaSend"></textarea>
      <button @click="qa.qaSend" :disabled="qa.qaLoading.value || !qa.qaInput.value.trim()">发送</button>
    </div>
    <div class="qa-resize" @mousedown.prevent="qa.startResize" :class="{ dragging: qa.resizing.value }"></div>
  </div>
</template>
