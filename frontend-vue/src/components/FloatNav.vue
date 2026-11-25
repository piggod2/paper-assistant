<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

// 浮动目录：定位在左栏与主区之间的空隙，随主区滚动高亮当前区域，点击平滑滚动
// 依赖主区元素带 data-section="名称" 属性；组件挂载后扫描 .panel-main 内所有 [data-section]
// 「检测结果」项下按命中等级（A/B/F/H/X）追加子分支，没命中的等级不显示

const props = defineProps({
  showLeft: Boolean,   // 左栏是否展开（折叠时目录跟着收起，避免挡住内容）
  report: Object,      // 检测报告（用于计算检测结果下的等级子分支）
});

const sections = ref([]);     // [{ id, label, el }]
const activeId = ref('');
const visible = ref(false);

let observer = null;
let mo = null;

// 可导航区域顺序（与 App.vue 模板顺序一致），只有实际存在的才展示
const SECTION_ORDER = ['input', 'translate', 'search', 'report'];

const SECTION_LABEL = {
  input: '输入区',
  translate: '翻译结果',
  search: '检索结果',
  report: '检测结果',
};

// 检测结果下的等级子分支：根据 report.hits 里有命中的等级动态生成
// C 级「只报告」没有 hits 桶（无 pattern），改看 summary.C 是否有有效值
const LEVEL_ORDER = ['A', 'B', 'C', 'F', 'H', 'X'];
const LEVEL_LABEL = { A: '机械改', B: '建议改', C: '只报告', F: '指纹', H: '人审区', X: '永不改' };

const reportLevels = computed(() => {
  const hits = props.report?.value?.hits || {};
  const present = new Set();
  for (const [rid, list] of Object.entries(hits)) {
    if (list.length) present.add(list[0].level);
  }
  // C 级不在 hits 里，单独看 summary.C 是否至少有一项有效值（非 null、非 0）
  const c = props.report?.value?.summary?.C || {};
  const hasC = Object.values(c).some(v => v !== null && v !== undefined && v !== 0);
  if (hasC) present.add('C');
  return LEVEL_ORDER.filter(lv => present.has(lv));
});

function scanSections() {
  const main = document.querySelector('.panel-main');
  if (!main) return;
  const els = main.querySelectorAll('[data-section]');
  const list = [];
  els.forEach(el => {
    const id = el.getAttribute('data-section');
    if (id && !list.some(s => s.id === id)) {
      list.push({ id, label: SECTION_LABEL[id] || id, el });
    }
  });
  // 按预定顺序排序
  list.sort((a, b) => SECTION_ORDER.indexOf(a.id) - SECTION_ORDER.indexOf(b.id));
  sections.value = list;
  visible.value = list.length > 0;
}

function rebuildObserver() {
  if (observer) observer.disconnect();
  observer = new IntersectionObserver(
    entries => {
      // 取当前视口内最靠上、且占据视口中部以上的区域为 active
      const inView = entries
        .filter(e => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (inView.length) {
        activeId.value = inView[0].target.getAttribute('data-section');
      }
    },
    { root: document.querySelector('.panel-main'), rootMargin: '-15% 0px -65% 0px', threshold: 0 }
  );
  sections.value.forEach(s => observer.observe(s.el));
}

function scrollToSection(id) {
  const s = sections.value.find(x => x.id === id);
  if (!s) return;
  const main = document.querySelector('.panel-main');
  if (!main) return;
  // 用 getBoundingClientRect 相对滚动容器计算，避免 offsetTop 因定位祖先不同而算错
  const elTop = s.el.getBoundingClientRect().top;
  const containerTop = main.getBoundingClientRect().top;
  const offset = elTop - containerTop + main.scrollTop;
  const target = Math.max(0, offset - 24);
  main.scrollTo({ top: target, behavior: 'smooth' });
  activeId.value = id;
}

// 跳转到检测结果下某个等级的分支卡片（主区 .level-group.lv-X；X 级走 .x-block）
function scrollToLevel(lv) {
  const main = document.querySelector('.panel-main');
  if (!main) return;
  const selector = lv === 'X' ? '.x-block' : '.level-group.lv-' + lv;
  const el = main.querySelector(selector);
  if (!el) return;
  const elTop = el.getBoundingClientRect().top;
  const containerTop = main.getBoundingClientRect().top;
  const offset = elTop - containerTop + main.scrollTop;
  main.scrollTo({ top: Math.max(0, offset - 24), behavior: 'smooth' });
  activeId.value = 'report';
}

// 内容变化（检测结果出现/收起、检索完成等）后重新扫描
function refresh() {
  scanSections();
  rebuildObserver();
}

onMounted(() => {
  refresh();
  // 用 MutationObserver 监听主区子树变化，动态增删的锚点自动纳入
  const main = document.querySelector('.panel-main');
  if (main) {
    mo = new MutationObserver(() => refresh());
    mo.observe(main, { childList: true, subtree: true });
  }
});

onBeforeUnmount(() => {
  if (observer) observer.disconnect();
  if (mo) mo.disconnect();
});
</script>

<template>
  <nav class="float-nav" :class="{ visible, hidden: !showLeft }" aria-label="页面目录">
    <ul>
      <li v-for="s in sections" :key="s.id" :class="{ active: activeId === s.id, 'has-child': s.id === 'report' }">
        <button type="button" @click="scrollToSection(s.id)">
          <span class="dot"></span>
          <span class="label">{{ s.label }}</span>
        </button>
        <!-- 检测结果下的等级子分支 -->
        <ul v-if="s.id === 'report' && reportLevels.length" class="sub-list">
          <li v-for="lv in reportLevels" :key="lv" class="sub-item">
            <button type="button" @click="scrollToLevel(lv)">
              <span class="sub-dot" :class="'lv-' + lv"></span>
              <span class="label">{{ LEVEL_LABEL[lv] }}</span>
            </button>
          </li>
        </ul>
      </li>
    </ul>
  </nav>
</template>