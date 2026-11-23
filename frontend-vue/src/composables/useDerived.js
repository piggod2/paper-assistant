import { computed } from 'vue';

export function useDerived(state) {
  const { report, levels } = state;

  const grades = computed(function () {
    return {
      A: { name: '机械改', desc: '固定句式/标点，零语义风险' },
      B: { name: '建议改', desc: '需句式重组，有豁免条件' },
      C: { name: '只报告', desc: '整篇分布特征', locked: true },
      F: { name: '指纹', desc: '分模型标点特征' },
      X: { name: '永不改', desc: '配对复测推翻', locked: true },
      H: { name: '人审区', desc: '贴切度需人审' },
    };
  });

  const intensities = computed(function () {
    return {
      conservative: { label: '保守', desc: '仅A级' },
      standard: { label: '标准', desc: 'A+B+F' },
      aggressive: { label: '激进', desc: 'A+B+F+B6' },
    };
  });

  const icons = { translate: '🌐', search: '📚', polish: '✨' };

  const xRules = computed(function () {
    if (!report.value) return [];
    const all = [];
    for (const [rid, hits] of Object.entries(report.value.hits || {})) {
      if (hits.length && hits[0].level === 'X') all.push({ id: rid, ...hits[0] });
    }
    return all;
  });

  const summaryC = computed(function () {
    if (!report.value) return '';
    const c = report.value.summary.C || {};
    return Object.entries(c).filter(function ([k, v]) { return v !== null && v !== 0 })
      .map(function ([k, v]) { return k.replace(/_prompt$/, '') + ':' + (typeof v === 'number' ? v.toFixed(2) : v) })
      .join(' · ') || '—';
  });

  function levelOn(k) { return levels[k] ?? false }
  function toggleLevel(k) { if (k !== 'X' && k !== 'C') levels[k] = !levels[k] }
  function totalLevel(lv) {
    if (!report.value) return 0;
    let t = 0;
    for (const [rid, hits] of Object.entries(report.value.hits || {})) {
      if (hits.length && hits[0].level === lv) t += hits.length;
    }
    return t;
  }
  function hitBadgeStyle(lv) {
    const m = { A: 'background:#fed7d7;color:#c53030', B: 'background:#feebc8;color:#b7791f', C: 'background:#e2e8f0;color:#718096', F: 'background:#c6d9f7;color:#1a56db', X: 'background:#c6f6d5;color:#276749', H: 'background:#faf5ff;color:#805ad5' };
    return m[lv] || '';
  }

  return { grades, intensities, icons, xRules, summaryC, levelOn, toggleLevel, totalLevel, hitBadgeStyle };
}
