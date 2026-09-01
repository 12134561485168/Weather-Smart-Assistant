<template>
  <article class="report" :class="{ compact }">
    <div class="report-edge" aria-hidden="true"></div>

    <header class="report-head">
      <span class="stamp">晴雨知心 · 气象播报</span>
      <span class="count mono">{{ cards.length }} 项</span>
    </header>

    <!-- 地点 + 时间已由外层「气象播报单」面板标题展示，卡片内不再重复 -->
    <div class="card-grid">
      <div
        v-for="(c, i) in cards"
        :key="c.key"
        class="card"
        :class="c.cls"
        :style="{ '--d': i * 80 + 'ms' }"
      >
        <span class="card-top">
          <span class="card-icon">
            <svg v-if="c.icon === 'clock'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3.2 2" />
            </svg>
            <svg v-else-if="c.icon === 'spark'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3c.6 4.5 2.5 6.9 7 7-4.5.6-6.4 2.5-7 7-.6-4.5-2.5-6.4-7-7 4.5-.6 6.4-2.5 7-7Z" />
            </svg>
            <svg v-else-if="c.icon === 'cloud'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6.5 16.5a4 4 0 1 1 .8-7.9 5.5 5.5 0 0 1 10.2 3.3 3.4 3.4 0 0 1-.5 4.6H6.5Z" />
              <path d="M8.5 19.5h7" />
            </svg>
            <svg v-else-if="c.icon === 'shirt'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M8.5 4 5 7l2.5 3v10h9V10L19 7l-3.5-3A3 3 0 0 1 8.5 4Z" />
              <path d="M12 4v3" />
            </svg>
            <svg v-else-if="c.icon === 'car'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 17v-3.5l2-5h12l2 5V17" />
              <path d="M4 17h16" />
              <circle cx="7" cy="17.5" r="1.8" />
              <circle cx="17" cy="17.5" r="1.8" />
            </svg>
            <svg v-else-if="c.icon === 'leaf'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 19.5C5 9 12 4 20 4c0 8-5 15-15 15.5Z" />
              <path d="M5 19.5c4-6.5 8.5-10 12.5-11.5" />
            </svg>
          </span>
          <h4 class="card-label">{{ c.label }}</h4>
        </span>
        <p class="card-value" :class="{ mono: c.key === 'time' }">{{ c.value }}</p>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../markdown.js'

// Result 结构化数据：time / summary / weather / clothing_advice / travel_tips / healthy_tips
// 每个字段渲染为一张小卡片
const props = defineProps({
  data: { type: Object, required: true },
  compact: { type: Boolean, default: false } // 紧凑模式：用于左侧窄侧栏
})

const FIELDS = [
  { key: 'summary',         label: '天气总结', icon: 'spark', cls: 'c-summary' },
  { key: 'weather',         label: '天气详情', icon: 'cloud', cls: 'c-weather' },
  { key: 'clothing_advice', label: '穿衣建议', icon: 'shirt', cls: 'c-clothing' },
  { key: 'travel_tips',     label: '出行建议', icon: 'car',   cls: 'c-travel' },
  { key: 'healthy_tips',    label: '健康防护', icon: 'leaf',  cls: 'c-health' }
]

// 地点 + 时间已由外层「气象播报单」面板标题展示，卡片内不再渲染
const cards = computed(() =>
  FIELDS.filter((f) => {
    const v = props.data[f.key]
    return v !== undefined && v !== null && String(v).trim() !== ''
  }).map((f) => ({ ...f, value: String(props.data[f.key]) }))
)
</script>

<style scoped>
.report {
  position: relative;
  width: 100%;
  max-width: 720px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.035));
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 22px 24px 24px;
  overflow: hidden;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
  animation: rise 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.1) both;
}

/* 顶部极光描边 */
.report-edge {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--sky), var(--sun), transparent);
}

.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.stamp {
  font-size: 11px;
  letter-spacing: 0.3em;
  color: var(--sun);
  border: 1px solid rgba(242, 180, 92, 0.45);
  border-radius: 999px;
  padding: 4px 12px;
}

.count {
  font-size: 11px;
  color: var(--ink-faint);
}

/* 小卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.card {
  background: var(--card);
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  padding: 14px 15px;
  opacity: 0;
  animation: rise 0.45s cubic-bezier(0.2, 0.9, 0.3, 1.1) forwards;
  animation-delay: var(--d);
  transition: transform 0.2s, border-color 0.2s, background 0.2s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card:hover {
  transform: translateY(-3px);
  border-color: var(--line);
  background: var(--card-strong);
}

/* 卡片上部：图标 + 标题横向并排 */
.card-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-label {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.18em;
  color: var(--ink-dim);
}

.card-value {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
}

.card-value.mono {
  font-family: var(--mono);
  font-size: 12.5px;
}

/* Markdown 内容：子元素由 v-html 生成、不带 scoped 属性，需用 :deep() 命中 */
.card-value.markdown {
  white-space: normal;
}

.card-value.markdown :deep(p) {
  margin: 0.3em 0;
}

.card-value.markdown :deep(> :first-child) {
  margin-top: 0;
}

.card-value.markdown :deep(> :last-child) {
  margin-bottom: 0;
}

.card-value.markdown :deep(ul),
.card-value.markdown :deep(ol) {
  margin: 0.3em 0;
  padding-left: 1.4em;
}

.card-value.markdown :deep(li) {
  margin: 0.1em 0;
}

.card-value.markdown :deep(strong) {
  color: #fff;
  font-weight: 700;
}

/* 图标 */
.card-icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  align-items: center;
  justify-content: center;
}

.card-icon svg {
  width: 18px;
  height: 18px;
}

.c-time .card-icon     { background: rgba(124, 196, 242, 0.14);  color: var(--sky); }
.c-summary .card-icon  { background: rgba(242, 180, 92, 0.14);   color: var(--sun); }
.c-weather .card-icon  { background: rgba(124, 196, 242, 0.14);  color: var(--sky); }
.c-clothing .card-icon { background: rgba(242, 180, 92, 0.14);   color: var(--sun); }
.c-travel .card-icon   { background: rgba(124, 196, 242, 0.14);  color: var(--sky); }
.c-health .card-icon   { background: rgba(94, 234, 212, 0.14);   color: var(--rain); }

/* 主题色强调条 */
.card::after {
  content: "";
  position: absolute;
  top: 0;
  left: 14px;
  right: 14px;
  height: 2px;
  border-radius: 0 0 2px 2px;
  opacity: 0.8;
}

.card { position: relative; }
.c-time::after,
.c-weather::after,
.c-travel::after { background: var(--sky); }
.c-summary::after,
.c-clothing::after { background: var(--sun); }
.c-health::after { background: var(--rain); }

@keyframes rise {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ---------- 紧凑模式（左侧窄侧栏） ---------- */
.report.compact {
  padding: 14px 12px 16px;
  border-radius: 14px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.32);
}

.report.compact .report-head {
  margin-bottom: 10px;
}

.report.compact .stamp {
  font-size: 9.5px;
  padding: 3px 9px;
  letter-spacing: 0.2em;
}

.report.compact .count {
  font-size: 10px;
}

/* 单列卡片：标题 + 图标在上方，文字在下方 */
.report.compact .card-grid {
  grid-template-columns: 1fr;
  gap: 8px;
}

.report.compact .card {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 9px 12px;
  border-radius: 11px;
}

.report.compact .card-top {
  gap: 8px;
}

.report.compact .card-label {
  font-size: 11px;
  letter-spacing: 0.13em;
  flex: 0 0 auto;
}

.report.compact .card-value {
  font-size: 12px;
  line-height: 1.6;
}

.report.compact .card-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  flex: 0 0 auto;
}

.report.compact .card-icon svg {
  width: 14px;
  height: 14px;
}

@media (max-width: 620px) {
  .report { padding: 18px 16px 20px; }
  .card-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 420px) {
  .card-grid { grid-template-columns: 1fr; }
}
</style>