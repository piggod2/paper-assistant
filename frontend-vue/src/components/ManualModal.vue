<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps({
  open: Boolean,
});
const emit = defineEmits(['close']);

// 关闭：点遮罩 / 点 ✕ / 按 Esc
function close() {
  emit('close');
}

function onKeydown(e) {
  if (e.key === 'Escape') close();
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown);
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div class="manual-mask" v-if="open" @click.self="close">
      <div class="manual-modal" role="dialog" aria-label="使用手册" aria-modal="true">
        <header class="manual-head">
          <div>
            <h2 class="manual-title">📖 论文智助 · 使用手册</h2>
            <p class="manual-sub">不替你改写，替你揪出 AI 味</p>
          </div>
          <button type="button" class="manual-close" @click="close" aria-label="关闭">✕</button>
        </header>

        <div class="manual-body">
          <!-- 一、这是什么 -->
          <section class="manual-sec">
            <h3>一、这是什么</h3>
            <p>论文智助是一款面向论文写作的「去 AI 味」工具，做三件事：<strong>检测</strong>（找出 AI 生成特征）、<strong>润色</strong>（按规则改掉）、<strong>辅助</strong>（翻译 + 找文献）。</p>
            <p>判断依据来自一套经两轮对照研究的规则集（629 篇不配对 + 270 对配对复测，约 520 万汉字），每个提示都带研究依据。</p>
          </section>

          <!-- 二、快速上手 -->
          <section class="manual-sec">
            <h3>二、快速上手（三步）</h3>
            <div class="step">
              <span class="step-num">1</span>
              <div><strong>把文字放进来</strong>：粘贴论文段落（中英文均可）或拖入 <code>.txt</code> / <code>.md</code> 文件。</div>
            </div>
            <div class="step">
              <span class="step-num">2</span>
              <div><strong>选一个按钮</strong>：</div>
            </div>
            <table class="manual-table">
              <thead><tr><th>按钮</th><th>作用</th></tr></thead>
              <tbody>
                <tr><td>✨ 检测并润色</td><td>先检测再自动改掉（最常用）</td></tr>
                <tr><td>🔍 只检测</td><td>只出报告，不动文字</td></tr>
                <tr><td>🚀 一键全流程</td><td>翻译 → 找文献 → 润色</td></tr>
                <tr><td>🌐 中英互译</td><td>只翻译</td></tr>
                <tr><td>📚 找相关文献</td><td>只在 arXiv 检索</td></tr>
              </tbody>
            </table>
            <div class="step">
              <span class="step-num">3</span>
              <div><strong>看结果</strong>：润色结果以前后对比展示，改动高亮；检测报告按等级分组；左侧浮动目录可快速跳转。</div>
            </div>
          </section>

          <!-- 三、检测级别 -->
          <section class="manual-sec">
            <h3>三、检测级别（核心概念）</h3>
            <table class="manual-table">
              <thead><tr><th>等级</th><th>名称</th><th>含义</th><th>自动改</th></tr></thead>
              <tbody>
                <tr><td>🔴 A</td><td>机械改</td><td>固定句式、标点问题</td><td class="c-yes">会</td></tr>
                <tr><td>🟡 B</td><td>建议改</td><td>需调句子结构，建议确认</td><td class="c-mid">视强度</td></tr>
                <tr><td>📊 C</td><td>只报告</td><td>整篇分布特征</td><td class="c-no">不改</td></tr>
                <tr><td>🔍 F</td><td>指纹</td><td>破折号、分号等标点习惯</td><td class="c-mid">视强度</td></tr>
                <tr><td>🛡️ X</td><td>永不改</td><td>研究证明不是 AI 味</td><td class="c-no">故意不改</td></tr>
                <tr><td>👁️ H</td><td>人审区</td><td>比喻贴切度需人判断</td><td class="c-no">只列出</td></tr>
              </tbody>
            </table>
            <p class="manual-note">⚠️ <strong>X 级（永不改）和 C 级（只报告）是锁定的</strong>，左侧「检测级别」里不能勾选——锁住是为了防止误关重要提示。</p>
          </section>

          <!-- 四、左侧栏设置 -->
          <section class="manual-sec">
            <h3>四、左侧栏设置</h3>
            <p><strong>检测级别</strong>：勾选要检测的等级，A/B/F 默认开，C/X 锁定。</p>
            <p><strong>改写强度</strong>：保守（仅 A）/ 标准（A+B+F）/ 激进（A+B+F+B6）。</p>
            <p><strong>外观</strong>：主题（浅色/深色/护眼/森林/午夜）、字号、标题字体（楷体/黑体）。</p>
            <p><strong>AI 头像</strong>：选表情或自定义 1~2 字符。<strong>称呼</strong>：填名字，智能体会用它称呼你。</p>
          </section>

          <!-- 五、右侧栏 -->
          <section class="manual-sec">
            <h3>五、右侧栏功能</h3>
            <p><strong>撤销润色</strong>一键退回改前；<strong>分享</strong>生成链接（7 天有效）。</p>
            <p>文献可点星标<strong>收藏</strong>，检测/润色留<strong>历史</strong>，均跨会话保留。</p>
          </section>

          <!-- 六、小功能 -->
          <section class="manual-sec">
            <h3>六、好用的小功能</h3>
            <p><strong>浮动目录</strong>：左栏与主区间的圆点目录，高亮当前位置，点击平滑跳转；检测结果下细分到等级，没命中不显示。</p>
            <p><strong>结果收起</strong>：点报告顶部「收起 ▲」，结果收成一条摘要条，再点展开，数据不丢。</p>
            <p><strong>智能体问答</strong>：右上角 💬 打开对话窗口，针对当前文本提问。</p>
          </section>

          <!-- 七、FAQ -->
          <section class="manual-sec">
            <h3>七、常见问题</h3>
            <div class="faq">
              <p class="faq-q">Q：有些项没被改，是不是坏了？</p>
              <p class="faq-a">A：X 级是研究证明"不是 AI 味"的特征，故意保留；C 级是整篇分布指标，不能改。这是特性。</p>
            </div>
            <div class="faq">
              <p class="faq-q">Q：润色会不会改掉原意？</p>
              <p class="faq-a">A：不会。遵循"信息守恒"，每个改动都能对应原文出处。B 级建议改项建议人工确认。</p>
            </div>
            <div class="faq">
              <p class="faq-q">Q：翻译和找文献有时用不了？</p>
              <p class="faq-a">A：润色检测完全离线；翻译、检索、问答、分享需联网配置。</p>
            </div>
            <div class="faq">
              <p class="faq-q">Q：数据会外传吗？</p>
              <p class="faq-a">A：润色检测走本地规则引擎，不上传第三方；仅翻译/检索/问答/分享联网。</p>
            </div>
          </section>

          <!-- 八、小贴士 -->
          <section class="manual-sec">
            <h3>八、小贴士</h3>
            <ul class="manual-tips">
              <li>先「只检测」看清问题，再决定是否「检测并润色」。</li>
              <li>改写强度非必要别拉满，标准档最稳。</li>
              <li>读一读报告里"这些不是 AI 味"的说明，能帮你建立正确判断标准。</li>
            </ul>
          </section>

          <p class="manual-foot">规则集基于 lieflat-less-ai-tone（CC BY-NC 4.0），本项目为非商业教学演示用途。</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>
