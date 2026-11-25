<script setup>
const props = defineProps({
  grades: Object,
  intensities: Object,
  levels: Object,
  intensity: Object,
  theme: Object,
  fontSize: Object,
  titleFont: Object,
  userName: Object,
  aiAvatar: Object,
  avatarOptions: Array,
  showLeft: Boolean,
  levelOn: Function,
  toggleLevel: Function,
});

const emit = defineEmits(['resize-start']);
</script>

<template>
  <aside class="panel-left" :class="{ collapsed: !showLeft }">
    <div class="resize-handle resize-left" @mousedown.prevent="emit('resize-start', 'left', $event)"
      v-if="showLeft"></div>
    <div class="setting-group">
      <h4>检测级别</h4>
      <div class="setting-row" v-for="(g, key) in grades" :key="key">
        <span class="grade-name">
          <span class="grade-title" :title="g.desc">{{ g.name }} · {{ key }}级</span>
          <span class="grade-desc">{{ g.desc }}</span>
        </span>
        <input type="checkbox" class="toggle" :checked="levelOn(key)" :disabled="g.locked" @change="toggleLevel(key)">
      </div>
    </div>
    <div class="setting-group">
      <h4>改写强度</h4>
      <div class="setting-row" v-for="(v, k) in intensities" :key="k">
        <label><input type="radio" v-model="intensity.value" :value="k" style="margin-right:4px">{{ v.label }}</label>
        <span style="font-size:var(--fs-caption);color:var(--text3)">{{ v.desc }}</span>
      </div>
    </div>
    <div class="setting-group">
      <h4>外观</h4>
      <div class="setting-row">
        <span>主题</span>
        <select class="theme-select" v-model="theme.value">
          <option value="light">浅色</option>
          <option value="dark">深色</option>
          <option value="sepia">护眼</option>
          <option value="forest">森林</option>
          <option value="midnight">午夜</option>
        </select>
      </div>
      <div class="setting-row">
        <span>字号</span>
        <select class="theme-select" v-model="fontSize.value">
          <option value="small">小</option>
          <option value="standard">标准</option>
          <option value="large">大</option>
          <option value="xlarge">特大</option>
        </select>
      </div>
      <div class="setting-row">
        <span>标题字体</span>
        <select class="theme-select" v-model="titleFont.value">
          <option value="kai">楷体（文雅）</option>
          <option value="hei">黑体（现代）</option>
        </select>
      </div>
    </div>
    <div class="setting-group">
      <h4>AI 头像</h4>
      <div class="avatar-grid">
        <button type="button" v-for="a in avatarOptions" :key="a" class="avatar-opt"
          :class="{ active: aiAvatar.value === a }" :title="a" @click="aiAvatar.value = a">{{ a }}</button>
      </div>
      <div class="avatar-custom">
        <input v-model="aiAvatar.value" maxlength="4" placeholder="自定义 1~2 个字符">
        <button type="button" class="avatar-reset" @click="aiAvatar.value = 'AI'" title="恢复默认">↺</button>
      </div>
    </div>
    <div class="setting-group">
      <h4>称呼</h4>
      <input v-model="userName.value" placeholder="你的称呼"
        style="width:100%;padding:4px 8px;border-radius:4px;border:1px solid rgba(128,128,128,.2);font-size:var(--fs-sub);background:var(--bg-card);color:var(--text)">
    </div>
  </aside>
</template>