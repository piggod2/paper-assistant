import { watch } from 'vue';

export function useSettings(state) {
  const { levels, intensity, theme, fontSize, userName } = state;

  ['levels', 'intensity', 'theme', 'fontSize', 'userName'].forEach(function (k) {
    const v = localStorage.getItem('paper_assistant_' + k);
    if (v !== null) {
      try {
        if (k === 'levels') { const d = JSON.parse(v); Object.assign(levels, d) }
        else if (k === 'intensity') intensity.value = v;
        else if (k === 'theme') theme.value = v;
        else if (k === 'fontSize') fontSize.value = v;
        else if (k === 'userName') userName.value = v;
      } catch (e) { }
    }
  });

  watch(levels, function () { localStorage.setItem('paper_assistant_levels', JSON.stringify(levels)) }, { deep: true });
  watch(intensity, function (v) { localStorage.setItem('paper_assistant_intensity', v) });
  watch(theme, function (v) { document.documentElement.setAttribute('data-theme', v); localStorage.setItem('paper_assistant_theme', v) });
  watch(fontSize, function (v) {
    const bases = { small: '13px', standard: '14px', large: '15px', xlarge: '16px' };
    document.documentElement.style.fontSize = bases[v] || '14px';
    localStorage.setItem('paper_assistant_fontSize', v);
  });
  watch(userName, function (v) { localStorage.setItem('paper_assistant_userName', v) });

  return function applySettings() {
    document.documentElement.setAttribute('data-theme', theme.value);
    const bases = { small: '13px', standard: '14px', large: '15px', xlarge: '16px' };
    document.documentElement.style.fontSize = bases[fontSize.value] || '14px';
  };
}
