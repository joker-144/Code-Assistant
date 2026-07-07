<script setup>
import { ref, onMounted, computed } from 'vue'

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

// ── 版本更新状态 ──
const currentVersion = ref('')
const latestVersion = ref('')
const hasUpdate = ref(false)
const changelog = ref('')
const releaseUrl = ref('')
const checkingUpdate = ref(false)
const updatingVersion = ref(false)
const updateLog = ref([])
const updateDone = ref(false)

// 是否运行在 Electron 中
const isElectron = computed(() => !!window.electronAPI)

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

// ── 版本更新逻辑 ──

async function checkVersion() {
  checkingUpdate.value = true
  currentVersion.value = ''
  latestVersion.value = ''
  hasUpdate.value = false
  changelog.value = ''
  updateDone.value = false

  try {
    let data
    if (window.electronAPI) {
      data = await window.electronAPI.checkVersion()
    } else {
      const resp = await fetch('/api/version/check')
      data = await resp.json()
    }

    currentVersion.value = data.current || ''
    latestVersion.value = data.latest || ''
    hasUpdate.value = data.has_update || false
    changelog.value = data.changelog || ''
    releaseUrl.value = data.release_url || ''
  } catch (e) {
    updateLog.value = [`检查更新失败: ${e.message}`]
  } finally {
    checkingUpdate.value = false
  }
}

async function startUpdate() {
  if (!window.electronAPI) {
    updateLog.value = ['请在桌面端使用更新功能']
    return
  }

  updatingVersion.value = true
  updateLog.value = []
  updateDone.value = false

  try {
    const result = await window.electronAPI.updateVersion()
    if (result.success) {
      updateLog.value = ['更新命令已提交，请等待后端处理...']
    } else {
      updateLog.value = [`更新启动失败: ${result.error}`]
    }
  } catch (e) {
    updateLog.value = [`更新异常: ${e.message}`]
  } finally {
    updatingVersion.value = false
  }
}

async function startUpdateBrowser() {
  updatingVersion.value = true
  updateLog.value = []
  updateDone.value = false

  try {
    const resp = await fetch('/api/version/update', { method: 'POST' })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split('\n')) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const msg = JSON.parse(trimmed.slice(6))
            updateLog.value.push(msg.message || JSON.stringify(msg))
            if (msg.status === 'done') updateDone.value = true
          } catch {
            updateLog.value.push(trimmed.slice(6))
          }
        }
      }
    }
  } catch (e) {
    updateLog.value.push(`更新异常: ${e.message}`)
  } finally {
    updatingVersion.value = false
  }
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

    <!-- 版本更新 -->
    <div class="form-section">
      <h2>版本更新</h2>

      <div class="version-info">
        <div class="version-row">
          <span class="version-label">当前版本</span>
          <span class="version-value" :class="{ pulse: checkingUpdate }">
            {{ currentVersion || '—' }}
          </span>
        </div>
        <div v-if="latestVersion" class="version-row">
          <span class="version-label">最新版本</span>
          <span class="version-value latest">{{ latestVersion }}</span>
        </div>
      </div>

      <div v-if="hasUpdate && changelog" class="changelog-box">
        <div class="changelog-title">更新日志</div>
        <pre class="changelog-content">{{ changelog }}</pre>
      </div>

      <div v-if="updateLog.length" class="update-log-box">
        <div v-for="(line, i) in updateLog" :key="i" class="log-line">{{ line }}</div>
      </div>

      <div v-if="updateDone" class="update-done-hint">
        更新完成，请重启应用以生效。
      </div>

      <div class="version-actions">
        <button class="btn-secondary" @click="checkVersion" :disabled="checkingUpdate">
          {{ checkingUpdate ? '检查中...' : '检查更新' }}
        </button>
        <button
          v-if="hasUpdate"
          class="btn-primary"
          @click="isElectron ? startUpdate() : startUpdateBrowser()"
          :disabled="updatingVersion"
        >
          {{ updatingVersion ? '更新中...' : '立即更新' }}
        </button>
      </div>

      <p v-if="!isElectron" class="hint warning">
        当前运行在浏览器模式，请在桌面端使用一键更新功能以获得最佳体验。
      </p>
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
.hint.warning { color: var(--text-muted); background: var(--bg-card); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--border); margin-top: 12px; }

/* ── 版本更新 ── */

.version-info { margin-bottom: 16px; }
.version-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); }
.version-label { font-size: 13px; color: var(--text-muted); }
.version-value { font-family: var(--font-mono); font-size: 13px; color: var(--text-primary); font-weight: 500; }
.version-value.latest { color: var(--accent); }
.version-value.pulse { animation: pulse 1s ease-in-out infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.changelog-box { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 16px; overflow: hidden; }
.changelog-title { font-size: 12px; font-weight: 600; color: var(--text-secondary); padding: 10px 14px; background: var(--bg-input); border-bottom: 1px solid var(--border); }
.changelog-content { font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); padding: 12px 14px; margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; line-height: 1.6; }

.update-log-box { background: var(--bg-code); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 10px 14px; margin-bottom: 12px; max-height: 200px; overflow-y: auto; }
.log-line { font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); line-height: 1.6; white-space: pre-wrap; word-break: break-all; }

.update-done-hint { font-size: 12px; color: var(--success); font-weight: 600; margin-bottom: 12px; padding: 8px 14px; background: color-mix(in srgb, var(--success) 10%, transparent); border: 1px solid var(--success); border-radius: var(--radius-md); }

.version-actions { display: flex; gap: 10px; margin-top: 8px; }
.btn-primary {
  background: var(--accent); color: white; border: none;
  padding: 10px 24px; border-radius: var(--radius-md);
  font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all var(--transition);
}
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: transparent; color: var(--text-primary); border: 1px solid var(--border);
  padding: 10px 24px; border-radius: var(--radius-md);
  font-family: var(--font-sans); font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.btn-secondary:hover:not(:disabled) { border-color: var(--accent-border); color: var(--accent); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

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
