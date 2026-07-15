<script setup>
import { ref, onMounted, computed, watch } from 'vue'

// ── 供应商定义 ──
const providers = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    defaultBaseUrl: 'https://api.deepseek.com/v1',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    defaultBaseUrl: 'https://api.openai.com/v1',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    defaultBaseUrl: 'https://api.anthropic.com/v1',
  },
  {
    id: 'qwen',
    name: '通义千问 (Qwen)',
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  },
  {
    id: 'zhipu',
    name: '智谱 (GLM)',
    defaultBaseUrl: 'https://open.bigmodel.cn/api/paas/v4',
  },
  {
    id: 'moonshot',
    name: '月之暗面 (Moonshot)',
    defaultBaseUrl: 'https://api.moonshot.cn/v1',
  },
  {
    id: 'custom',
    name: '自定义接口',
    defaultBaseUrl: '',
  },
]

const DEFAULT_SETTINGS = {
  provider: 'deepseek',
  apiKeys: {},       // { providerId: 'sk-xxx' }
  model: 'deepseek-chat',
  baseUrl: 'https://api.deepseek.com/v1',
  temperature: 0.3,
  maxTokens: 4096,
}

const settings = ref(structuredClone(DEFAULT_SETTINGS))
const saved = ref(false)

const activeProvider = computed(() => providers.find((p) => p.id === settings.value.provider))

// 动态模型列表（从后端 API 获取）
const providerModels = ref([])
const modelsLoading = ref(false)
const modelsError = ref('')

async function fetchModels(providerId, apiKey, baseUrl) {
  providerModels.value = []
  modelsError.value = ''

  if (!providerId || !baseUrl) {
    modelsError.value = '请先配置 Base URL'
    return
  }

  if (!apiKey) {
    modelsError.value = '请先配置 API Key'
    return
  }

  modelsLoading.value = true
  try {
    const params = new URLSearchParams({ provider: providerId })
    if (apiKey) params.set('api_key', apiKey)
    if (baseUrl) params.set('base_url', baseUrl)

    const resp = await fetch(`/api/models?${params}`)
    const data = await resp.json()

    if (data.error) {
      modelsError.value = data.error
      return
    }

    providerModels.value = (data.models || []).map(m => ({
      value: m.id,
      label: m.name || m.id,
    }))

    // 缓存模型列表到 localStorage 供 ChatInput 使用
    try {
      const cache = JSON.parse(localStorage.getItem('devagent-models-cache') || '{}')
      cache[providerId] = providerModels.value
      localStorage.setItem('devagent-models-cache', JSON.stringify(cache))
    } catch { /* ignore */ }

    // 如果当前选中的模型不在新列表中，自动选第一个
    if (providerModels.value.length && !providerModels.value.find(m => m.value === settings.value.model)) {
      settings.value.model = providerModels.value[0].value
    }
  } catch (e) {
    modelsError.value = `连接失败: ${e.message}`
  } finally {
    modelsLoading.value = false
  }
}

// provider 切换时自动同步 baseUrl + 拉取模型
watch(() => settings.value.provider, (newProviderId) => {
  const p = providers.find((pr) => pr.id === newProviderId)
  if (p && p.id !== 'custom') {
    settings.value.baseUrl = p.defaultBaseUrl
  }
  fetchModels(newProviderId, settings.value.apiKeys[newProviderId], settings.value.baseUrl)
})

// 当 API Key 或 Base URL 变更时重新拉取模型（防抖 800ms）
let modelFetchTimer = null
watch([() => settings.value.apiKeys[settings.value.provider], () => settings.value.baseUrl], () => {
  clearTimeout(modelFetchTimer)
  modelFetchTimer = setTimeout(() => {
    fetchModels(settings.value.provider, settings.value.apiKeys[settings.value.provider], settings.value.baseUrl)
  }, 800)
})

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
    const stored = localStorage.getItem('devagent-settings')
    if (stored) {
      const parsed = JSON.parse(stored)
      // 合并：保留新增的默认字段
      const merged = { ...structuredClone(DEFAULT_SETTINGS), ...parsed }
      settings.value = merged
    }
  } catch { /* ignore */ }

  // 初始化时拉取当前供应商的模型列表
  fetchModels(settings.value.provider, settings.value.apiKeys[settings.value.provider], settings.value.baseUrl)
})

function saveSettings() {
  try {
    localStorage.setItem('devagent-settings', JSON.stringify(settings.value))
  } catch { /* ignore */ }
  saved.value = true
  setTimeout(() => saved.value = false, 2000)
}

function resetSettings() {
  settings.value = structuredClone(DEFAULT_SETTINGS)
  saveSettings()
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
      <p class="subtitle">配置模型供应商、API Key 与参数</p>
    </header>

    <!-- ── 模型供应商 ── -->
    <div class="form-section">
      <h2>API 供应商</h2>
      <p class="section-desc">选择要使用的模型供应商，并提供对应的 API Key</p>

      <div class="provider-grid">
        <button
          v-for="p in providers"
          :key="p.id"
          class="provider-card"
          :class="{ active: settings.provider === p.id }"
          @click="settings.provider = p.id"
        >
          <span class="provider-name">{{ p.name }}</span>
          <span v-if="p.id !== 'custom'" class="provider-model-count">{{ providerModels.length || '...' }} 个模型</span>
        </button>
      </div>

      <div class="form-group">
        <label>API Key</label>
        <div class="input-with-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" stroke-width="2"/><path d="M7 11V7a5 5 0 0110 0v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input
            v-model="settings.apiKeys[settings.provider]"
            type="password"
            :placeholder="activeProvider?.id === 'custom' ? '输入完整 API Key' : `输入 ${activeProvider?.name} API Key`"
          />
        </div>
        <p class="hint">API Key 仅保存在浏览器本地存储中，不会上传到服务器。</p>
      </div>

      <div class="form-group">
        <label>API Base URL</label>
        <div class="input-with-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" stroke="currentColor" stroke-width="2"/></svg>
          <input
            v-model="settings.baseUrl"
            type="url"
            placeholder="https://api.example.com/v1"
          />
        </div>
        <p class="hint">API 端点地址。预设供应商会自动填充，切换供应商将覆盖自定义地址。</p>
      </div>
    </div>

    <!-- ── 模型与参数 ── -->
    <div class="form-section">
      <h2>模型与参数</h2>

      <div class="form-group">
        <label>模型选择
          <span v-if="modelsLoading" class="models-status loading">加载中...</span>
        </label>
        <div class="select-wrapper">
          <select v-model="settings.model" :disabled="modelsLoading">
            <template v-if="providerModels.length">
              <option v-for="m in providerModels" :key="m.value" :value="m.value">{{ m.label }}</option>
            </template>
            <option v-else value="">— 请先配置 API Key —</option>
          </select>
          <svg class="select-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <p v-if="modelsError" class="hint error">{{ modelsError }}</p>
      </div>

      <div class="form-group">
        <label>自定义模型 ID</label>
        <div class="input-with-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="2"/><path d="M8 12h8M12 8v8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input
            v-model="settings.model"
            type="text"
            placeholder="如 gpt-4o, claude-3-sonnet，填写后覆盖上方下拉选择"
          />
        </div>
        <p class="hint">直接输入模型 ID 可覆盖下拉列表中的选项，用于使用最新或未列出的模型。</p>
      </div>

      <div class="form-group">
        <label>Temperature <span class="param-value">({{ settings.temperature }})</span></label>
        <div class="slider-row">
          <span class="slider-end">0</span>
          <input v-model.number="settings.temperature" type="range" min="0" max="2" step="0.1" class="slider" />
          <span class="slider-end">2.0</span>
        </div>
        <div class="range-labels"><span>精确</span><span>平衡</span><span>创造</span></div>
        <p class="hint">越高越有创造性，越低越精确。代码生成建议 0.1-0.3。</p>
      </div>

      <div class="form-group">
        <label>最大 Token 数</label>
        <div class="preset-row">
          <button
            v-for="n in [2048, 4096, 8192, 16384, 32768]"
            :key="n"
            class="preset-chip"
            :class="{ active: settings.maxTokens === n }"
            @click="settings.maxTokens = n"
          >{{ n >= 1024 ? n / 1024 + 'K' : n }}</button>
          <input
            v-model.number="settings.maxTokens"
            type="number"
            min="512"
            max="32768"
            step="512"
            class="number-input inline"
            placeholder="自定义"
          />
        </div>
        <p class="hint">单次回复的最大 Token 数量，较大值适合长文档生成。</p>
      </div>
    </div>

    <!-- ── 版本更新 ── -->
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
      <button class="btn-reset" @click="resetSettings">
        恢复默认
      </button>
    </div>
  </div>
</template>

<style scoped>
.settings { flex: 1; overflow-y: auto; padding: 32px; max-width: 680px; margin: 0 auto; }

.settings-header { margin-bottom: 32px; }
.settings-header h1 { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.subtitle { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.form-section { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; margin-bottom: 24px; }
.form-section h2 { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
.section-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 18px; line-height: 1.5; }

/* ── 供应商卡片 ── */
.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 22px;
}
.provider-card {
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 14px 16px;
  cursor: pointer; transition: all var(--transition);
  font-family: var(--font-sans); text-align: left;
}
.provider-card:hover { border-color: var(--accent-border); background: var(--bg-hover); }
.provider-card.active {
  border-color: var(--accent-border); background: var(--accent-soft);
  box-shadow: 0 0 0 1px var(--accent-border);
}
.provider-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.provider-model-count { font-size: 11px; color: var(--text-faint); }

.form-group { margin-bottom: 20px; }
.form-group:last-child { margin-bottom: 0; }
.form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 6px; }
.param-value { font-weight: 400; color: var(--text-muted); }

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

/* ── Temperature 滑块 ── */
.slider-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
}
.slider-end { font-size: 11px; color: var(--text-faint); font-family: var(--font-mono); min-width: 24px; }
.slider-row .slider { flex: 1; }
.slider {
  appearance: none; height: 6px; background: var(--bg-card); border-radius: 3px; outline: none;
}
.slider::-webkit-slider-thumb { appearance: none; width: 18px; height: 18px; background: var(--accent); border-radius: 50%; cursor: pointer; border: 2px solid var(--bg-surface); }
.range-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-faint); padding: 0 2px; }

/* ── Token 预设芯片 ── */
.preset-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.preset-chip {
  padding: 6px 12px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-input);
  color: var(--text-muted); font-family: var(--font-mono);
  font-size: 12px; cursor: pointer; transition: all var(--transition);
}
.preset-chip:hover { border-color: var(--accent-border); color: var(--text-primary); }
.preset-chip.active {
  border-color: var(--accent-border); background: var(--accent-soft);
  color: var(--accent); font-weight: 600;
}
.number-input.inline {
  width: 90px; text-align: center; margin-left: auto;
}
.number-input {
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-md); color: var(--text-primary);
  font-family: var(--font-mono); font-size: 13px; padding: 9px 14px;
  transition: border-color var(--transition);
}
.number-input:focus { outline: none; border-color: var(--accent-border); box-shadow: 0 0 0 2px var(--accent-soft); }

.hint { font-size: 11px; color: var(--text-faint); margin-top: 6px; line-height: 1.5; }
.hint.error { color: #f87171; }
.hint.warning { color: var(--text-muted); background: var(--bg-card); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--border); margin-top: 12px; }

.models-status {
  font-size: 10px; font-weight: 500; padding: 1px 6px; border-radius: 3px;
  margin-left: 6px; vertical-align: middle;
}
.models-status.loading { background: var(--bg-card); color: var(--text-muted); }

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
  .provider-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
}
</style>
