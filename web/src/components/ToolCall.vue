<script setup>
import { ref } from 'vue'

const props = defineProps({
  tool: { type: Object, required: true },
})

const expanded = ref(false)
const copied = ref(false)

function getIcon(name) {
  const map = {
    read_file: 'R', write_file: 'W', edit_file: 'E', list_dir: 'D',
    search_code: 'S', run_command: 'C', git_status: 'G', git_diff: 'Df',
    git_log: 'L', git_commit: 'Cm', git_branch: 'B',
    git_add: '+', git_create_branch: 'Br', error: '!',
  }
  return map[name] || '?'
}

function getColor(name) {
  if (name === 'error') return 'var(--error)'
  if (name.startsWith('git')) return '#d2a8ff'
  if (name.includes('search')) return '#79c0ff'
  if (name.includes('write') || name.includes('edit')) return '#ffa657'
  if (name.includes('read') || name.includes('list')) return '#7ee787'
  return 'var(--accent)'
}

function copyResult() {
  navigator.clipboard.writeText(props.tool.result || '')
  copied.value = true
  setTimeout(() => copied.value = false, 1500)
}
</script>

<template>
  <div class="tool-call" :class="{ error: tool.isError, expanded }">
    <div class="tool-header" @click="expanded = !expanded">
      <div class="tool-badge" :style="{ background: getColor(tool.name) }">
        {{ getIcon(tool.name) }}
      </div>
      <span class="tool-name">{{ tool.name }}</span>
      <span v-if="tool.content" class="tool-desc">{{ tool.content }}</span>
      <div class="tool-right">
        <span v-if="!tool.done" class="tool-spinner"></span>
        <span v-else class="tool-done">&#10003;</span>
        <svg class="chevron" :class="{ rotated: expanded }" width="12" height="12" viewBox="0 0 24 24" fill="none">
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
          <div class="section-header">
            <span class="section-label">结果</span>
            <button class="copy-btn" :class="{ copied }" @click.stop="copyResult">
              {{ copied ? '已复制' : '复制' }}
            </button>
          </div>
          <pre class="code-block result">{{ tool.result }}</pre>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.tool-call {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin: 6px 0 6px 32px;
  overflow: hidden;
  transition: all var(--transition);
  animation: slideInRight 0.25s ease;
}
.tool-call:hover { border-color: var(--text-muted); }
.tool-call.expanded { border-color: var(--accent-border); box-shadow: 0 0 0 1px var(--accent-soft); }
.tool-call.error { border-left: 3px solid var(--error); }

.tool-header {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; cursor: pointer; user-select: none;
}
.tool-header:hover { background: var(--bg-hover); }

.tool-badge {
  width: 22px; height: 22px; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 10px; font-weight: 700; font-family: var(--font-mono);
  flex-shrink: 0;
}

.tool-name {
  font-size: 12px; font-weight: 600; color: var(--text-primary);
  font-family: var(--font-mono); flex-shrink: 0;
}
.tool-call.error .tool-name { color: var(--error); }

.tool-desc {
  font-size: 11px; color: var(--text-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;
}

.tool-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.tool-spinner {
  width: 12px; height: 12px; border: 2px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.tool-done { color: var(--success); font-size: 12px; }

.chevron { color: var(--text-muted); transition: transform var(--transition); }
.chevron.rotated { transform: rotate(180deg); }

.tool-body { padding: 0 12px 12px; }

.tool-section { margin-top: 8px; }

.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}

.section-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-faint);
}

.copy-btn {
  font-size: 10px; color: var(--text-muted);
  background: var(--bg-hover); border: 1px solid var(--border);
  padding: 2px 8px; border-radius: 4px; cursor: pointer;
  transition: all var(--transition); font-family: var(--font-sans);
}
.copy-btn:hover { color: var(--text-primary); border-color: var(--text-muted); }
.copy-btn.copied { color: var(--success); border-color: var(--success); }

.code-block {
  background: var(--bg-code); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 10px 12px;
  font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);
  overflow-x: auto; max-height: 320px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
  line-height: 1.7;
}
</style>
