import { ref, nextTick } from 'vue'

const SSE_TIMEOUT_MS = 60000 // 60 秒无响应超时（配合后端 5s 心跳保活）

export function useChat() {
  const messages = ref([])
  const isProcessing = ref(false)
  const statusText = ref('系统就绪')
  const conversationId = ref(null)
  const messagesRef = ref(null)

  let currentAssistant = null
  let abortController = null

  function scrollToBottom() {
    nextTick(() => {
      const el = messagesRef.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  function reset() {
    messages.value = [{
      role: 'assistant',
      content: '你好！我是 DevAgent，一个 AI 编码智能体。告诉我你的开发需求，我会自主完成：读取文件、编辑代码、运行命令、搜索代码库。',
      tools: [],
    }]
    conversationId.value = null
  }

  function cancel() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    if (isProcessing.value) {
      isProcessing.value = false
      statusText.value = '已取消'
      // 标记最后一条助手消息
      if (currentAssistant && !currentAssistant.content && currentAssistant.tools.length === 0) {
        currentAssistant.content = '（已取消）'
      }
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || isProcessing.value) return

    isProcessing.value = true
    statusText.value = 'Agent 思考中...'

    // 添加用户消息
    messages.value.push({
      role: 'user',
      content: text,
      tools: [],
    })
    scrollToBottom()

    // 创建助手消息容器
    currentAssistant = {
      role: 'assistant',
      content: '',
      tools: [],
    }
    messages.value.push(currentAssistant)
    scrollToBottom()

    try {
      await streamChat(text)
    } catch (err) {
      if (err.name === 'AbortError') {
        currentAssistant.content += `\n\n（已取消）`
      } else {
        currentAssistant.content += `\n\n**错误:** ${err.message}`
      }
    } finally {
      abortController = null
      isProcessing.value = false
      if (statusText.value === 'Agent 思考中...' || statusText.value.startsWith('执行:')) {
        statusText.value = '系统就绪'
      }
    }
  }

  function streamChat(message) {
    abortController = new AbortController()

    return new Promise((resolve, reject) => {
      // 读取前端设置并传递给后端
      let settings = null
      try {
        const stored = localStorage.getItem('devagent-settings')
        if (stored) {
          const parsed = JSON.parse(stored)
          settings = {
            api_key: parsed.apiKeys?.[parsed.provider] || '',
            base_url: parsed.baseUrl || '',
            model: parsed.model || '',
            temperature: parsed.temperature,
            max_tokens: parsed.maxTokens,
          }
        }
      } catch { /* ignore */ }

      const body = { message }
      if (conversationId.value) {
        body.conversation_id = conversationId.value
      }
      if (settings) {
        body.settings = settings
      }

      // SSE 超时兜底：3 分钟无任何数据则中止
      let sseTimer = setTimeout(() => {
        if (abortController) {
          abortController.abort()
        }
      }, SSE_TIMEOUT_MS)

      fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortController.signal,
      }).then(res => {
        if (!res.ok) {
          clearTimeout(sseTimer)
          reject(new Error(`HTTP ${res.status}`))
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = null

        function read() {
          reader.read().then(({ done, value }) => {
            if (done) {
              clearTimeout(sseTimer)
              resolve()
              return
            }

            // 收到数据，重置超时
            clearTimeout(sseTimer)
            sseTimer = setTimeout(() => {
              if (abortController) abortController.abort()
            }, SSE_TIMEOUT_MS)

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim()
              } else if (line.startsWith('data: ') && currentEvent) {
                try {
                  const data = JSON.parse(line.slice(6))
                  handleEvent(currentEvent, data)
                } catch (e) {
                  // 忽略解析错误
                }
                currentEvent = null
              }
            }

            read()
          }).catch((err) => {
            clearTimeout(sseTimer)
            reject(err)
          })
        }

        read()
      }).catch((err) => {
        clearTimeout(sseTimer)
        reject(err)
      })
    })
  }

  function handleEvent(type, data) {
    switch (type) {
      case 'tool_start':
        currentAssistant.tools.push({
          name: data.tool,
          args: data.args || {},
          content: data.content || '',
          result: '',
          expanded: false,
          done: false,
        })
        statusText.value = `执行: ${data.tool}`
        scrollToBottom()
        break

      case 'tool_result':
        if (currentAssistant.tools.length > 0) {
          const last = currentAssistant.tools[currentAssistant.tools.length - 1]
          last.result = data.content || ''
          last.done = true
        }
        statusText.value = 'Agent 思考中...'
        scrollToBottom()
        break

      case 'text':
        currentAssistant.content += data.content
        scrollToBottom()
        break

      case 'error':
        currentAssistant.tools.push({
          name: 'error',
          args: {},
          content: data.content,
          result: '',
          expanded: false,
          done: true,
          isError: true,
        })
        scrollToBottom()
        break

      case 'done':
        if (data.conversation_id) {
          conversationId.value = data.conversation_id
        }
        if (!currentAssistant.content && currentAssistant.tools.length === 0) {
          currentAssistant.content = '（无回复）'
        }
        break
    }
  }

  return {
    messages,
    isProcessing,
    statusText,
    conversationId,
    messagesRef,
    sendMessage,
    cancel,
    reset,
    scrollToBottom,
  }
}
