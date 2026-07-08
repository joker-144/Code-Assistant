<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({ disabled: { type: Boolean, default: false } })
const emit = defineEmits(['send'])

const text = ref('')
const textareaRef = ref(null)
const focused = ref(false)

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  if (e.key === 'Escape') { e.target.blur() }
}

function submit() {
  const value = text.value.trim()
  if (!value || props.disabled) return
  emit('send', value)
  text.value = ''
  nextTick(autoResize)
}
</script>

<template>
  <div class="input-area" :class="{ focused }">
    <div class="input-shell">
      <div class="input-prefix">
        <span class="prefix-label">></span>
      </div>
      <textarea
        ref="textareaRef" v-model="text" :disabled="disabled"
        placeholder="输入指令或描述需求… (Enter 发送 · Shift+Enter 换行 · Esc 退出)" rows="1"
        @input="autoResize" @keydown="handleKeydown"
        @focus="focused = true" @blur="focused = false"
      ></textarea>
      <div class="input-actions">
        <span class="char-count" v-if="text">{{ text.length }}</span>
        <button class="send-btn" :disabled="disabled || !text.trim()" @click="submit" title="发送 (Enter)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="input-hint">
      <span class="hint-left"><kbd>Enter</kbd> 发送 · <kbd>Shift</kbd>+<kbd>Enter</kbd> 换行</span>
      <span class="hint-right">DevAgent · 编码智能体</span>
    </div>
  </div>
</template>

<style scoped>
.input-area { padding: 8px 0; }

.input-shell {
  display: flex; align-items: flex-end;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 4px 8px 4px 12px;
  transition: all 0.2s ease;
  box-shadow: var(--shadow-sm);
}
.input-area.focused .input-shell {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow-md);
}

.input-prefix {
  display: flex; align-items: center; padding-bottom: 8px; flex-shrink: 0;
  margin-right: 6px;
}
.prefix-label {
  font-family: var(--font-mono); font-size: 15px; font-weight: 700;
  color: var(--accent); opacity: 0.8;
}

textarea {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-primary); font-family: var(--font-mono);
  font-size: 13px; line-height: 1.6; padding: 8px 0;
  resize: none; min-height: 22px; max-height: 180px;
}
textarea::placeholder { color: var(--text-faint); font-family: var(--font-sans); }
textarea:disabled { color: var(--text-muted); }

.input-actions { display: flex; align-items: center; gap: 6px; padding-bottom: 4px; flex-shrink: 0; }
.char-count { font-family: var(--font-mono); font-size: 10px; color: var(--text-faint); }

.send-btn {
  width: 32px; height: 32px; background: var(--accent);
  border: none; border-radius: 8px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: white; flex-shrink: 0; transition: all 0.15s ease;
}
.send-btn:hover:not(:disabled) { background: var(--accent-hover); transform: scale(1.06); }
.send-btn:active:not(:disabled) { transform: scale(0.94); }
.send-btn:disabled { background: var(--bg-hover); color: var(--text-faint); cursor: not-allowed; }

.input-hint {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 7px; font-size: 10px; color: var(--text-faint); padding: 0 4px;
}
kbd {
  display: inline-block; padding: 1px 5px;
  font-family: var(--font-mono); font-size: 9px; line-height: 1.4;
  color: var(--text-muted); background: var(--bg-card);
  border: 1px solid var(--border); border-radius: 3px;
}
.hint-right { color: var(--text-faint); opacity: 0.6; }
</style>
