<script setup>
import { onMounted, ref } from 'vue'
import { useChat } from './composables/useChat'
import Sidebar from './components/Sidebar.vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import IndexModal from './components/IndexModal.vue'
import StatsModal from './components/StatsModal.vue'
import SkillsPanel from './components/SkillsPanel.vue'

const {
  messages,
  isProcessing,
  statusText,
  messagesRef,
  agentStates,
  sendMessage,
  reset,
} = useChat()

const showIndex = ref(false)
const showStats = ref(false)
const showSkills = ref(false)

onMounted(() => {
  reset()
})
</script>

<template>
  <Sidebar
    :status-text="statusText"
    :is-processing="isProcessing"
    @new-chat="reset"
    @index="showIndex = true"
    @stats="showStats = true"
    @skills="showSkills = !showSkills"
  />

  <main class="chat-area">
    <template v-if="!showSkills">
      <!-- 顶部标题 + Agent 快速状态 -->
      <header class="chat-header">
        <div class="header-title">
          <span class="title-text">AI 编码智能体</span>
          <span class="title-sub">多智能体协作 · 流式响应</span>
        </div>
        <div class="header-agents">
          <div
            v-for="agent in agentStates"
            :key="agent.id"
            class="header-agent"
            :class="{ active: agent.active, done: agent.status === 'done' }"
          >
            <span>{{ agent.icon }}</span>
            <span>{{ agent.status || '待命中' }}</span>
          </div>
        </div>
      </header>

      <!-- 消息区域 -->
      <div class="messages" ref="messagesRef">
        <div class="messages-inner">
          <ChatMessage
            v-for="(msg, i) in messages"
            :key="i"
            :message="msg"
          />
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-section">
        <ChatInput
          :disabled="isProcessing"
          @send="sendMessage"
        />
      </div>
    </template>

    <SkillsPanel v-else />
  </main>

  <!-- 模态框 -->
  <transition name="fade">
    <IndexModal v-if="showIndex" @close="showIndex = false" />
  </transition>
  <transition name="fade">
    <StatsModal v-if="showStats" @close="showStats = false" />
  </transition>
</template>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.chat-header {
  flex-shrink: 0;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.title-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.title-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px;
}

.messages-inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: min-content;
}

.input-section {
  flex-shrink: 0;
  padding: 0 24px 16px;
  background: var(--bg-base);
}

.input-section :deep(.input-area) {
  max-width: 860px;
  margin: 0 auto;
}

@media (max-width: 768px) {
  .messages {
    padding: 0 12px;
  }
  .input-section {
    padding: 0 12px 12px;
  }
  .chat-header {
    padding: 12px 16px;
  }
  .title-sub {
    display: none;
  }
  .header-agents {
    display: none;
  }
}
</style>
