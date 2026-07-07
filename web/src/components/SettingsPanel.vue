<script setup>
import { ref, onMounted } from 'vue'

const settings = ref({
  apiKey: '',
  model: 'deepseek-v3',
  temperature: 0.3,
  maxTokens: 4096,
})

const models = [
  { value: 'deepseek-v3', label: 'DeepSeek V3' },
  { value: 'deepseek-r1', label: 'DeepSeek R1' },
  { value: 'qwen-max', label: 'Qwen Max' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  { value: 'custom', label: '自定义...' },
]

const saved = ref(false)
const loading = ref(false)

// 从 localStorage 读取已保存的设置
onMounted(() => {
  try {
    const saved = localStorage.getItem('devagent-settings')
    if (saved) {
      const parsed = JSON.parse(saved)
      Object.assign(settings.value, parsed)
    }
  } catch { /* ignore */ }
})

function saveSettings() {
  try {
    localStorage.setItem('devagent-settings', JSON.stringify(settings.value))
  } catch { /* ignore */ }
  saved.value = true
  setTimeout(() => saved.value = false, 2000)
}
</script>

<template>
  <div class="settings">
    <header class="settings-header">
      <h1>设置</h1>
      <p class="subtitle">配置模型、API Key 与参数</p>
    </header>

    <div class="form-section">
      <h2>模型配置</h2>

      <div class="form-group">
        <label>API Key</label>
        <div class="input-with-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" stroke-width="2"/><path d="M7 11V7a5 5 0 0110 0v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input v-model="settings.apiKey" type="password" placeholder="sk-..." />
        </div>
        <p class="hint">API Key 仅保存在浏览器本地存储中，不会上传到服务器。</p>
      </div>

      <div class="form-group">
        <label>模型选择</label>
        <div class="select-wrapper">
          <select v-model="settings.model">
            <option v-for="m in models" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
          <svg class="select-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
      </div>

      <div class="form-group">
        <label>Temperature ({{ settings.temperature }})</label>
        <input v-model.number="settings.temperature" type="range" min="0" max="2" step="0.1" class="slider" />
        <div class="range-labels"><span>精确 0</span><span>平衡 1.0</span><span>创造 2.0</span></div>
        <p class="hint">越高越有创造性，越低越精确。代码生成建议 0.1-0.3。</p>
      </div>

      <div class="form-group">
        <label>最大 Token 数</label>
        <input v-model.number="settings.maxTokens" type="number" min="512" max="32768" step="512" class="number-input" />
        <p class="hint">单次回复的最大 Token 数量，较大值适合长文档生成。</p>
      </div>
    </div>

    <div class="actions">
      <button class="btn-save" @click="saveSettings" :class="{ saved }">
        {{ saved ? '已保存' : '保存设置' }}
      </button>
      <button class="btn-reset" @click="settings.apiKey = ''; saveSettings()">
        清除 API Key
      </button>
    </div>
  </div>
</template>

<style scoped>
.settings { flex: 1; overflow-y: auto; padding: 32px; max-width: 640px; margin: 0 auto; }

.settings-header { margin-bottom: 32px; }
.settings-header h1 { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.subtitle { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.form-section { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; margin-bottom: 24px; }
.form-section h2 { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }

.form-group { margin-bottom: 20px; }
.form-group:last-child { margin-bottom: 0; }
.form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 6px; }

.input-with-icon {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 0 14px;
  transition: border-color var(--transition);
}
.input-with-icon:focus-within { border-color: var(--accent-border); box-shadow: 0 0 0 2px var(--accent-soft); }
.input-with-icon svg { color: var(--text-muted); flex-shrink: 0; }
.input-with-icon input {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-primary); font-family: var(--font-mono);
  font-size: 13px; padding: 12px 0;
}
.input-with-icon input::placeholder { color: var(--text-faint); }

.select-wrapper { position: relative; }
select {
  width: 100%; appearance: none; background: var(--bg-input);
  border: 1px solid var(--border); border-radius: var(--radius-md);
  color: var(--text-primary); font-family: var(--font-sans);
  font-size: 13px; padding: 11px 14px; cursor: pointer;
  transition: border-color var(--transition);
}
select:focus { outline: none; border-color: var(--accent-border); box-shadow: 0 0 0 2px var(--accent-soft); }
.select-chevron { position: absolute; right: 14px; top: 50%; transform: translateY(-50%); color: var(--text-muted); pointer-events: none; }

.slider { width: 100%; appearance: none; height: 6px; background: var(--bg-card); border-radius: 3px; outline: none; margin: 10px 0 6px; }
.slider::-webkit-slider-thumb { appearance: none; width: 18px; height: 18px; background: var(--accent); border-radius: 50%; cursor: pointer; border: 2px solid var(--bg-surface); }
.range-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-faint); }

.number-input {
  width: 100%; background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-md); color: var(--text-primary);
  font-family: var(--font-mono); font-size: 13px; padding: 11px 14px;
  transition: border-color var(--transition);
}
.number-input:focus { outline: none; border-color: var(--accent-border); box-shadow: 0 0 0 2px var(--accent-soft); }

.hint { font-size: 11px; color: var(--text-faint); margin-top: 6px; line-height: 1.5; }

.actions { display: flex; gap: 10px; }
.btn-save {
  background: var(--accent); color: white; border: none;
  padding: 10px 24px; border-radius: var(--radius-md);
  font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all var(--transition);
}
.btn-save:hover { background: var(--accent-hover); }
.btn-save.saved { background: var(--success); }
.btn-reset {
  background: transparent; color: var(--text-muted);
  border: 1px solid var(--border); padding: 10px 24px;
  border-radius: var(--radius-md); font-family: var(--font-sans);
  font-size: 13px; cursor: pointer; transition: all var(--transition);
}
.btn-reset:hover { border-color: var(--error); color: var(--error); }

@media (max-width: 768px) {
  .settings { padding: 20px 14px; }
}
</style>
