<script setup>
import { ref } from 'vue'

defineProps({
  statusText: { type: String, default: '系统就绪' },
  isProcessing: { type: Boolean, default: false },
  activeView: { type: String, default: 'chat' },
  sidebarExpanded: { type: Boolean, default: true },
})

const emit = defineEmits(['new-chat', 'index', 'stats', 'navigate', 'toggle-sidebar'])
</script>

<template>
  <div class="sidebar-layout">
    <!-- Activity Bar: 48px icon-only -->
    <nav class="activity-bar">
      <div class="activity-top">
        <button class="activity-btn" :class="{ active: activeView === 'chat' }" title="对话" @click="emit('navigate', 'chat')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
        </button>
        <button class="activity-btn" :class="{ active: activeView === 'dashboard' }" title="仪表盘" @click="emit('navigate', 'dashboard')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/><rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/><rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/><rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/></svg>
        </button>
        <button class="activity-btn" :class="{ active: activeView === 'settings' }" title="设置" @click="emit('navigate', 'settings')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
        </button>
      </div>

      <div class="activity-bottom">
        <button class="activity-btn" title="索引项目" @click="emit('index')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M3 7l9-4 9 4M3 7v10l9 4 9-4V7M3 7l9 4 9-4M12 11v10" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
        </button>
        <button class="activity-btn" title="记忆统计" @click="emit('stats')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M4 19V10M10 19V4M16 19v-7M22 19H2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
        </button>
      </div>
    </nav>

    <!-- Expanded Sidebar Panel: 240px -->
    <aside v-show="sidebarExpanded" class="expanded-sidebar">
      <div class="sidebar-header">
        <div class="sidebar-logo">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
            <path d="M2 12l10 5 10-5M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          </svg>
        </div>
        <span class="sidebar-title">DevAgent</span>
      </div>

      <div class="status-indicator">
        <div class="status-dot" :class="{ active: isProcessing }"></div>
        <span>{{ statusText }}</span>
      </div>

      <div class="sidebar-section">
        <div class="section-label">对话</div>
        <button class="new-chat-btn" @click="emit('new-chat')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <span>新对话</span>
        </button>
        <div class="chat-list-empty">暂无历史对话</div>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Agent</div>
        <div class="agent-item active">
          <span class="agent-dot"></span>
          <span>编码智能体</span>
        </div>
      </div>

      <div class="sidebar-footer">
        <span class="version-tag">v0.5.0</span>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.sidebar-layout { display: flex; flex-shrink: 0; }

/* ── Activity Bar ── */
.activity-bar {
  width: 48px; flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column; justify-content: space-between;
  padding: 8px 0;
}

.activity-top, .activity-bottom {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}

.activity-btn {
  width: 40px; height: 40px; border: none; border-radius: 8px;
  background: transparent; color: var(--text-muted);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.15s ease;
  position: relative;
}
.activity-btn:hover { color: var(--text-primary); background: var(--bg-hover); }
.activity-btn.active { color: var(--accent); }
.activity-btn.active::before {
  content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%);
  width: 2px; height: 24px; background: var(--accent); border-radius: 0 2px 2px 0;
}

/* ── Expanded Sidebar ── */
.expanded-sidebar {
  width: 240px; flex-shrink: 0;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: 0 10px;
}

.sidebar-header {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 6px 12px;
}
.sidebar-logo {
  width: 26px; height: 26px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  border-radius: 7px; display: flex; align-items: center; justify-content: center;
  color: white;
}
.sidebar-title {
  font-size: 14px; font-weight: 700;
  background: linear-gradient(135deg, var(--accent), #a78bfa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

.status-indicator {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; margin-bottom: 14px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 11px; color: var(--text-secondary);
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); }
.status-dot.active { background: var(--accent); animation: pulse 0.8s ease-in-out infinite; }

.sidebar-section { margin-bottom: 16px; }
.section-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-faint);
  padding: 6px 6px 8px;
}

.new-chat-btn {
  display: flex; align-items: center; gap: 8px; padding: 9px 12px;
  background: var(--accent); border: none; border-radius: var(--radius-md);
  color: white; font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all var(--transition); width: 100%; margin-bottom: 8px;
}
.new-chat-btn:hover { background: var(--accent-hover); }

.chat-list-empty {
  font-size: 11px; color: var(--text-faint); padding: 16px 6px; text-align: center;
}

.agent-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: var(--radius-md);
  font-size: 12px; color: var(--text-secondary); cursor: pointer;
  transition: all var(--transition);
}
.agent-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.agent-item.active { background: var(--accent-soft); color: var(--accent); }
.agent-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }

.sidebar-footer {
  margin-top: auto; padding: 12px 6px;
  border-top: 1px solid var(--border);
}
.version-tag {
  font-size: 10px; font-weight: 600; color: var(--text-muted);
  background: var(--bg-card); padding: 2px 8px; border-radius: 4px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
