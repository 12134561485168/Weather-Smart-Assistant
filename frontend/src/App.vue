<template>
  <div class="app">
    <!-- 侧栏 · 气象控制台 -->
    <aside class="console">
      <div class="brand">
        <div class="brand-glyph" aria-hidden="true">
          <svg viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="18" stroke="currentColor" stroke-width="1.4" opacity="0.35" />
            <path d="M10 23a4.5 4.5 0 1 1 .9-8.9A6 6 0 0 1 27.8 17 3.8 3.8 0 0 1 27 24.5H10Z" fill="currentColor" opacity="0.22" />
            <circle cx="23.5" cy="14" r="3.4" fill="currentColor" opacity="0.85" />
          </svg>
        </div>
        <div>
          <h1>晴雨知心</h1>
          <p>天气播报助手</p>
        </div>
      </div>

      <dl class="telemetry">
        <div class="telemetry-row">
          <dt>链路</dt>
          <dd><span class="dot" :class="linkState"></span>{{ linkState === 'ok' ? '已连接' : '待命' }}</dd>
        </div>
        <div class="telemetry-row">
          <dt>状态</dt>
          <dd>{{ loading ? '生成中…' : '就绪' }}</dd>
        </div>
      </dl>

      <!-- 气象播报单：结构化天气卡片渲染在链路/状态下方，不在消息流内 -->
      <aside class="weather-panel">
        <div class="panel-head">
          <span class="panel-title">气象播报单</span>
          <span v-if="lastReport" class="panel-situ">{{ lastReport.address }} · {{ lastReport.time }}</span>
        </div>
        <div v-if="lastReport" class="panel-body" :key="lastReportKey">
          <WeatherReport :data="lastReport" compact />
        </div>
        <p v-else class="panel-empty">回答中出现天气播报时，卡片将展示在这里</p>
      </aside>

      <button class="ghost-btn" @click="startNewSession">新会话</button>

      <footer class="console-foot">MCP · LangGraph · Vue</footer>
    </aside>

    <!-- 主区 · 对话 -->
    <main class="stage">
      <header class="stage-head">
        <div class="stage-head-left">
          <span class="going" :class="{ on: !loading }"></span>
          <span>{{ loading ? '正在查询天气…' : '输入地点与时间，即可查询天气' }}</span>
        </div>
        <div class="stage-head-right">
          <span class="sun-mark">&#9727;</span>
        </div>
      </header>

      <div class="stage-body">
        <div class="messages" ref="scroller">
        <!-- 开场问候（装饰性，不参与轮次） -->
        <div class="msg assistant">
          <div class="assistant-bubble plain">
            我是「晴雨知心」。告诉我地点与时间——例如「北理工明天天气如何」，或「这周哪天适合爬山」。支持多轮追问，可随时重新回答、编辑与切换分支。
          </div>
        </div>

        <!-- 分支链展示：只渲染当前选中的变体及其派生，切换变体时后续消息自动跟随 -->
        <template v-for="(t, k) in chain" :key="t.qid">
          <div class="msg user">
            <div class="user-block">
              <div v-if="editingQid === t.qid" class="user-bubble edit-box">
                <textarea
                  v-model="editDraft"
                  rows="1"
                  @keydown.enter.exact.prevent="saveEdit(t)"
                  @input="autosize"
                ></textarea>
                <div class="edit-actions">
                  <button class="ghost-mini ok" :disabled="loading" @click="saveEdit(t)">保存</button>
                  <button class="ghost-mini" :disabled="loading" @click="editingQid = null">取消</button>
                </div>
              </div>
              <div v-else class="user-bubble" :key="t.variants.length ? 'v' + t.active : 'pend'">{{ t.pending ? t.question : t.variants[t.active].question }}</div>
              <div class="user-tools">
                <!-- 问题版本切换条（编辑产生的分支）：固定在消息下方，与回答切换条彼此独立 -->
                <template v-if="versionTotal(t) >= 2">
                  <button
                    class="page-btn"
                    :disabled="!versionReach(t, -1)"
                    @click="pageVersion(t, -1)"
                    aria-label="上一个问题版本"
                  >&#8249;</button>
                  <span class="page-ind">{{ versionCount(t).pos }}/{{ versionCount(t).total }}</span>
                  <button
                    class="page-btn"
                    :disabled="!versionReach(t, 1)"
                    @click="pageVersion(t, 1)"
                    aria-label="下一个问题版本"
                  >&#8250;</button>
                </template>
                <div class="msg-actions">
                  <button class="revoke-btn" :disabled="loading || !t.variants.length" @click="startEdit(t)">编辑</button>
                  <button class="revoke-btn" :disabled="loading" @click="revokeNode(t)">撤销</button>
                </div>
              </div>
            </div>
          </div>

          <div class="msg assistant">
            <div class="assistant-block">
              <template v-if="t.pending">
                <div class="assistant-bubble typing"><i></i><i></i><i></i></div>
              </template>
              <template v-else-if="t.variants.length">
                <template v-if="t.variants[t.active].pending">
                  <div class="assistant-bubble typing"><i></i><i></i><i></i></div>
                </template>
                <template v-else>
                  <div class="assistant-content" :key="t.variants[t.active].cid || (t.variants.length + '-' + t.active)">
                    <template v-for="(m, mi) in t.variants[t.active].msgs" :key="mi">
                        <div class="assistant-bubble plain">{{ m.content }}</div>
                      </template>
                  </div>
                </template>

                <!-- 回答切换条（初始回答/重新回答的分支）：固定在 AI 回答内容下方，独立于问题版本切换条 -->
                <div class="variant-bar">
                  <template v-if="answerCount(t).total >= 2">
                    <button
                      class="page-btn"
                      :disabled="!answerReach(t, -1)"
                      @click="pageAnswer(t, -1)"
                      aria-label="上一个回答"
                    >&#8249;</button>
                    <span class="page-ind">{{ answerCount(t).pos }}/{{ answerCount(t).total }}</span>
                    <button
                      class="page-btn"
                      :disabled="!answerReach(t, 1)"
                      @click="pageAnswer(t, 1)"
                      aria-label="下一个回答"
                    >&#8250;</button>
                  </template>
                  <button
                    class="continue-btn"
                    :disabled="loading || !!t.variants[t.active].pending"
                    @click="reanswer(t)"
                  >重新回答</button>
                </div>
              </template>
            </div>
          </div>
        </template>

        <div v-if="error" class="error-banner">{{ error }}</div>
        <transition name="fade">
          <div v-if="toast" class="toast">{{ toast }}</div>
        </transition>
        </div>
      </div>

      <form class="composer" @submit.prevent="send">
        <textarea
          v-model="draft"
          rows="1"
          placeholder="输入地点与时间，例如：北理工明天天气如何？"
          @keydown.enter.exact.prevent="send"
          @input="autosize"
        ></textarea>
        <button type="submit" class="send-btn" :disabled="!draft.trim() || loading">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19V5" />
            <path d="m5 12 7-7 7 7" />
          </svg>
          发送
        </button>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, reactive, nextTick, watch, onMounted } from 'vue'
import WeatherReport from './components/WeatherReport.vue'

// ============================= 状态 =============================
// 消息以「分支树」组织：roots 为根列表，每个节点 = 一轮问答。
// node = {
//   qid, question, sourceCid,   // sourceCid = 提问前的检查点（重新回答/编辑/撤销的基准）
//   variants: [ { cid, msgs, children: [node...] } ],  // 同一问题的多个回答；派生问题挂在各自变体下
//   active,                     // 当前展示哪个变体（切换时其后续消息自动跟随）
//   pending,                    // 该轮回答生成中
// }
const roots = ref([])

// 当前展示的「分支链」：沿每个节点的 active 变体向下遍历得到
const chain = computed(() => {
  const out = []
  const walk = (nodes) => {
    for (const n of nodes) {
      out.push(n)
      const v = n.variants[n.active]
      if (v && v.children && v.children.length) walk(v.children)
    }
  }
  walk(roots.value)
  return out
})

// 当前展示链中最近一处的天气播报（切换分支/变体时自动跟随面板）
const lastReport = computed(() => {
  const arr = chain.value
  for (let i = arr.length - 1; i >= 0; i--) {
    const v = arr[i].variants[arr[i].active]
    if (v && v.structured) return v.structured
  }
  return null
})

// 面板 key：变体内容变化时重播入场动画
const lastReportKey = computed(() =>
  lastReport.value ? JSON.stringify(lastReport.value) : 'none'
)

const draft = ref('')
const editDraft = ref('') // 编辑框中的新问题文本
const editingQid = ref(null) // 正在编辑的节点 qid；null = 无
const toast = ref('') // 轻提示（如「内容未修改」），短暂展示后自动消失
let toastTimer = null
const loading = ref(false)
const error = ref('')
const linkState = ref('idle')
const scroller = ref(null)

// 会话 ID 随机生成，不对外展示，仅用于后端多轮上下文隔离
function newThreadId() {
  return 'web-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}
const threadId = ref(newThreadId())
let qidSeq = 0

// 后端可能返回 Result 字典（对象），也可能返回 JSON 字符串，统一识别
function tryParseStructured(r) {
  if (r !== null && typeof r === 'object' && !Array.isArray(r)) {
    return r.summary != null || r.weather != null || r.time != null ? r : null
  }
  if (typeof r === 'string') {
    try {
      const o = JSON.parse(r)
      if (o !== null && typeof o === 'object' && !Array.isArray(o)) {
        return o.summary != null || o.weather != null || o.time != null ? o : null
      }
    } catch {
      /* 不是 JSON，按普通文本处理 */
    }
  }
  return null
}

function scrollToBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

// 短暂展示轻提示（保存无变化、内容为空等场景给用户明确反馈）
function flash(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 1800)
}

function autosize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

// 当前展示链的尾部回答变体 = 新问题的续接点；全新会话返回 null
function tailVariant() {
  const last = chain.value[chain.value.length - 1]
  if (!last) return null
  return last.variants[last.active] || null
}

// 从分支树上移除某节点（撤销 / 发送失败回滚）
function removeNode(node) {
  const walk = (nodes) => {
    for (let i = 0; i < nodes.length; i++) {
      if (nodes[i] === node) {
        nodes.splice(i, 1)
        return true
      }
      for (const v of nodes[i].variants) {
        if (v.children && v.children.length && walk(v.children)) return true
      }
    }
    return false
  }
  walk(roots.value)
}

// 变体携带 question：用户消息与回答作为一对整体翻页切换（编辑/重新回答产生新版本）
// g 记录「问题版本」分组：每次编辑产生新分组（+1），重新回答沿用当前分组；
// 翻页时整个消息的全部变体统一编页，分组信息仅作为溯源元数据保留。
// 结构化天气数据独立存在 structured 字段，供左侧「气象播报单」面板渲染，不进入消息流
function buildVariant(data, question, origin, g) {
  const structured = tryParseStructured(data.result)
  const msgs = structured
    ? [{ role: 'assistant', content: '已为你查询到对应天气，气象播报单见左侧面板。' }]
    : [{ role: 'assistant', content: String(data.result ?? '（未获取到有效回复）') }]
  return { g, origin, question, cid: data.after_checkpoint_id ?? null, msgs, structured, children: [], pending: false }
}

async function ask(checkpoint_id, question) {
  const res = await fetch('/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: threadId.value, question, checkpoint_id }),
  })
  if (!res.ok) throw new Error('后端返回异常（HTTP ' + res.status + '）')
  return res.json()
}

// ============================= 发送 =============================
// 续接点 = 当前展示分支的尾部回答（切换变体即切换续接点）；全新会话为 null
async function send() {
  const q = draft.value.trim()
  if (!q || loading.value) return
  loading.value = true
  error.value = ''
  draft.value = ''

  const tail = tailVariant()
  const src = tail ? tail.cid : null
  // 节点必须用 reactive 创建：回答返回后要对 variants/pending 等做增量更新，
  // 若用普通对象直接推入 ref 数组，后续变更绕过响应式系统，左侧气象播报单将不会更新
  const node = reactive({
    qid: 'q' + ++qidSeq,
    question: q,
    sourceCid: src,
    variants: [],
    active: 0,
    pending: true, // 用户消息立即上屏，回答生成中
  })
  if (tail) tail.children.push(node)
  else roots.value.push(node)
  scrollToBottom()

  try {
    const data = await ask(src, q)
    linkState.value = 'ok'
    node.pending = false
    node.variants.push(buildVariant(data, q, 'send', 0))
    node.active = 0
  } catch (e) {
    removeNode(node)
    linkState.value = 'down'
    error.value = '无法连接到后端：' + (e.message || '未知错误')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// ============================= 重新回答 =============================
// 从该问题提问前的检查点重新生成：新回答框立即出现（生成动画），完成后填充；
// 旧回答保留在「回答 n」里，可随时切回，其后续消息随切换自动跟随。
async function reanswer(node) {
  if (!node || !node.variants.length || loading.value) return
  loading.value = true
  error.value = ''
  // 用「当前展示版本」的问题文本重新生成（翻页切换过的版本以 active 为准）
  const srcQ = (node.variants[node.active] && node.variants[node.active].question) || node.question
  // 重新回答沿用当前问题版本的分组（不新增问题版本）
  const g = (node.variants[node.active] && node.variants[node.active].g) ?? 0
  const idx = node.variants.length
  node.variants.push({ g, origin: 'reanswer', question: srcQ, cid: null, msgs: [], children: [], pending: true })
  node.active = idx
  scrollToBottom()
  try {
    // 发送「对应的问题」并从该问题提问前的检查点 fork（sourceCid = 上一个问题回答后的检查点）：
    // AI 保留此前全部问答上下文，仅重新生成本轮回答，旧回答保留为可切换的上一版本
    const data = await ask(node.sourceCid || '__root__', srcQ)
    const v = node.variants[idx]
    const { question, cid, msgs, children, structured } = buildVariant(data, srcQ, 'reanswer', g)
    Object.assign(v, { question, cid, msgs, children, structured, pending: false })
  } catch (e) {
    node.variants.splice(idx, 1) // 生成失败，移除占位回答框
    if (node.active >= node.variants.length) node.active = node.variants.length - 1
    error.value = '重新回答失败：' + (e.message || '未知错误')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// ============================= 编辑 =============================
// 问题文本改为新内容后，以提问前的检查点为基准重新生成，作为新变体（从该位置创建分支）；
// 旧回答及其派生消息存在原变体下，互不污染，可切换回来。
function startEdit(node) {
  if (!node || !node.variants.length) return
  const cur = node.variants[node.active]
  editDraft.value = cur ? cur.question : node.question
  editingQid.value = node.qid
  toast.value = ''
  nextTick(() => scrollToBottom())
}

async function saveEdit(node) {
  const q = editDraft.value.trim()
  if (loading.value) return
  // 空文本：轻提示，不产生分支
  if (!q) {
    flash('问题不能为空')
    return
  }
  // 无论内容是否修改：只要非空就保存并创建新分支（未改动时同样产生一个独立变体）
  loading.value = true
  error.value = ''
  // 编辑产生新的「问题版本」：分组号在当前基础上 +1，使回答计数按问题版本独立统计
  let g = 0
  for (const v of node.variants) g = Math.max(g, v.g ?? 0)
  g += 1
  const idx = node.variants.length
  node.variants.push({ g, origin: 'edit', question: q, cid: null, msgs: [], children: [], pending: true })
  node.active = idx
  editingQid.value = null // 收起编辑框，新回答框立即生成动画
  scrollToBottom()
  try {
    // 发送「修改后的问题」并从该问题提问前的检查点 fork（sourceCid = 上一个问题回答后的检查点），
    // 新分支保留此前全部上下文，仅重算本轮与后续回答
    const data = await ask(node.sourceCid || '__root__', q)
    node.question = q
    const v = node.variants[idx]
    const { question, cid, msgs, children, structured } = buildVariant(data, q, 'edit', g)
    Object.assign(v, { question, cid, msgs, children, structured, pending: false })
  } catch (e) {
    node.variants.splice(idx, 1)
    if (node.active >= node.variants.length) node.active = node.variants.length - 1
    error.value = '编辑失败：' + (e.message || '未知错误')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// ============================= 切换变体：问答两条独立切换轴 =============================
// 「问题版本」与「回答」彼此分开、互不影响：
// - 用户侧切换条 = 问题版本（编辑产生的分支）：按版本总数编页，切到哪个版本就展示该版本的一组回答；
// - AI 侧切换条 = 当前问题版本下的回答（初始回答/重新回答）：按该版本内的回答数编页。
// 两组切换条可同时显示、各自独立翻页；边界禁用：1/N → 左禁，N/N → 右禁。
// 生成中允许切换（纯展示层操作，不影响后台请求），仅编辑/重答/发送等被 loading 锁定。

// g 取值连续（send=0，edit=max+1，reanswer 沿用所在版本），版本总数 = 最大 g + 1
function versionTotal(t) {
  let m = 0
  for (const v of t.variants) m = Math.max(m, v.g ?? 0)
  return m + 1
}
function versionCount(t) {
  const v = t.variants[t.active]
  const g = (v && v.g != null) ? v.g : 0
  return { pos: Math.min(g + 1, versionTotal(t)), total: versionTotal(t) }
}
function versionReach(t, dir) {
  const c = versionCount(t)
  return dir < 0 ? c.pos > 1 : c.pos < c.total
}
// 问题版本切换：跳到 g±1 的版本，尽量保持当前版本内的相对回答位置
function pageVersion(node, dir) {
  if (!node || !node.variants.length) return
  const v = node.variants[node.active]
  const g = (v && v.g != null) ? v.g : 0
  const tg = g + dir
  if (tg < 0 || tg >= versionTotal(node)) return
  const from = [], to = []
  for (let i = 0; i < node.variants.length; i++) {
    const gg = node.variants[i].g ?? 0
    if (gg === g) from.push(i)
    if (gg === tg) to.push(i)
  }
  const rel = Math.max(from.indexOf(node.active), 0)
  node.active = to[Math.min(rel, to.length - 1)]
  scrollToBottom()
}

// 当前版本内的回答：只统计与活动变体同 g 的变体
function answerCount(t) {
  const v = t.variants[t.active]
  const g = (v && v.g != null) ? v.g : 0
  const idx = []
  for (let i = 0; i < t.variants.length; i++) if ((t.variants[i].g ?? 0) === g) idx.push(i)
  return { pos: Math.max(idx.indexOf(t.active) + 1, 1), total: Math.max(idx.length, 1) }
}
function answerReach(t, dir) {
  const c = answerCount(t)
  return dir < 0 ? c.pos > 1 : c.pos < c.total
}
// 回答切换：只在当前问题版本内相邻移动，不影响其他版本
function pageAnswer(node, dir) {
  if (!node || !node.variants.length) return
  const v = node.variants[node.active]
  const g = (v && v.g != null) ? v.g : 0
  const idx = []
  for (let i = 0; i < node.variants.length; i++) if ((node.variants[i].g ?? 0) === g) idx.push(i)
  const pos = idx.indexOf(node.active)
  const next = pos + dir
  if (next < 0 || next >= idx.length) return
  node.active = idx[next]
  scrollToBottom()
}

// ============================= 撤销 =============================
// 删除该问题及其之后的全部分支（所有变体、所有后续），回退到提问前的状态
async function revokeNode(node) {
  if (!node || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/revoke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId.value, checkpoint_id: node.sourceCid || '__root__' }),
    })
    if (!res.ok) throw new Error('撤销失败（HTTP ' + res.status + '）')
    await res.json()
    removeNode(node)
    if (editingQid.value === node.qid) editingQid.value = null
  } catch (e) {
    error.value = '撤销失败：' + (e.message || '未知错误')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function startNewSession() {
  threadId.value = newThreadId()
  roots.value = []
  editingQid.value = null
  error.value = ''
}

watch([chain, loading, error], scrollToBottom)

onMounted(() => scrollToBottom())
</script>

<style scoped>
.app {
  display: flex;
  height: 100%;
  max-width: 1280px;
  margin: 0 auto;
  gap: 20px;
  padding: 20px 20px 20px 24px;
}

/* ---------- 侧栏 ---------- */
.console {
  position: relative;
  width: 260px;
  flex: 0 0 260px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 26px 22px;
  background: var(--card);
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  backdrop-filter: blur(14px);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}

.console::before {
  content: "";
  position: absolute;
  top: 0;
  left: 22px;
  right: 22px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(242, 180, 92, 0.55), transparent);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-glyph {
  width: 46px;
  height: 46px;
  color: var(--sun);
}

.brand h1 {
  margin: 0;
  font-family: var(--serif);
  font-size: 21px;
  letter-spacing: 0.16em;
  font-weight: 700;
}

.brand p {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--ink-faint);
  letter-spacing: 0.3em;
}

.telemetry {
  margin: 0;
  border-top: 1px solid var(--line-soft);
  border-bottom: 1px solid var(--line-soft);
  padding: 14px 0;
  display: grid;
  gap: 10px;
}

.telemetry-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.telemetry-row dt {
  color: var(--ink-faint);
}

.telemetry-row dd {
  margin: 0;
  color: var(--ink-dim);
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-faint);
  box-shadow: 0 0 0 0 rgba(0, 0, 0, 0);
}

.dot.ok {
  background: var(--rain);
  box-shadow: 0 0 10px rgba(94, 234, 212, 0.8);
}

.dot.down {
  background: var(--danger);
  box-shadow: 0 0 10px rgba(244, 143, 177, 0.7);
}

.ghost-btn {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-dim);
  border-radius: 10px;
  padding: 10px;
  font-size: 13px;
  letter-spacing: 0.08em;
  transition: all 0.2s;
}

.ghost-btn:hover {
  color: var(--ink);
  border-color: var(--sun);
  background: rgba(242, 180, 92, 0.08);
}

.console-foot {
  margin-top: auto;
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--ink-faint);
  letter-spacing: 0.18em;
}

/* ---------- 对话主区 ---------- */
.stage {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--card);
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  backdrop-filter: blur(14px);
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22);
}

/* 主区主体：左侧对话流 */
.stage-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* ---------- 侧栏内：气象播报单（位于链路/状态下方，可滚动） ---------- */
.weather-panel {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-head {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.panel-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.26em;
  color: var(--ink-faint);
}

.panel-situ {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-dim);
  letter-spacing: 0.04em;
  word-break: break-word;
}

.panel-body {
  min-width: 0;
}

.panel-empty {
  margin: 0;
  padding: 22px 10px;
  border: 1px dashed var(--line);
  border-radius: 14px;
  text-align: center;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-faint);
}

/* ---------- 优雅滚动条（卡片区 + 对话流） ---------- */
.weather-panel,
.messages {
  scrollbar-width: thin;
  scrollbar-color: rgba(124, 196, 242, 0.38) transparent;
  scrollbar-gutter: stable;
}

.weather-panel::-webkit-scrollbar,
.messages::-webkit-scrollbar {
  width: 6px;
}

.weather-panel::-webkit-scrollbar-track,
.messages::-webkit-scrollbar-track {
  background: transparent;
}

.weather-panel::-webkit-scrollbar-thumb,
.messages::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(124, 196, 242, 0.45), rgba(94, 234, 212, 0.35));
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
}

.weather-panel::-webkit-scrollbar-thumb:hover,
.messages::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(124, 196, 242, 0.75), rgba(94, 234, 212, 0.6));
}

.stage-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 26px;
  height: 56px;
  border-bottom: 1px solid var(--line-soft);
  flex: 0 0 auto;
}

.stage-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
  color: var(--ink-dim);
  letter-spacing: 0.02em;
}

.going {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--sky);
  box-shadow: 0 0 8px rgba(94, 212, 255, 0.35);
}

.going.on {
  animation: pulse 1.2s ease-in-out infinite;
}

.sun-mark {
  color: var(--sun);
  font-size: 20px;
  opacity: 0.75;
}

.messages {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 26px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scroll-behavior: smooth;
}

.msg {
  display: flex;
  max-width: 780px;
}

.msg.user {
  align-self: flex-end;
}

.msg.assistant {
  align-self: flex-start;
}

.user-block {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  max-width: 520px;
}

.user-bubble {
  background: linear-gradient(135deg, rgba(244, 192, 108, 0.92), rgba(214, 138, 48, 0.96));
  color: #1a1204;
  padding: 12px 18px;
  border-radius: 18px 18px 6px 18px;
  font-size: 14.5px;
  line-height: 1.6;
  max-width: 520px;
  box-shadow: 0 8px 20px rgba(242, 180, 92, 0.16);
  animation: rise 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 编辑模式：用户气泡内联输入框 */
.edit-box {
  background: rgba(0, 0, 0, 0.35);
  color: var(--ink);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: 14px 14px 4px 14px;
}

.edit-box textarea {
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink);
  outline: none;
  resize: none;
  min-width: 240px;
}

.edit-box textarea:focus {
  border-color: var(--sun);
  box-shadow: 0 0 0 3px rgba(242, 180, 92, 0.12);
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.ghost-mini {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-dim);
  border-radius: 8px;
  padding: 3px 12px;
  font-size: 12px;
  letter-spacing: 0.06em;
  transition: all 0.2s;
}

.ghost-mini.ok {
  color: var(--sun);
  border-color: var(--sun);
}

.ghost-mini:hover:not(:disabled) {
  color: var(--ink);
  border-color: var(--sun);
  background: rgba(242, 180, 92, 0.08);
}

.ghost-mini:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.msg-actions,
.user-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.revoke-btn {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-faint);
  border-radius: 8px;
  padding: 3px 12px;
  font-size: 12px;
  letter-spacing: 0.06em;
  opacity: 0.7;
  transition: all 0.2s;
}

.revoke-btn:hover:not(:disabled) {
  color: var(--danger);
  border-color: var(--danger);
  opacity: 1;
}

.revoke-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* 回答变体 / 选择续接点 */
.assistant-block {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  max-width: 780px;
}

/* 变体内容随分支切换淡入 */
.assistant-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  animation: rise 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* 操作条默认低饱和，悬停/聚焦时显现（克制 chrome） */
.user-tools,
.variant-bar {
  opacity: 0.45;
  transition: opacity 0.18s ease;
}

.user-block:hover .user-tools,
.user-block:focus-within .user-tools,
.assistant-block:hover .variant-bar {
  opacity: 1;
}

.variant-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

/* 回答版本翻页：左翻 / 右侧 / 页码指示 */
.page-btn {
  width: 28px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-dim);
  border-radius: 8px;
  font-size: 15px;
  line-height: 1;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  color: var(--ink);
  border-color: var(--sun);
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-ind {
  font-family: var(--mono);
  font-size: 11.5px;
  color: var(--ink-dim);
  letter-spacing: 0.04em;
  min-width: 36px;
  text-align: center;
}

.continue-btn {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-faint);
  border-radius: 999px;
  padding: 4px 13px;
  font-size: 11.5px;
  letter-spacing: 0.05em;
  transition: all 0.2s;
}

.continue-btn:hover:not(:disabled) {
  color: var(--ink);
  border-color: var(--sun);
}

.continue-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.assistant-bubble.plain {
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid var(--line-soft);
  border-radius: 6px 18px 18px 18px;
  padding: 14px 18px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
  animation: rise 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.typing {
  display: flex;
  gap: 5px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid var(--line-soft);
  border-radius: 6px 18px 18px 18px;
  align-self: flex-start;
  animation: rise 0.3s ease both;
}

.typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sky);
  animation: bounce 1.2s infinite;
}

.typing i:nth-child(2) { animation-delay: 0.15s; }
.typing i:nth-child(3) { animation-delay: 0.3s; }

.error-banner {
  align-self: center;
  color: var(--danger);
  font-size: 12.5px;
  padding: 8px 15px;
  border: 1px solid rgba(244, 143, 177, 0.28);
  border-radius: 999px;
  background: rgba(244, 143, 177, 0.07);
  animation: rise 0.3s ease both;
}

/* 轻提示：短暂展示「内容未修改」等反馈，吸顶在对话流上方 */
.toast {
  position: sticky;
  top: 10px;
  z-index: 5;
  align-self: center;
  color: var(--sun);
  font-size: 12.5px;
  padding: 7px 16px;
  border: 1px solid rgba(242, 180, 92, 0.38);
  border-radius: 999px;
  background: rgba(242, 180, 92, 0.1);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(8px);
  pointer-events: none;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ---------- 输入区 ---------- */
.composer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 26px 22px;
  border-top: 1px solid var(--line-soft);
  align-items: flex-end;
}

.composer textarea {
  flex: 1;
  resize: none;
  background: rgba(0, 0, 0, 0.26);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 13px 16px;
  font-size: 14.5px;
  line-height: 1.5;
  outline: none;
  max-height: 160px;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.composer textarea:focus {
  border-color: rgba(242, 180, 92, 0.65);
  box-shadow: 0 0 0 3px rgba(242, 180, 92, 0.09);
  background: rgba(0, 0, 0, 0.34);
}

.composer textarea::placeholder {
  color: var(--ink-faint);
}

.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: linear-gradient(135deg, var(--sun), #d98a2b);
  color: #1a1204;
  border: none;
  border-radius: 14px;
  padding: 13px 20px;
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  transition: transform 0.15s, opacity 0.2s, box-shadow 0.2s;
  box-shadow: 0 8px 22px rgba(242, 180, 92, 0.18);
}

.send-btn svg {
  width: 15px;
  height: 15px;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(242, 180, 92, 0.26);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

/* ---------- 动画 ---------- */
@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-5px); opacity: 1; }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.25); opacity: 0.55; }
}

/* ---------- 触屏：无 hover，操作条常显 ---------- */
@media (hover: none) {
  .user-tools,
  .variant-bar {
    opacity: 1;
  }
}

/* ---------- 窄屏 ---------- */
@media (max-width: 860px) {
  .app {
    padding: 10px;
  }
  .console {
    display: none;
  }
  .messages {
    padding: 18px;
  }
}
</style>