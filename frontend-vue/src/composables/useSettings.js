import { watch } from 'vue';

export function useSettings(state) {
  const { levels, intensity, theme, fontSize, titleFont, userName, aiAvatar, customPrompt, leftWidth, rightWidth, savedPapers, history } = state;

  ['levels', 'intensity', 'theme', 'fontSize', 'titleFont', 'userName', 'aiAvatar', 'customPrompt', 'leftWidth', 'rightWidth', 'savedPapers', 'history'].forEach(function (k) {
    const v = localStorage.getItem('paper_assistant_' + k);
    if (v !== null) {
      try {
        if (k === 'levels') { const d = JSON.parse(v); Object.assign(levels, d) }
        else if (k === 'savedPapers') { savedPapers.value = JSON.parse(v) || [] }
        else if (k === 'history') { history.value = JSON.parse(v) || [] }
        else if (k === 'intensity') intensity.value = v;
        else if (k === 'theme') theme.value = v;
        else if (k === 'fontSize') fontSize.value = v;
        else if (k === 'titleFont') titleFont.value = v;
        else if (k === 'userName') userName.value = v;
        else if (k === 'aiAvatar') aiAvatar.value = v;
        else if (k === 'customPrompt') customPrompt.value = v;
        else if (k === 'leftWidth') leftWidth.value = Number(v) || 260;
        else if (k === 'rightWidth') rightWidth.value = Number(v) || 220;
      } catch (e) { }
    }
  });

  watch(levels, function () { localStorage.setItem('paper_assistant_levels', JSON.stringify(levels)) }, { deep: true });
  watch(intensity, function (v) { localStorage.setItem('paper_assistant_intensity', v) });
  watch(theme, function (v) { document.documentElement.setAttribute('data-theme', v); localStorage.setItem('paper_assistant_theme', v) });
  watch(fontSize, function (v) {
    const bases = { small: '14px', standard: '15px', large: '16px', xlarge: '17px' };
    document.documentElement.style.fontSize = bases[v] || '15px';
    localStorage.setItem('paper_assistant_fontSize', v);
  });
  watch(titleFont, function (v) {
    document.documentElement.setAttribute('data-title-font', v || 'kai');
    localStorage.setItem('paper_assistant_titleFont', v || 'kai');
  });
  watch(userName, function (v) { localStorage.setItem('paper_assistant_userName', v) });
  watch(aiAvatar, function (v) { localStorage.setItem('paper_assistant_aiAvatar', v) });
  watch(customPrompt, function (v) { localStorage.setItem('paper_assistant_customPrompt', v) });
  watch(leftWidth, function (v) { localStorage.setItem('paper_assistant_leftWidth', v) });
  watch(rightWidth, function (v) { localStorage.setItem('paper_assistant_rightWidth', v) });
  watch(savedPapers, function (v) {
    try { localStorage.setItem('paper_assistant_savedPapers', JSON.stringify(v)) } catch (e) { }
  }, { deep: true });
  let persistingHistory = false;
  watch(history, function (v) {
    if (persistingHistory) return;
    let list = v;
    while (true) {
      try {
        localStorage.setItem('paper_assistant_history', JSON.stringify(list));
        break;
      } catch (e) {
        if (list.length <= 1) { list = null; break }
        list = list.slice(0, Math.max(1, Math.floor(list.length / 2)));
      }
    }
    if (list && list.length !== v.length) {
      persistingHistory = true;
      history.value = list;
      persistingHistory = false;
      if (state.showToast) state.showToast('存储空间不足，已自动清理旧历史');
    }
  }, { deep: true });

  return function applySettings() {
    document.documentElement.setAttribute('data-theme', theme.value);
    const bases = { small: '14px', standard: '15px', large: '16px', xlarge: '17px' };
    document.documentElement.style.fontSize = bases[fontSize.value] || '15px';
    document.documentElement.setAttribute('data-title-font', titleFont.value || 'kai');
  };
}