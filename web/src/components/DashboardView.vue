<script setup>
import { ref, onMounted } from 'vue'

const stats = ref({
  todayConversations: 0,
  todayMessages: 0,
  todayToolCalls: 0,
  totalTokens: 0,
  activeAgents: 0,
  apiVersion: '0.5.0',
})

const loading = ref(true)

async function loadStats() {
  loading.value = true
  try {
    const [healthRes, memRes] = await Promise.allSettled([
      fetch('/health'),
      fetch('/memory/stats'),
    ])
    if (healthRes.status === 'fulfilled') {
      const h = await healthRes.value.json()
      stats.value.apiVersion = h.version || '0.5.0'
    }
    if (memRes.status === 'fulfilled') {
      const m = await memRes.value.json()
      stats.value.todayConversations = m.conversations || 0
      stats.value.todayMessages = m.messages || 0
    }
  } catch { /* 使用默认值 */ }
  finally { loading.value = false }
}

onMounted(loadStats)

const quickActions = [
  { icon: 'CR', label: '代码审查', prompt: '请审查当前项目的代码质量，给出改进建议' },
  { icon: 'FX', label: 'Bug 修复', prompt: '帮我分析并修复以下代码中的 bug：' },
  { icon: 'TS', label: '生成测试', prompt: '为当前模块生成单元测试用例' },
  { icon: 'EX', label: '代码解释', prompt: '请解释以下代码的设计思路和关键逻辑：' },
]
</script>

<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <h1>仪表盘</h1>
      <p class="subtitle">DevAgent 运行状态一览</p>
    </header>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon-wrap" style="background: rgba(88,166,255,0.12); color: #58a6ff;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.todayConversations }}</div>
          <div class="stat-label">今日对话数</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon-wrap" style="background: rgba(126,231,135,0.12); color: #7ee787;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.todayMessages }}</div>
          <div class="stat-label">消息数量</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon-wrap" style="background: rgba(210,153,29,0.12); color: #d2991d;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><polyline points="16 18 22 12 16 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><polyline points="8 6 2 12 8 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.todayToolCalls }}</div>
          <div class="stat-label">工具调用</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon-wrap" style="background: rgba(167,139,250,0.12); color: #a78bfa;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.activeAgents }}</div>
          <div class="stat-label">活跃 Agent</div>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="section">
      <h2>快捷操作</h2>
      <div class="quick-grid">
        <div v-for="act in quickActions" :key="act.label" class="quick-card">
          <div class="quick-icon">{{ act.icon }}</div>
          <div class="quick-label">{{ act.label }}</div>
          <div class="quick-prompt">{{ act.prompt }}</div>
        </div>
      </div>
    </div>

    <!-- 系统信息 -->
    <div class="section">
      <h2>系统信息</h2>
      <div class="sys-info">
        <div class="sys-row"><span>API 版本</span><code>{{ stats.apiVersion }}</code></div>
        <div class="sys-row"><span>运行环境</span><code>Python 3.12 · FastAPI + SSE</code></div>
        <div class="sys-row"><span>架构模式</span><code>Agentic Loop · 多 Agent 协同</code></div>
        <div class="sys-row"><span>前端框架</span><code>Vue 3 + Vite · Marked + highlight.js</code></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard { flex: 1; overflow-y: auto; padding: 32px; max-width: 960px; margin: 0 auto; }

.dashboard-header { margin-bottom: 28px; }
.dashboard-header h1 { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.subtitle { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 32px; }
.stat-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px 16px; display: flex; align-items: flex-start; gap: 14px; transition: all var(--transition); animation: fadeInUp 0.4s ease both; }
.stat-card:nth-child(2) { animation-delay: 0.05s; }
.stat-card:nth-child(3) { animation-delay: 0.1s; }
.stat-card:nth-child(4) { animation-delay: 0.15s; }
.stat-card:hover { border-color: var(--text-muted); transform: translateY(-2px); }
.stat-icon-wrap { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-value { font-size: 26px; font-weight: 700; font-family: var(--font-mono); color: var(--text-primary); line-height: 1.1; }
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.section { margin-bottom: 28px; }
.section h2 { font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px; padding-left: 2px; }

.quick-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.quick-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px; cursor: pointer; transition: all var(--transition); }
.quick-card:hover { background: var(--bg-card); border-color: var(--accent-border); }
.quick-icon { font-size: 22px; font-weight: 700; font-family: var(--font-mono); color: var(--accent); margin-bottom: 4px; }
.quick-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.quick-prompt { font-size: 11px; color: var(--text-muted); margin-top: 4px; line-height: 1.4; }

.sys-info { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.sys-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-light); font-size: 13px; color: var(--text-secondary); }
.sys-row:last-child { border-bottom: none; }
.sys-row code { font-family: var(--font-mono); font-size: 12px; color: var(--text-primary); background: var(--bg-card); padding: 3px 10px; border-radius: 4px; }

@media (max-width: 768px) {
  .dashboard { padding: 20px 14px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .quick-grid { grid-template-columns: 1fr; }
}
</style>
