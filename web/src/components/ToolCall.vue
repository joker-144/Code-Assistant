<script setup>
import { ref } from 'vue'

const props = defineProps({
  tool: { type: Object, required: true },
})

const expanded = ref(false)

const toolIcons = {
  read_file: '📄',
  write_file: '✏️',
  edit_file: '🔧',
  list_dir: '📁',
  search_code: '🔍',
  run_command: '⚡',
  git_status: '📊',
  git_diff: '📋',
  git_log: '📝',
  git_commit: '✅',
  git_branch: '🌿',
  git_add: '➕',
  git_create_branch: '🌱',
  error: '❌',
}

function getIcon(name) {
  return toolIcons[name] || '⚙'
}
</script>

<template>
  <div class="tool-call" :class="{ error: tool.isError }">
    <div class="tool-header" @click="expanded = !expanded">
      <span class="tool-icon">{{ getIcon(tool.name) }}</span>
      <span class="tool-name">{{ tool.name }}</span>
      <span v-if="tool.content" class="tool-desc">{{ tool.content }}</span>
      <div class="tool-right">
        <span v-if="!tool.done" class="tool-spinner"></span>
        <span v-else class="tool-done">✓</span>
        <svg
          class="chevron"
          :class="{ rotated: expanded }"
          width="14" height="14" viewBox="0 0 24 24" fill="none"
        >
          <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
    </div>

    <transition name="fade">
      <div v-if="expanded" class="tool-body">
        <div v-if="Object.keys(tool.args).length > 0" class="tool-section">
          <div class="section-label">参数</div>
          <pre class="code-block">{{ JSON.stringify(tool.args, null, 2) }}</pre>
        </div>
        <div v-if="tool.result" class="tool-section">
          <div class="section-label">结果</div>
          <pre class="code-block result">{{ tool.result }}</pre>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.tool-call {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-left: 3px solid var(--tool);
  border-radius: var(--radius-md);
  margin: 6px 0;
  overflow: hidden;
  transition: border-color var(--transition);
}

.tool-call:hover {
  border-color: var(--tool-border);
}

.tool-call.error {
  border-left-color: var(--error);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}

.tool-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.tool-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--tool);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.tool-call.error .tool-name {
  color: var(--error);
}

.tool-desc {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.tool-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.tool-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tool-done {
  color: var(--tool);
  font-size: 12px;
}

.chevron {
  color: var(--text-muted);
  transition: transform var(--transition);
}

.chevron.rotated {
  transform: rotate(180deg);
}

.tool-body {
  padding: 0 12px 10px;
}

.tool-section {
  margin-top: 6px;
}

.section-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-faint);
  margin-bottom: 4px;
}

.code-block {
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.code-block.result {
  color: var(--text-secondary);
}
</style>
