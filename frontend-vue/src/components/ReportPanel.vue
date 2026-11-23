<script setup>
const props = defineProps({
  report: Object,
  polished: Object,
  changes: Object,
  safetyFailures: Object,
  text: Object,
  totalLevel: Function,
  summaryC: Object,
  xRules: Object,
  hitBadgeStyle: Function,
});
</script>

<template>
  <div v-if="report.value">
    <div class="stat-bar">
      <span class="stat-tag A" v-if="totalLevel('A')">A级 {{ totalLevel('A') }}处</span>
      <span class="stat-tag B" v-if="totalLevel('B')">B级 {{ totalLevel('B') }}处</span>
      <span class="stat-tag C" v-if="report.value.summary.C">C级 {{ summaryC.value }}项</span>
      <span class="stat-tag F" v-if="totalLevel('F')">F级 {{ totalLevel('F') }}处</span>
      <span class="stat-tag X" v-if="totalLevel('X')">X级 {{ totalLevel('X') }}处已保护</span>
      <span class="stat-tag H" v-if="totalLevel('H')">H级 {{ totalLevel('H') }}处待人审</span>
    </div>

    <div class="result-card" v-if="polished.value">
      <div class="compare-view">
        <div class="compare-col">
          <div class="label before">润色前</div>
          <div class="content">{{ text.value }}</div>
        </div>
        <div class="compare-col">
          <div class="label after">润色后</div>
          <div class="content">{{ polished.value }}</div>
        </div>
      </div>
      <div style="margin-top:10px;font-size:0.857rem;color:var(--text2)">
        共 {{ changes.value.length }} 处改动，{{ safetyFailures.value.length }} 处安全检查未通过
      </div>
    </div>

    <template v-for="(hits, rid) in report.value.hits" :key="rid">
      <div class="result-card" v-if="hits.length">
        <div style="font-weight:600;font-size:0.929rem;margin-bottom:6px">{{ rid }} · {{ hits[0].strategy }}</div>
        <div class="hit-item" v-for="h in hits" :key="h.span[0] + h.match">
          <span class="hit-badge" :class="h.level" :style="hitBadgeStyle(h.level)">{{ h.level }}</span>
          <div class="hit-info">
            <span class="excerpt">{{ h.match }}</span>
            <div class="evidence">📊 {{ h.evidence }}</div>
            <div class="note" v-if="h.action === 'exempt'">⚠ {{ h.exempt_reason }}</div>
          </div>
        </div>
      </div>
    </template>

    <div class="x-block" v-if="totalLevel('X')">
      <h3>以下特征经 270 对配对复测方向反转或净零，系统故意不修改</h3>
      <div class="x-item" v-for="rule in xRules.value" :key="rule.id">
        <strong>{{ rule.id }} · {{ rule.strategy }}</strong><br>
        <span class="flip">{{ rule.evidence }}</span><br>
        <span style="font-size:0.786rem">{{ rule.note }}</span>
      </div>
    </div>

    <div class="result-card" v-if="safetyFailures.value.length" style="border-left:3px solid var(--red)">
      <div style="font-weight:600;color:var(--red);margin-bottom:6px">安全检查未通过，已保留原文</div>
      <div v-for="f in safetyFailures.value" style="font-size:0.857rem;padding:4px 0">{{ f.strategy }}：{{ f.reason }}</div>
    </div>
  </div>
</template>
