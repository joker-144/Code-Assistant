<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({ isProcessing: { type: Boolean, default: false } })

const tokens = ref(0)
let tokenTimer = null

onMounted(() => { tokenTimer = setInterval(() => tokens.value = Math.floor(Math.random() * 5000 + 200), 5000) })
onUnmounted(() => clearInterval(tokenTimer))
</script>

<template>
  <footer class="status-bar">
    <div class="status-left">
      <div class="status-item">
        <span class="dot" :class="{ active: isProcessing }"></span>
        <span>{{ isProcessing ? '处理中' : '就绪' }}</span>
      </div>
      <div class="status-sep"></div>
      <span class="status-item muted">DeepSeek V3</span>
    </div>
    <div class="status-right">
      <span class="status-item muted">Tokens: {{ tokens.toLocaleString() }}</span>
    </div>
  </footer>
</template>

<style scoped>
.status-bar {
  height: 28px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 14px;
  background: var(--bg-surface);
  border-top: 1px solid var(--border);
  font-size: 11px; color: var(--text-muted);
}

.status-left, .status-right {
  display: flex; align-items: center; gap: 10px;
}

.status-item { display: flex; align-items: center; gap: 6px; }
.muted { color: var(--text-faint); }

.dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--success);
}
.dot.active { background: var(--accent); animation: pulse 0.8s ease-in-out infinite; }

.status-sep {
  width: 1px; height: 12px; background: var(--border);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
