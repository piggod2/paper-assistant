import { ref, reactive } from 'vue';

export function createState() {
  const toast = ref('');

  const state = {
    text: ref(''),
    report: ref(null),
    polished: ref(''),
    changes: ref([]),
    safetyFailures: ref([]),
    papers: ref([]),
    searchSort: ref('relevance'),   // relevance | citations | year
    searchOpenOnly: ref(false),     // 只看开放获取 PDF
    searchLimit: ref(10),           // 检索篇数，默认 10
    translateResult: ref(null),
    pipelineSteps: ref([]),
    loading: ref(''),
    errorMsg: ref(''),
    toast: toast,
    shareBanner: ref(''),
    offline: ref(!navigator.onLine),
    showLeft: ref(true),
    leftWidth: ref(260),              // 左侧栏宽度（可拖拽调整）
    rightWidth: ref(220),             // 右侧栏宽度（可拖拽调整）
    shareCode: ref(''),
    levels: reactive({ A: true, B: true, C: false, F: true, X: true, H: false }),
    intensity: ref('standard'),
    theme: ref('light'),
    fontSize: ref('standard'),
    titleFont: ref('kai'),           // kai=楷体(霞鹜文楷) | hei=黑体(系统)
    userName: ref(''),
    aiAvatar: ref('AI'),
    customPrompt: ref(''),          // 用户自定义的 DeepSeek 补充提示词（追加到内置规则集之后）
    savedPapers: ref([]),           // 收藏的文献列表（跨会话保留）
    history: ref([]),               // 润色/检测历史（跨会话保留，限条数）
    resultCollapsed: ref(false),    // 检测结果是否收起为摘要条
    avatarOptions: ['AI', '🤖', '🧑‍🎓', '📚', '✍️', '🦉', '🌸', '🐱', '🧠', '✨'],
  };

  state.showToast = function (msg) {
    toast.value = msg;
    setTimeout(function () { toast.value = ''; }, 2500);
  };

  return state;
}