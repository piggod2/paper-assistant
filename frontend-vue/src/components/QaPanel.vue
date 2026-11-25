<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  qa: Object,
  avatar: { type: String, default: 'AI' },
  customPrompt: { type: Object, default: null },
});

// 提示词编辑弹窗
const showPromptEditor = ref(false);
const draftPrompt = ref('');

function openPromptEditor() {
  draftPrompt.value = props.customPrompt ? props.customPrompt.value : '';
  showPromptEditor.value = true;
}
function savePrompt() {
  if (props.customPrompt) props.customPrompt.value = draftPrompt.value;
  showPromptEditor.value = false;
}

// 头像可能是 emoji 或多字自定义文本，按码点长度调整字号，避免撑破 28px 圆形
const avatarClass = computed(() => {
  const a = props.avatar || 'AI';
  const cp = [...a].length;
  if (cp <= 1) return 'is-emoji';
  if (cp >= 3) return 'is-tiny';
  return '';
});

// 把模板 DOM 元素绑定到 composable 里的 ref（供拖拽/滚动使用）
function setQaPanel(el) { if (el) props.qa.qaPanel.value = el; }
function setQaChatBox(el) { if (el) props.qa.qaChatBox.value = el; }

// 输入框自动撑高：随内容行数增长，最高 160px，超出则滚动，避免文字被裁切
function autoGrow(e) {
  const el = e.target;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

// 大模型流式回答时会先插入一条空的 assistant 消息，此时它本身就是"思考框"，
// 不能再叠加底部的三点动画气泡，否则会出现两个
const showTyping = computed(() => {
  const list = props.qa.qaMessages.value;
  const last = list.length ? list[list.length - 1] : null;
  return props.qa.qaLoading.value && !(last && last.role === 'assistant');
});
</script>

<template>
  <div class="qa-panel" :ref="setQaPanel">
    <div class="qa-head">
      💬 论文智助智能体
      <select class="qa-model" v-model="qa.qaMode.value" title="切换模式：自动/自由问答/润色/检测">
        <option v-for="m in qa.qaModes" :key="m.id" :value="m.id">{{ m.label }}</option>
      </select>
      <select class="qa-model" v-model="qa.qaModel.value" title="切换模型">
        <option v-for="m in qa.qaModels" :key="m.id" :value="m.id">{{ m.label }}</option>
      </select>
      <button type="button" class="qa-prompt-btn" @click="openPromptEditor"
        :title="customPrompt && customPrompt.value ? '已设置自定义提示词' : '设置自定义提示词'">
        ⚙ 提示词<span v-if="customPrompt && customPrompt.value" class="qa-prompt-dot"></span>
      </button>
      <button type="button" class="qa-close" @click="qa.qaOpen.value = false" title="收起">✕</button>
    </div>
    <div class="qa-chat" :ref="setQaChatBox">
      <div class="qa-msg qa-assistant">
        <div class="qa-avatar" :class="avatarClass">{{ avatar || 'AI' }}</div>
        <div class="qa-bubble">你好，我是论文智助智能体。你可以直接问我工具怎么用，也可以贴一段论文让我检测/润色/翻译/找文献。</div>
      </div>
      <div class="qa-msg" v-for="(m, i) in qa.qaMessages.value" :key="i" :class="'qa-' + m.role">
        <div class="qa-avatar" :class="m.role === 'assistant' ? avatarClass : ''">{{ m.role === 'user' ? '我' : (avatar
          || 'AI') }}</div>
        <div>
          <div class="qa-bubble">{{ m.text }}</div>
          <div class="qa-tools" v-if="m.role === 'assistant' && m.tools && m.tools.length">
            <span class="qa-tool" v-for="t in m.tools" :key="t">{{ t }}</span>
          </div>
        </div>
      </div>
      <div class="qa-msg qa-assistant" v-if="showTyping">
        <div class="qa-avatar" :class="avatarClass">{{ avatar || 'AI' }}</div>
        <div class="qa-bubble"><span class="qa-typing"><i></i><i></i><i></i></span></div>
      </div>
    </div>
    <div class="qa-inputbar">
      <textarea v-model="qa.qaInput.value" placeholder="问我工具用法，或贴论文段落…"
        @input="autoGrow" @keydown.enter.exact.prevent="qa.qaSend"></textarea>
      <button @click="qa.qaSend" :disabled="qa.qaLoading.value || !qa.qaInput.value.trim()">发送</button>
    </div>
    <div class="qa-resize" @mousedown.prevent="qa.startResize" :class="{ dragging: qa.resizing.value }"></div>

    <!-- 自定义提示词弹窗 -->
    <div class="prompt-modal-mask" v-if="showPromptEditor" @click.self="showPromptEditor = false">
      <div class="prompt-modal">
        <div class="prompt-modal-head">
          <span>自定义 AI 提示词</span>
          <button type="button" class="qa-close" @click="showPromptEditor = false" title="关闭">✕</button>
        </div>
        <p class="prompt-modal-tip">写一段补充要求，会<b>追加</b>到内置的去 AI 味规则集之后（不覆盖核心能力）。例如角色设定、回答语气、专业领域偏好等。</p>
        <textarea class="prompt-modal-input" v-model="draftPrompt"
          placeholder="例如：回答时更学术一点，多用「论证」「证据」这类表述；我主要写计算机方向的论文…"></textarea>
        <div class="prompt-modal-actions">
          <button type="button" class="btn btn-secondary" @click="showPromptEditor = false">取消</button>
          <button type="button" class="btn btn-primary" @click="savePrompt">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>