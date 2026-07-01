<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import ToolCall from './ToolCall.vue'

marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
})

const props = defineProps({
  message: { type: Object, required: true },
})

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return marked.parse(props.message.content)
})
</script>

<template>
  <div class="message" :class="message.role">
    <!-- 用户消息 -->
    <div v-if="message.role === 'user'" class="user-bubble">
      <div class="user-label">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="2"/>
          <path d="M4 20c0-4 4-6 8-6s8 2 8 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>你</span>
      </div>
      <div class="user-content">{{ message.content }}</div>
    </div>

    <!-- 助手消息 -->
    <div v-else class="assistant-block">
      <div class="assistant-label">
        <div class="avatar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
            <path d="M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          </svg>
        </div>
        <span>DevAgent</span>
      </div>

      <!-- 工具调用 -->
      <ToolCall
        v-for="(tool, i) in message.tools"
        :key="i"
        :tool="tool"
      />

      <!-- 文本内容 -->
      <div
        v-if="renderedContent"
        class="assistant-content markdown"
        v-html="renderedContent"
      ></div>

      <!-- 等待动画 -->
      <div v-if="!message.content && message.tools.length === 0" class="typing">
        <span></span><span></span><span></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  animation: fadeIn 0.3s ease forwards;
  opacity: 0;
}

/* 用户消息 */
.user-bubble {
  max-width: 75%;
  margin-left: auto;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
  padding: 12px 16px;
}

.user-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.user-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
}

/* 助手消息 */
.assistant-block {
  width: 100%;
}

.assistant-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.avatar {
  width: 24px;
  height: 24px;
  background: linear-gradient(135deg, var(--accent), #3b82f6);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.assistant-label span {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}

.assistant-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
  padding-left: 32px;
}

/* Markdown 样式 */
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  color: var(--text-primary);
  font-weight: 600;
  margin: 16px 0 8px;
}
.markdown :deep(h1) { font-size: 20px; }
.markdown :deep(h2) { font-size: 17px; }
.markdown :deep(h3) { font-size: 15px; }

.markdown :deep(p) {
  margin: 6px 0;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.markdown :deep(li) {
  margin: 2px 0;
}

.markdown :deep(pre) {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin: 10px 0;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
}

.markdown :deep(pre code) {
  background: none;
  padding: 0;
  color: var(--text-primary);
}

.markdown :deep(code) {
  font-family: var(--font-mono);
  background: var(--bg-elevated);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #6366f1;
}

.markdown :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.markdown :deep(a:hover) {
  text-decoration: underline;
}

.markdown :deep(blockquote) {
  border-left: 3px solid var(--accent-border);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-muted);
}

.markdown :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
}

.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}

.markdown :deep(th) {
  background: var(--bg-elevated);
  font-weight: 600;
}

/* 等待动画 */
.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 32px;
}

.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: bounce 1.4s ease-in-out infinite;
}

.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
</style>
