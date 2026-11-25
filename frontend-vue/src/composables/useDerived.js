import { computed } from 'vue';

export function useDerived(state) {
  const { report, levels } = state;

  const grades = computed(function () {
    return {
      A: { name: '机械改', desc: '固定的句式、标点问题，机器能安全地直接帮你改' },
      B: { name: '建议改', desc: '需要调整句子结构，建议你确认后再改' },
      C: { name: '只报告', desc: '整篇文章的分布特征，只提示、不动手', locked: true },
      F: { name: '指纹', desc: '破折号、分号这类标点使用习惯' },
      X: { name: '永不改', desc: '经反复比对，这些其实不是 AI 味，故意不改', locked: true },
      H: { name: '人审区', desc: '比喻贴不贴切要你自己判断，系统只列出' },
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

  // C 级指标中文名映射（后端返回的 summary.C 键 → 可读中文）
  const C_LABEL = {
    sentence_cv_prompt: '句长CV',
    mtld_prompt: '词汇多样性',
    isomorphic_prompt: '同构率',
    synonym_swap: '同义换词段',
    max_connect_chain: '衔接连环',
  };

  // C 级「只报告」四条规则的展示元数据（与 data/polish-rules.json 的 C1~C4 保持一致）
  // C 级没有具体命中位置（span/match），只能按指标逐项列出实测值 + 通俗说明 + 研究依据
  const C_META = {
    C1: {
      label: '句长CV',
      strategy: '句长变异系数CV',
      ref: '0.54',
      plain: '句子长度太均匀，缺乏起伏。这里只提示你实测值，不自动改（乱改节奏反而更糟）。',
      evidence: '配对复测人类参考 0.54；第一轮抽样 0.67 口径不同不可混用',
    },
    C2: {
      label: '小节方差',
      strategy: '小节长度方差/小标题密度',
      ref: '',
      plain: '小标题分得太碎。只提示，结构问题不逐句改。',
      evidence: 'AI 中位数 7节 vs 人类 1节；小标题密度 AI 1.26/千字 vs 人类 0.32/千字',
    },
    C3: {
      label: '词汇多样性',
      strategy: '词汇多样性 mtld/mattr',
      ref: '143',
      plain: '用词不敢重复、拼命换近义词。其实同一对象反复用原词是正常写法。只提示。',
      evidence: '配对复测 mtld AI 227 vs 人类 143（AI更高=\'用词不敢重复\'）',
    },
    C4: {
      label: '衔接连环',
      strategy: '衔接顺滑度',
      ref: '',
      plain: '段落之间衔接得太顺、跳话题太少。只提示，默认不动。',
      evidence: 'AI 段间跳转 2.1% vs 人类 7.2%（人类反而更爱跳话题）；≥6连环 AI 93%的文章有',
    },
  };

  // 展开态 C 级明细卡片：四条规则都列出，实测值为 null 时标「样本不足」
  const cItems = computed(function () {
    if (!report.value) return [];
    const c = (report.value.summary && report.value.summary.C) || {};
    const items = [];
    for (const rid of Object.keys(C_META)) {
      if (!(rid in c)) continue;
      const meta = C_META[rid];
      const v = c[rid];
      let display;
      if (v === null || v === undefined) display = '样本不足';
      else if (typeof v === 'number') display = Number.isInteger(v) ? String(v) : v.toFixed(2);
      else display = String(v);
      items.push(Object.assign({ rid: rid, value: v, display: display }, meta));
    }
    return items;
  });

  // 旧指标名键 ↔ 新规则 id 键的重复关系（同值，只显示一次）
  const C_PROMPT_DUP = { sentence_cv_prompt: 'C1', mtld_prompt: 'C3', max_connect_chain: 'C4' };

  function _fmtC(v) {
    return typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(2)) : v;
  }

  const summaryC = computed(function () {
    if (!report.value) return '';
    const c = (report.value.summary && report.value.summary.C) || {};
    const parts = [];
    // 优先按 C1~C4 规则 id 展示（新后端）
    for (const rid of Object.keys(C_META)) {
      if (!(rid in c)) continue;
      const v = c[rid];
      if (v === null || v === 0) continue;
      parts.push(C_META[rid].label + ' ' + _fmtC(v));
    }
    // 再补旧指标名键里不与 C1~C4 重复的（同构率、同义换词段等，也兼容旧后端数据）
    for (const [k, v] of Object.entries(c)) {
      if (k in C_META || C_PROMPT_DUP[k]) continue;
      if (v === null || v === 0) continue;
      parts.push((C_LABEL[k] || k.replace(/_prompt$/, '')) + ' ' + _fmtC(v));
    }
    return parts.join(' · ') || '';
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

  return { grades, intensities, icons, xRules, summaryC, cItems, levelOn, toggleLevel, totalLevel, hitBadgeStyle };
}