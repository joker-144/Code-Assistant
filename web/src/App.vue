<script setup>
import { ref, onMounted } from 'vue'
import { useChat } from './composables/useChat'
import Sidebar from './components/Sidebar.vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import DashboardView from './components/DashboardView.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import IndexModal from './components/IndexModal.vue'
import StatsModal from './components/StatsModal.vue'

const {
  messages, isProcessing, statusText, messagesRef,
  sendMessage, reset,
} = useChat()

const activeView = ref('chat')
const showIndex = ref(false)
const showStats = ref(false)

function handleNavigate(view) {
  activeView.value = view
}

onMounted(() => { reset() })
</script>

<template>
  <Sidebar
    :status-text="statusText"
    :is-processing="isProcessing"
    :active-view="activeView"
    @new-chat="reset"
    @index="showIndex = true"
    @stats="showStats = true"
    @navigate="handleNavigate"
  />

  <main class="main-content">
    <!-- 对话视图 -->
    <div v-if="activeView === 'chat'" class="chat-area">
      <header class="chat-header">
        <div class="header-left">
          <div class="header-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
              <path d="M2 12l10 5 10-5M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
            </svg>
          </div>
          <div>
            <div class="header-title">DevAgent</div>
            <div class="header-sub">AI 编码智能体 · 在线</div>
          </div>
        </div>
        <div class="header-right">
          <span class="version-badge">v0.5.0</span>
        </div>
      </header>

      <div class="messages" ref="messagesRef">
        <div class="messages-inner">
          <ChatMessage
            v-for="(msg, i) in messages"
            :key="i"
            :message="msg"
          />
        </div>
      </div>

      <div class="input-section">
        <ChatInput
          :disabled="isProcessing"
          @send="sendMessage"
        />
      </div>
    </div>

    <!-- 仪表盘视图 -->
    <DashboardView v-else-if="activeView === 'dashboard'" />

    <!-- 设置视图 -->
    <SettingsPanel v-else-if="activeView === 'settings'" />
  </main>

  <transition name="fade">
    <IndexModal v-if="showIndex" @close="showIndex = false" />
  </transition>
  <transition name="fade">
    <StatsModal v-if="showStats" @close="showStats = false" />
  </transition>
</template>

<style scoped>
.main-content {
  flex: 1; display: flex; flex-direction: column;
  overflow: hidden; background: var(--bg-base);
}

/* ── 对话视图 ── */
.chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.chat-header {
  flex-shrink: 0; padding: 14px 24px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}

.header-left { display: flex; align-items: center; gap: 12px; }

.header-avatar {
  width: 36px; height: 36px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: white; box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}

.header-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.header-sub { font-size: 11px; color: var(--text-muted); }

.header-right { display: flex; align-items: center; gap: 10px; }

.version-badge {
  font-size: 10px; font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 3px 10px; border-radius: 20px;
}

.messages { flex: 1; overflow-y: auto; padding: 0 24px; }
.messages-inner { max-width: 860px; margin: 0 auto; padding: 24px 0; display: flex; flex-direction: column; gap: 20px; min-height: min-content; }

.input-section { flex-shrink: 0; padding: 0 24px 16px; background: var(--bg-base); }
.input-section :deep(.input-area) { max-width: 860px; margin: 0 auto; }

@media (max-width: 768px) {
  .messages { padding: 0 12px; }
  .input-section { padding: 0 12px 12px; }
  .chat-header { padding: 12px 16px; }
  .header-sub { display: none; }
}
</style>
