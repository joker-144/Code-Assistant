<script setup>
defineProps({
  statusText: { type: String, default: '系统就绪' },
  isProcessing: { type: Boolean, default: false },
})

const emit = defineEmits(['new-chat', 'index', 'stats'])
</script>

<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="logo">
      <div class="logo-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
      </div>
      <span class="logo-text">DevAgent</span>
    </div>

    <!-- 状态指示 -->
    <div class="status">
      <div class="status-dot" :class="{ active: isProcessing }"></div>
      <span>{{ statusText }}</span>
    </div>

    <!-- 操作按钮 -->
    <nav class="nav">
      <button class="nav-btn" @click="emit('new-chat')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>新对话</span>
      </button>

      <button class="nav-btn" @click="emit('index')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M3 7l9-4 9 4M3 7v10l9 4 9-4V7M3 7l9 4 9-4M12 11v10" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
        <span>索引项目</span>
      </button>

      <button class="nav-btn" @click="emit('stats')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M4 19V10M10 19V4M16 19v-7M22 19H2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>记忆统计</span>
      </button>
    </nav>

    <!-- 底部信息 -->
    <div class="sidebar-footer">
      <div class="version-tag">v0.4.0</div>
      <div class="powered-by">Agent + 工具集范式</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 4px 16px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, var(--accent) 0%, #3b82f6 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-elevated);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--tool);
  animation: pulse 2s ease-in-out infinite;
}

.status-dot.active {
  background: var(--accent);
  animation: pulse 0.8s ease-in-out infinite;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
  text-align: left;
}

.nav-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.nav-btn svg {
  flex-shrink: 0;
  opacity: 0.7;
}

.sidebar-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.version-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-elevated);
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 6px;
}

.powered-by {
  font-size: 10px;
  color: var(--text-faint);
}

@media (max-width: 768px) {
  .sidebar {
    width: 60px;
    padding: 12px 8px;
  }
  .logo-text, .status span, .nav-btn span, .sidebar-footer {
    display: none;
  }
  .nav-btn {
    justify-content: center;
  }
}
</style>
