<script setup>
defineProps({
  statusText: { type: String, default: '系统就绪' },
  isProcessing: { type: Boolean, default: false },
  activeView: { type: String, default: 'chat' },
})

const emit = defineEmits(['new-chat', 'index', 'stats', 'navigate'])
</script>

<template>
  <aside class="sidebar">
    <div class="logo">
      <div class="logo-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          <path d="M2 12l10 5 10-5M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
      </div>
      <span class="logo-text">DevAgent</span>
    </div>

    <div class="status">
      <div class="status-dot" :class="{ active: isProcessing }"></div>
      <span>{{ statusText }}</span>
    </div>

    <nav class="nav">
      <div class="nav-section-label">功能</div>
      <button class="nav-btn" :class="{ active: activeView === 'chat' }" @click="emit('navigate', 'chat')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
        <span>对话</span>
      </button>
      <button class="nav-btn" :class="{ active: activeView === 'dashboard' }" @click="emit('navigate', 'dashboard')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/><rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/><rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/><rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/></svg>
        <span>仪表盘</span>
      </button>

      <div class="nav-section-label">工具</div>
      <button class="nav-btn" @click="emit('index')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M3 7l9-4 9 4M3 7v10l9 4 9-4V7M3 7l9 4 9-4M12 11v10" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
        <span>索引项目</span>
      </button>
      <button class="nav-btn" @click="emit('stats')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M4 19V10M10 19V4M16 19v-7M22 19H2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        <span>记忆统计</span>
      </button>

      <div class="nav-section-label">系统</div>
      <button class="nav-btn" :class="{ active: activeView === 'settings' }" @click="emit('navigate', 'settings')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        <span>设置</span>
      </button>
    </nav>

    <button class="new-chat-btn" @click="emit('new-chat')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <span>新对话</span>
    </button>

    <div class="sidebar-footer">
      <div class="version-tag">v0.5.0</div>
      <div class="powered-by">Agent + 工具集范式</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar { width: 240px; flex-shrink: 0; background: var(--bg-surface); border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 16px 10px; }

.logo { display: flex; align-items: center; gap: 10px; padding: 4px 8px 16px; }
.logo-icon { width: 32px; height: 32px; background: linear-gradient(135deg, #2563eb, #7c3aed); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; box-shadow: 0 2px 8px rgba(37,99,235,0.3); }
.logo-text { font-size: 16px; font-weight: 700; background: linear-gradient(135deg, var(--accent), #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

.status { display: flex; align-items: center; gap: 8px; padding: 8px 12px; margin-bottom: 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); font-size: 11px; color: var(--text-secondary); }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); animation: pulse 2s ease-in-out infinite; }
.status-dot.active { background: var(--accent); animation: pulse 0.8s ease-in-out infinite; }

.nav { display: flex; flex-direction: column; gap: 2px; flex: 1; overflow-y: auto; }
.nav-section-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-faint); padding: 12px 12px 4px; }
.nav-btn { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: transparent; border: none; border-radius: var(--radius-md); color: var(--text-secondary); font-family: var(--font-sans); font-size: 13px; font-weight: 500; cursor: pointer; transition: all var(--transition); text-align: left; width: 100%; }
.nav-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-btn.active { background: var(--accent-soft); color: var(--accent); }
.nav-btn svg { flex-shrink: 0; opacity: 0.7; }
.nav-btn.active svg { opacity: 1; }

.new-chat-btn { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 10px; background: var(--accent); border: none; border-radius: var(--radius-md); color: white; font-family: var(--font-sans); font-size: 13px; font-weight: 600; cursor: pointer; transition: all var(--transition); margin-top: 12px; }
.new-chat-btn:hover { background: var(--accent-hover); transform: translateY(-1px); }
.new-chat-btn:active { transform: translateY(0); }

.sidebar-footer { padding-top: 12px; border-top: 1px solid var(--border); margin-top: 12px; }
.version-tag { display: inline-block; font-size: 10px; font-weight: 600; color: var(--text-muted); background: var(--bg-card); padding: 2px 8px; border-radius: 4px; margin-bottom: 6px; }
.powered-by { font-size: 10px; color: var(--text-faint); }

@media (max-width: 768px) {
  .sidebar { width: 56px; padding: 12px 6px; }
  .logo-text, .status span, .nav-btn span, .new-chat-btn span, .sidebar-footer, .nav-section-label { display: none; }
  .nav-btn { justify-content: center; padding: 10px; }
}
</style>
