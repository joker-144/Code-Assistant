<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({ disabled: { type: Boolean, default: false } })
const emit = defineEmits(['send'])

const text = ref('')
const textareaRef = ref(null)

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
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
  <div class="input-area">
    <div class="input-wrapper">
      <textarea
        ref="textareaRef" v-model="text" :disabled="disabled"
        placeholder="描述你的开发需求… (Enter 发送 · Shift+Enter 换行)" rows="1"
        @input="autoResize" @keydown="handleKeydown"
      ></textarea>
      <button class="send-btn" :disabled="disabled || !text.trim()" @click="submit" title="发送">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>
    <div class="input-hint">
      <span>Chat · 所有对话均在本地处理</span>
      <span class="token-hint" v-if="text">{{ text.length }} 字符</span>
    </div>
  </div>
</template>

<style scoped>
.input-area { padding: 12px 0; }

.input-wrapper {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 4px 4px 4px 16px;
  transition: all var(--transition);
}
.input-wrapper:focus-within {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

textarea {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-primary); font-family: var(--font-sans);
  font-size: 14px; line-height: 1.5; padding: 10px 0;
  resize: none; min-height: 24px; max-height: 160px;
}
textarea::placeholder { color: var(--text-faint); }
textarea:disabled { color: var(--text-muted); }

.send-btn {
  width: 38px; height: 38px; background: var(--accent);
  border: none; border-radius: 50%; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: white; flex-shrink: 0; transition: all var(--transition);
}
.send-btn:hover:not(:disabled) { background: var(--accent-hover); transform: scale(1.08); }
.send-btn:active:not(:disabled) { transform: scale(0.95); }
.send-btn:disabled { background: var(--bg-hover); color: var(--text-faint); cursor: not-allowed; }

.input-hint {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 6px; font-size: 10px; color: var(--text-faint);
}
.token-hint { color: var(--text-muted); }
</style>
