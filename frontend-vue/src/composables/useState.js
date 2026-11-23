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
    translateResult: ref(null),
    pipelineSteps: ref([]),
    loading: ref(''),
    errorMsg: ref(''),
    toast: toast,
    shareBanner: ref(''),
    offline: ref(!navigator.onLine),
    showLeft: ref(true),
    shareCode: ref(''),
    levels: reactive({ A: true, B: true, C: false, F: true, X: true, H: false }),
    intensity: ref('standard'),
    theme: ref('light'),
    fontSize: ref('standard'),
    userName: ref(''),
  };

  state.showToast = function (msg) {
    toast.value = msg;
    setTimeout(function () { toast.value = ''; }, 2500);
  };

  return state;
}
