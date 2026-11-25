<script setup>
import { computed } from 'vue';

const props = defineProps({
  report: Object,
  polished: Object,
  changes: Object,
  safetyFailures: Object,
  text: Object,
  totalLevel: Function,
  summaryC: Object,
  cItems: Object,
  xRules: Object,
  hitBadgeStyle: Function,
  qa: Object,
  collapsed: Object,
});

const emit = defineEmits(['toggle-collapse']);

const JUDGE_LABEL = {
  conclusion_colon: '结论提示冒号（规则12）',
  isomorphic_triple: '高度同构三连（规则13）',
};

// 等级图标映射（字母+emoji 双重编码，色弱/快速扫读更友好）
const LEVEL_ICON = { A: '🔴', B: '🟡', C: '📊', F: '🔍', X: '🛡️', H: '👁️' };

// 等级中文名（用于分支标题）
const LEVEL_NAME = { A: '机械改', B: '建议改', C: '只报告', F: '指纹', X: '永不改', H: '人审区' };

// 按等级聚合 report.hits：{ A: [{rid, hits}], B: [...], ... }，只含有命中的等级
// 注意：X 级走独立的 x-block（有"故意不修改"的特殊语义说明），不纳入这里
const GROUP_ORDER = ['A', 'B', 'F', 'H'];
const groupedHits = computed(() => {
  const map = {};
  const hits = props.report.value?.hits || {};
  for (const [rid, list] of Object.entries(hits)) {
    if (!list.length) continue;
    const lv = list[0].level;
    if (!map[lv]) map[lv] = [];
    map[lv].push({ rid, hits: list });
  }
  // 按等级固定顺序 + 等级内按规则 id 排序
  return GROUP_ORDER
    .filter(lv => map[lv])
    .map(lv => ({ level: lv, groups: map[lv].sort((a, b) => a.rid.localeCompare(b.rid)) }));
});

// ── diff 高亮：把 changes 里的 original/replacement 在原文/改文中标色 ──
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 按位置倒序、长片段优先替换，避免重叠/偏移问题
function applyHighlights(baseText, segments, cls) {
  let html = escapeHtml(baseText);
  // 用占位符回填，避免转义后定位偏移
  const sorted = [...segments].sort((a, b) => b.str.length - a.str.length);
  for (const seg of sorted) {
    if (!seg.str) continue;
    const esc = escapeHtml(seg.str);
    if (html.includes(esc)) {
      html = html.split(esc).join(`<mark class="diff ${cls}">${esc}</mark>`);
    }
  }
  return html;
}

const highlightedBefore = computed(() => {
  const segs = (props.changes.value || []).map(c => ({ str: c.original })).filter(s => s.str);
  return applyHighlights(props.text.value || '', segs, 'diff-del');
});

const highlightedAfter = computed(() => {
  const segs = (props.changes.value || []).map(c => ({ str: c.replacement })).filter(s => s.str);
  return applyHighlights(props.polished.value || '', segs, 'diff-add');
});
</script>

<template>
  <div v-if="report.value">
    <!-- 收起态：摘要条 -->
    <div class="result-summary-bar" v-if="collapsed.value" @click="emit('toggle-collapse')">
      <span class="summary-icons">
        <template v-if="totalLevel('A')">🔴{{ totalLevel('A') }}</template>
        <template v-if="totalLevel('B')">🟡{{ totalLevel('B') }}</template>
        <template v-if="summaryC.value">📊</template>
        <template v-if="totalLevel('F')">🔍{{ totalLevel('F') }}</template>
      </span>
      <span class="summary-text">
        共 {{ report.value.actionable_total || 0 }} 处 AI 味特征
        <template v-if="polished.value"> · ✨ 润色已完成</template>
      </span>
      <span class="summary-hint">— 点击展开完整结果 —</span>
    </div>

    <!-- 展开态：完整内容 -->
    <template v-if="!collapsed.value">
      <div class="report-toolbar">
        <span class="report-toolbar-title">检测报告</span>
        <button type="button" class="collapse-btn" @click="emit('toggle-collapse')">收起 ▲</button>
      </div>

      <div class="stat-bar">
        <span class="stat-tag A" v-if="totalLevel('A')">🔴 A级 {{ totalLevel('A') }}处</span>
        <span class="stat-tag B" v-if="totalLevel('B')">🟡 B级 {{ totalLevel('B') }}处</span>
        <span class="stat-tag C" v-if="summaryC.value">📊 C级 {{ summaryC.value }}</span>
        <span class="stat-tag F" v-if="totalLevel('F')">🔍 F级 {{ totalLevel('F') }}处</span>
        <span class="stat-tag X" v-if="totalLevel('X')">🛡️ X级 {{ totalLevel('X') }}处已保护</span>
        <span class="stat-tag H" v-if="totalLevel('H')">👁️ H级 {{ totalLevel('H') }}处待人审</span>
      </div>

      <div class="result-card judge-card" v-if="qa">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span style="font-weight:600;font-size:var(--fs-body)">🧠 语义精判</span>
          <span style="font-size:var(--fs-caption);color:var(--text3)">需理解句意，由大模型按封闭判据判定 · 只出建议、不自动改</span>
          <button class="btn btn-secondary" style="margin-left:auto;font-size:var(--fs-caption)"
            @click="qa.runJudge(text.value)" :disabled="qa.judgeLoading.value || !text.value.trim()">
            <span class="loading" v-if="qa.judgeLoading.value"></span>{{ qa.judgeLoading.value ? '判读中…' : '开始精判' }}
          </button>
        </div>
        <div v-if="qa.judgeError.value" style="color:var(--red);font-size:var(--fs-sub);margin-top:8px">{{
          qa.judgeError.value }}</div>
        <div v-for="r in qa.judgeResults.value" :key="r.task" class="judge-result" style="margin-top:10px">
          <div style="font-weight:600;font-size:var(--fs-sub)">{{ r.label }}</div>
          <div v-if="!r.ok" style="font-size:var(--fs-sub);color:var(--text3);margin-top:4px">⚠ {{ r.error || '未完成判读' }}
          </div>
          <div v-else>
            <div style="font-size:var(--fs-sub);margin-top:4px">
              <span class="hit-badge" :class="r.verdict === '是' ? 'B' : 'A'">{{ r.verdict === '是' ? '疑似' : '未见'
                }}</span>
              <span style="color:var(--text2)">{{ r.reason }}</span>
            </div>
            <div v-if="r.suggestions.length" style="margin-top:6px">
              <div class="judge-suggestion" v-for="(s, i) in r.suggestions" :key="i">
                <span class="suggestion-tag">建议{{ i + 1 }}</span>{{ s }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="result-card" v-if="polished.value">
        <div class="compare-view">
          <div class="compare-col">
            <div class="label before">润色前</div>
            <div class="content" v-html="highlightedBefore"></div>
          </div>
          <div class="compare-col">
            <div class="label after">润色后</div>
            <div class="content" v-html="highlightedAfter"></div>
          </div>
        </div>
        <div style="margin-top:10px;font-size:var(--fs-sub);color:var(--text2)">
          共 {{ changes.value.length }} 处改动，{{ safetyFailures.value.length }} 处安全检查未通过
        </div>
      </div>

      <!-- 按等级分组展示命中项：没命中的等级不显示 -->
      <div class="result-card level-group" v-for="grp in groupedHits" :key="grp.level" :class="'lv-' + grp.level">
        <div class="level-group-head">
          <span class="hit-badge" :class="grp.level" :style="hitBadgeStyle(grp.level)">{{ LEVEL_ICON[grp.level] }} {{
            grp.level }}</span>
          <span class="level-group-title">{{ LEVEL_NAME[grp.level] }}</span>
          <span class="level-group-count">{{grp.groups.reduce((n, g) => n + g.hits.length, 0)}} 处</span>
        </div>
        <div class="level-rule" v-for="g in grp.groups" :key="g.rid">
          <div class="level-rule-name">{{ g.rid }} · {{ g.hits[0].strategy }}</div>
          <div class="hit-item" v-for="h in g.hits" :key="h.span[0] + h.match">
            <div class="hit-info">
              <span class="excerpt">{{ h.match }}</span>
              <div class="plain" v-if="h.plain">💡 {{ h.plain }}</div>
              <div class="note" v-if="h.action === 'exempt'">⚠ {{ h.exempt_reason }}</div>
              <details class="evidence-details" v-if="h.evidence">
                <summary>查看研究依据</summary>
                <div class="evidence">📊 {{ h.evidence }}</div>
              </details>
            </div>
          </div>
        </div>
      </div>

      <!-- C 级「只报告」：整篇分布指标，没有具体命中位置，按规则逐项列出实测值 -->
      <div class="result-card level-group lv-C" v-if="cItems && cItems.value && cItems.value.length">
        <div class="level-group-head">
          <span class="hit-badge C" :style="hitBadgeStyle('C')">📊 C</span>
          <span class="level-group-title">只报告</span>
          <span class="level-group-count">{{ cItems.value.length }} 项</span>
        </div>
        <div class="level-rule" v-for="it in cItems.value" :key="it.rid">
          <div class="level-rule-name">{{ it.rid }} · {{ it.strategy }}</div>
          <div class="hit-item">
            <div class="hit-info">
              <span class="excerpt">{{ it.label }}
                <strong style="font-weight:700;color:var(--text)">{{ it.display }}</strong><span v-if="it.ref">（人类参考 {{
                  it.ref }}）</span></span>
              <div class="plain" v-if="it.plain">💡 {{ it.plain }}</div>
              <details class="evidence-details" v-if="it.evidence">
                <summary>查看研究依据</summary>
                <div class="evidence">📊 {{ it.evidence }}</div>
              </details>
            </div>
          </div>
        </div>
      </div>

      <div class="x-block" v-if="totalLevel('X')">
        <h3>以下特征经反复比对不是 AI 味，系统故意不修改</h3>
        <div class="x-item" v-for="rule in xRules.value" :key="rule.id">
          <strong>{{ rule.id }} · {{ rule.strategy }}</strong><br>
          <span v-if="rule.plain">💡 {{ rule.plain }}</span><br>
          <details v-if="rule.evidence" class="evidence-details">
            <summary>查看研究依据</summary>
            <span class="flip">{{ rule.evidence }}</span>
          </details>
        </div>
      </div>

      <div class="result-card" v-if="safetyFailures.value.length" style="border-left:3px solid var(--red)">
        <div style="font-weight:600;color:var(--red);margin-bottom:6px">安全检查未通过，已保留原文</div>
        <div v-for="f in safetyFailures.value" style="font-size:var(--fs-sub);padding:4px 0">{{ f.strategy }}：{{
          f.reason }}</div>
      </div>
    </template>
  </div>
</template>