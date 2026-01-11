<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type ChatMessage = {
  id: string
  role: string
  content: string
  session_id: string
  created_at: string
  tool_calls?: string | null
  tool_results?: string | null
}

type ChatSession = {
  id: string
  title?: string
  created_at: string
  updated_at: string
  messages?: ChatMessage[]
}

type ChatResponse = {
  session_id: string
  message: ChatMessage
  is_complete: boolean
}

const sessions = ref<ChatSession[]>([])
const currentSessionId = ref<string | null>(null)
const currentSession = ref<ChatSession | null>(null)

const newTitle = ref('')
const inputMessage = ref('')
const useStream = ref(true)
const sending = ref(false)
const status = ref('')

const messageListEl = ref<HTMLDivElement | null>(null)
const abortController = ref<AbortController | null>(null)
const elapsedSec = ref(0)
let elapsedTimer: number | null = null

const currentTitle = computed(() => currentSession.value?.title || '未选择会话')
const currentMeta = computed(() => {
  if (!currentSession.value) return '请选择左侧会话'
  return `创建：${fmtTime(currentSession.value.created_at)}  更新：${fmtTime(currentSession.value.updated_at)}`
})

const lastMessageFingerprint = computed(() => {
  const msgs = currentSession.value?.messages || []
  const last = msgs.length > 0 ? msgs[msgs.length - 1] : undefined
  if (!last) return ''
  return `${last.id}:${(last.content || '').length}`
})

const sendingLabel = computed(() => {
  if (!sending.value) return ''
  const sec = elapsedSec.value
  const mm = String(Math.floor(sec / 60)).padStart(2, '0')
  const ss = String(sec % 60).padStart(2, '0')
  return `已等待 ${mm}:${ss}`
})

function fmtTime(value?: string) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString()
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail ? `: ${body.detail}` : ''
    } catch {
      // ignore
    }
    throw new Error(`HTTP ${res.status}${detail}`)
  }

  const text = await res.text()
  if (!text) return null as unknown as T
  return JSON.parse(text) as T
}

function scrollToLatest() {
  const el = messageListEl.value
  if (!el) return
  // 等 DOM 更新后滚动
  requestAnimationFrame(() => {
    el.scrollTop = el.scrollHeight
  })
}

function startElapsedTimer() {
  stopElapsedTimer()
  elapsedSec.value = 0
  elapsedTimer = window.setInterval(() => {
    elapsedSec.value += 1
  }, 1000)
}

function stopElapsedTimer() {
  if (elapsedTimer !== null) {
    window.clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function ensureCurrentMessages() {
  if (!currentSession.value) return [] as ChatMessage[]
  if (!currentSession.value.messages) currentSession.value.messages = []
  return currentSession.value.messages
}

async function loadSessions() {
  status.value = '正在加载会话...'
  sessions.value = await requestJson<ChatSession[]>('/api/chat/sessions')
  status.value = '会话已刷新'
}

async function selectSession(id: string | null) {
  currentSessionId.value = id
  currentSession.value = null

  if (!id) {
    status.value = ''
    return
  }

  status.value = '正在加载会话详情...'
  currentSession.value = await requestJson<ChatSession>(`/api/chat/sessions/${encodeURIComponent(id)}`)
  status.value = '会话详情已加载'
  await nextTick()
  scrollToLatest()
}

async function createSession() {
  const title = newTitle.value.trim() || 'New Chat Session'
  status.value = '正在创建会话...'
  const created = await requestJson<ChatSession>('/api/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
  newTitle.value = ''
  await loadSessions()
  await selectSession(created.id)
  status.value = '会话已创建'
}

async function ensureSessionSelected() {
  if (currentSessionId.value) return currentSessionId.value
  // 自动创建一个新会话，避免用户必须先点“新建会话”
  const created = await requestJson<ChatSession>('/api/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ title: 'New Chat Session' }),
  })
  await loadSessions()
  await selectSession(created.id)
  return created.id
}

async function renameSession() {
  const id = currentSessionId.value
  if (!id) return

  const current = sessions.value.find((s) => s.id === id)
  const oldTitle = current?.title || 'New Chat Session'
  const nextTitle = window.prompt('输入新的会话标题', oldTitle)
  if (nextTitle === null) return

  const title = String(nextTitle).trim()
  if (!title) return

  status.value = '正在更新标题...'
  await requestJson<ChatSession>(`/api/chat/sessions/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  })
  await loadSessions()
  await selectSession(id)
  status.value = '标题已更新'
}

async function deleteSession() {
  const id = currentSessionId.value
  if (!id) return
  const ok = window.confirm('确认删除该会话？（会话及其消息都会删除）')
  if (!ok) return

  status.value = '正在删除会话...'
  await requestJson<{ detail: string }>(`/api/chat/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })
  currentSessionId.value = null
  currentSession.value = null
  await loadSessions()
  status.value = '会话已删除'
}

async function sendNonStreaming(sessionId: string, message: string, signal?: AbortSignal) {
  const res = await requestJson<ChatResponse>('/api/chat/message', {
    method: 'POST',
    signal,
    body: JSON.stringify({ session_id: sessionId, message, stream: false }),
  })
  const msgs = ensureCurrentMessages()
  msgs.push(res.message)
}

async function sendStreaming(sessionId: string, message: string, signal?: AbortSignal) {
  // SSE: text/event-stream
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    signal,
    body: JSON.stringify({ session_id: sessionId, message, stream: true }),
  })

  if (!response.ok || !response.body) {
    let detail = ''
    try {
      const body = await response.json()
      detail = body?.detail ? `: ${body.detail}` : ''
    } catch {
      // ignore
    }
    throw new Error(`HTTP ${response.status}${detail}`)
  }

  const msgs = ensureCurrentMessages()

  const draft: ChatMessage = {
    id: `draft-${Date.now()}`,
    role: 'assistant',
    content: '',
    session_id: sessionId,
    created_at: new Date().toISOString(),
  }
  msgs.push(draft)

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE events separated by blank line
      while (true) {
        const idx = buffer.indexOf('\n\n')
        if (idx === -1) break
        const rawEvent = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)

        const lines = rawEvent.split(/\r?\n/)
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const data = trimmed.slice(5).trim()
          if (!data) continue
          if (data === '[DONE]') return

          let payload: any
          try {
            payload = JSON.parse(data)
          } catch {
            continue
          }

          const contentChunk = String(payload?.content || '')
          if (contentChunk) {
            draft.content += contentChunk
          }
          if (payload?.is_final) {
            // 目前后端只在最终块可能带 tool_calls
            if (payload?.tool_calls) {
              try {
                draft.tool_calls = JSON.stringify(payload.tool_calls)
              } catch {
                draft.tool_calls = String(payload.tool_calls)
              }
            }
          }
        }
      }
    }
  } catch (e) {
    if (signal?.aborted) {
      throw new Error('已取消')
    }
    throw e
  }
}

async function sendMessage() {
  const message = inputMessage.value.trim()
  if (!message || sending.value) return
  sending.value = true
  status.value = useStream.value ? '正在生成（流式）...' : '正在生成...'
  startElapsedTimer()

  const controller = new AbortController()
  abortController.value = controller

  try {
    const sessionId = await ensureSessionSelected()

    // optimistic user message
    if (currentSession.value) {
      const msgs = ensureCurrentMessages()
      msgs.push({
        id: `local-${Date.now()}`,
        role: 'user',
        content: message,
        session_id: sessionId,
        created_at: new Date().toISOString(),
      })
    }

    inputMessage.value = ''

    await nextTick()
    scrollToLatest()

    if (useStream.value) {
      await sendStreaming(sessionId, message, controller.signal)
    } else {
      await sendNonStreaming(sessionId, message, controller.signal)
    }

    // 刷新会话详情，拿到数据库中最终消息（以及 updated_at）
    await loadSessions()
    await selectSession(sessionId)
    status.value = '完成'
  } catch (e: any) {
    status.value = `发送失败：${e?.message || e}`
  } finally {
    sending.value = false
    abortController.value = null
    stopElapsedTimer()
  }
}

function cancelSend() {
  const c = abortController.value
  if (!c) return
  c.abort()
  status.value = '已取消'
}

function onComposerKeydown(e: KeyboardEvent) {
  // Enter 发送，Shift+Enter 换行
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

onMounted(async () => {
  try {
    await loadSessions()
  } catch (e: any) {
    status.value = `无法连接后端：${e?.message || e}`
  }
})

watch(lastMessageFingerprint, async () => {
  await nextTick()
  scrollToLatest()
})

watch(currentSessionId, async () => {
  await nextTick()
  scrollToLatest()
})

onBeforeUnmount(() => {
  stopElapsedTimer()
  abortController.value?.abort()
})
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div class="topbar__left">
        <div class="brand">Academic QA Agent</div>
        <div class="muted">会话 + 对话</div>
      </div>
      <div class="topbar__right">
        <label class="toggle">
          <input v-model="useStream" type="checkbox" />
          <span>流式</span>
        </label>
        <button class="btn" @click="loadSessions">刷新</button>
      </div>
    </header>

    <main class="layout">
      <aside class="sidebar">
        <div class="sidebar__actions">
          <input v-model="newTitle" class="input" placeholder="新会话标题（可选）" />
          <button class="btn btn--primary" @click="createSession">新建会话</button>
        </div>

        <div class="sidebar__listHeader">
          <div class="h">会话列表</div>
          <div class="muted">{{ sessions.length }} 个</div>
        </div>

        <div class="sessionList">
          <div v-if="sessions.length === 0" class="empty">暂无会话</div>
          <button
            v-for="s in sessions"
            :key="s.id"
            class="sessionItem"
            :class="{ 'is-active': s.id === currentSessionId }"
            @click="selectSession(s.id)"
          >
            <div class="sessionItem__title">{{ s.title || 'New Chat Session' }}</div>
            <div class="sessionItem__meta">
              <span>{{ fmtTime(s.created_at) }}</span>
              <span>{{ s.id.slice(0, 8) }}</span>
            </div>
          </button>
        </div>
      </aside>

      <section class="content">
        <div class="content__header">
          <div>
            <div class="h">{{ currentTitle }}</div>
            <div class="muted">{{ currentMeta }}</div>
          </div>
          <div class="content__actions">
            <button class="btn" :disabled="!currentSessionId" @click="renameSession">重命名</button>
            <button class="btn btn--danger" :disabled="!currentSessionId" @click="deleteSession">删除</button>
          </div>
        </div>

        <div class="chat">
          <div ref="messageListEl" class="messageList">
            <div v-if="!currentSessionId" class="empty">直接在下方输入提问，会自动创建会话。</div>
            <div v-else-if="(currentSession?.messages || []).length === 0" class="empty">暂无消息，开始提问吧。</div>
            <div v-else>
              <div
                v-for="m in currentSession?.messages"
                :key="m.id"
                class="msg"
                :class="m.role === 'user' ? 'msg--user' : 'msg--assistant'"
              >
                <div class="msg__role">{{ m.role }} · {{ fmtTime(m.created_at) }}</div>
                <div class="msg__content">{{ m.content }}</div>
                <div v-if="m.tool_calls" class="msg__tool">tool_calls: {{ m.tool_calls }}</div>
              </div>
            </div>
          </div>

          <div class="composer">
            <textarea
              v-model="inputMessage"
              class="textarea"
              rows="3"
              placeholder="输入你的问题（Enter 发送，Shift+Enter 换行）"
              :disabled="sending"
              @keydown="onComposerKeydown"
            ></textarea>
            <div class="composer__actions">
              <div v-if="sending" class="sendingHint">
                <span class="dot"></span>
                <span>生成中</span>
                <span class="muted">{{ sendingLabel }}</span>
              </div>
              <div class="composer__buttons">
                <button class="btn" :disabled="!sending" @click="cancelSend">停止</button>
                <button class="btn btn--primary" :disabled="sending || !inputMessage.trim()" @click="sendMessage">
                  {{ sending ? '发送中…' : '发送' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="status" aria-live="polite">{{ status }}</div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(16, 24, 39, 0.72);
  backdrop-filter: blur(8px);
}

.topbar__left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.brand {
  font-weight: 700;
}

.muted {
  opacity: 0.7;
  font-size: 12px;
}

.layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  min-height: calc(100vh - 56px);
}

.sidebar {
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px;
  background: rgba(16, 24, 39, 0.55);
}

.sidebar__actions {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.sidebar__listHeader {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}

.content {
  padding: 14px;
}

.content__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.content__actions {
  display: flex;
  gap: 8px;
}

.h {
  font-size: 14px;
  font-weight: 700;
}

.input {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
}

.btn {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  user-select: none;
}

.toggle input {
  accent-color: rgba(79, 140, 255, 0.85);
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn--primary {
  border-color: rgba(79, 140, 255, 0.55);
  background: rgba(79, 140, 255, 0.15);
}

.btn--danger {
  border-color: rgba(255, 93, 93, 0.55);
  background: rgba(255, 93, 93, 0.12);
}

.sessionList {
  display: grid;
  gap: 8px;
}

.sessionItem {
  text-align: left;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  padding: 10px;
}

.sessionItem.is-active {
  border-color: rgba(79, 140, 255, 0.55);
  background: rgba(79, 140, 255, 0.10);
}

.sessionItem__title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sessionItem__meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  opacity: 0.7;
  font-size: 11px;
}

.messageList {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  padding: 10px;
  min-height: 240px;
  max-height: calc(100vh - 56px - 56px - 160px);
  overflow: auto;
}

.msg {
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  margin: 8px 0;
  background: rgba(255, 255, 255, 0.04);
}

.msg--user {
  border-color: rgba(79, 140, 255, 0.35);
  background: rgba(79, 140, 255, 0.10);
}

.msg--assistant {
  border-color: rgba(255, 255, 255, 0.10);
}

.msg__role {
  font-size: 11px;
  opacity: 0.75;
  margin-bottom: 6px;
}

.msg__content {
  white-space: pre-wrap;
  line-height: 1.5;
  font-size: 13px;
}

.msg__tool {
  margin-top: 6px;
  font-size: 11px;
  opacity: 0.7;
  white-space: pre-wrap;
}

.empty {
  opacity: 0.7;
  font-size: 12px;
  padding: 10px;
}


.chat {
  display: grid;
  gap: 10px;
}

.composer {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.composer__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.composer__buttons {
  display: flex;
  gap: 10px;
}

.sendingHint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  opacity: 0.9;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(79, 140, 255, 0.85);
  box-shadow: 0 0 0 0 rgba(79, 140, 255, 0.55);
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(0.9);
    box-shadow: 0 0 0 0 rgba(79, 140, 255, 0.55);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 10px rgba(79, 140, 255, 0);
  }
  100% {
    transform: scale(0.9);
    box-shadow: 0 0 0 0 rgba(79, 140, 255, 0);
  }
}

.textarea {
  width: 100%;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  resize: vertical;
}

.status {
  margin-top: 10px;
  opacity: 0.75;
  font-size: 12px;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
}
</style>
