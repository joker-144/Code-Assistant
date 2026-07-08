<script setup>
import { ref, onMounted, provide } from 'vue'
import { useChat } from './composables/useChat'
import TitleBar from './components/TitleBar.vue'
import StatusBar from './components/StatusBar.vue'
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
const sidebarExpanded = ref(true)

function handleNavigate(view) {
  if (view === activeView.value) {
    sidebarExpanded.value = !sidebarExpanded.value
  } else {
    activeView.value = view
    sidebarExpanded.value = true
  }
}

onMounted(() => { reset() })
</script>

<template>
  <div class="app-shell">
    <TitleBar />

    <div class="app-body">
      <Sidebar
        :status-text="statusText"
        :is-processing="isProcessing"
        :active-view="activeView"
        :sidebar-expanded="sidebarExpanded"
        @new-chat="reset"
        @index="showIndex = true"
        @stats="showStats = true"
        @navigate="handleNavigate"
      />

      <main class="main-content">
        <div v-if="activeView === 'chat'" class="chat-area">
          <div class="messages" ref="messagesRef">
            <div class="messages-inner">
              <ChatMessage v-for="(msg, i) in messages" :key="i" :message="msg" />
            </div>
          </div>
          <div class="input-section">
            <ChatInput :disabled="isProcessing" @send="sendMessage" />
          </div>
        </div>

        <DashboardView v-else-if="activeView === 'dashboard'" />
        <SettingsPanel v-else-if="activeView === 'settings'" />
      </main>
    </div>

    <StatusBar :is-processing="isProcessing" />

    <transition name="fade"><IndexModal v-if="showIndex" @close="showIndex = false" /></transition>
    <transition name="fade"><StatsModal v-if="showStats" @close="showStats = false" /></transition>
  </div>
</template>

<style scoped>
.app-shell { height: 100vh; display: flex; flex-direction: column; background: var(--bg-base); overflow: hidden; }
.app-body { flex: 1; display: flex; overflow: hidden; }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg-base); }

.chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.messages { flex: 1; overflow-y: auto; padding: 0 32px; }
.messages-inner {
  max-width: 820px; margin: 0 auto;
  padding: 28px 0; display: flex; flex-direction: column; gap: 22px;
}
.input-section {
  flex-shrink: 0; padding: 0 32px 20px;
  background: linear-gradient(to top, var(--bg-base) 80%, transparent);
}
.input-section :deep(.input-area) { max-width: 820px; margin: 0 auto; }

@media (max-width: 1000px) {
  .messages { padding: 0 20px; }
  .input-section { padding: 0 20px 14px; }
}
</style>
