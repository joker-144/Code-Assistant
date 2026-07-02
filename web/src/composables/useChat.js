import { ref, nextTick, reactive } from 'vue'

const API_BASE = 'http://localhost:8000'

export function useChat() {
  const messages = ref([])
  const isProcessing = ref(false)
  const statusText = ref('系统就绪')
  const conversationId = ref(null)
  const messagesRef = ref(null)

  const agentStates = reactive([
    { id: 'planner', icon: '🧠', name: '规划Agent', status: '待命中', active: false },
    { id: 'coder', icon: '⚡', name: '编码Agent', status: '待命中', active: false },
    { id: 'reviewer', icon: '🔍', name: '审查Agent', status: '待命中', active: false },
  ])

  let currentAssistant = null

  function scrollToBottom() {
    nextTick(() => {
      const el = messagesRef.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  function resetAgents() {
    agentStates.forEach(a => { a.status = '待命中'; a.active = false })
  }

  function reset() {
    messages.value = [{
      role: 'assistant',
      content: '你好！我是 DevAgent，一个 AI 多智能体协作编码助手。\n\n' +
        '我由三个智能体组成：\n' +
        '- **🧠 规划Agent** — 需求分析 + 任务拆解 + 自我改进\n' +
        '- **⚡ 编码Agent** — 代码生成 + 技术栈识别 + 规范约束\n' +
        '- **🔍 审查Agent** — 代码审查 + Bug检测 + 性能优化\n\n' +
        '告诉我你的开发需求，我会自主协作完成！',
      tools: [],
    }]
    conversationId.value = null
    resetAgents()
  }

  function addMessage(role, content, label) {
    const msg = { role, content, tools: [] }
    messages.value.push(msg)
    scrollToBottom()
    return msg
  }

  async function sendMessage(text) {
    if (!text.trim() || isProcessing.value) return

    isProcessing.value = true
    statusText.value = 'Agent 思考中...'

    addMessage('user', text)

    // 创建助手消息容器
    let assistantMsg = null
    let textBuffer = ''

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId.value,
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let leftover = ''

      const READ_TIMEOUT = 30000 // 单个 chunk 读取超时 30 秒

      // eslint-disable-next-line no-constant-condition
      while (true) {
        // 用 Promise.race 给 reader.read() 加上超时保护
        let readResult
        try {
          readResult = await Promise.race([
            reader.read(),
            new Promise((_, reject) =>
              setTimeout(() => reject(new Error('READ_TIMEOUT')), READ_TIMEOUT)
            ),
          ])
        } catch (raceErr) {
          if (raceErr.message === 'READ_TIMEOUT') {
            reader.cancel() // 取消读取
            if (assistantMsg && textBuffer) {
              assistantMsg.content = textBuffer + '\n\n⚠️ 响应超时，DeepSeek 流式输出中断，请重试。'
            } else {
              addMessage('assistant', '⚠️ 响应超时，DeepSeek 流式输出中断，请重试。')
            }
            statusText.value = '响应超时'
            break
          }
          throw raceErr
        }

        const { done, value } = readResult
        if (done) break

        leftover += decoder.decode(value, { stream: true })
        const lines = leftover.split('\n')
        leftover = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              switch (eventType || 'text') {
                case 'tool_start': {
                  if (!assistantMsg) assistantMsg = addMessage('assistant', '')
                  assistantMsg.tools.push({
                    name: data.tool,
                    args: data.args || {},
                    content: data.content || '',
                    result: '',
                    expanded: false,
                    done: false,
                  })
                  updateAgentByTool(data.tool, '执行中...')
                  statusText.value = `执行: ${data.tool}`
                  break
                }

                case 'tool_result': {
                  if (assistantMsg && assistantMsg.tools.length > 0) {
                    const last = assistantMsg.tools[assistantMsg.tools.length - 1]
                    last.result = data.content || ''
                    last.done = true
                  }
                  statusText.value = 'Agent 思考中...'
                  break
                }

                case 'text': {
                  if (!assistantMsg) assistantMsg = addMessage('assistant', '')
                  textBuffer += data.content
                  assistantMsg.content = textBuffer
                  break
                }

                case 'error': {
                  if (!assistantMsg) assistantMsg = addMessage('assistant', '')
                  assistantMsg.tools.push({
                    name: 'error',
                    args: {},
                    content: data.content,
                    result: '',
                    expanded: false,
                    done: true,
                    isError: true,
                  })
                  break
                }

                case 'done': {
                  if (data.conversation_id) {
                    conversationId.value = data.conversation_id
                  }
                  if (!assistantMsg && textBuffer) {
                    addMessage('assistant', textBuffer)
                  } else if (assistantMsg && textBuffer) {
                    assistantMsg.content = textBuffer
                  }
                  agentStates.forEach(a => {
                    if (a.active) { a.status = '已完成'; a.active = false }
                  })
                  break
                }
              }
              scrollToBottom()
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    } catch (err) {
      addMessage('assistant', `⚠️ 请求失败: ${err.message}`)
      console.error('SSE error:', err)
      statusText.value = '连接失败'
    } finally {
      isProcessing.value = false
      if (statusText.value !== '响应超时') {
        statusText.value = '系统就绪'
      }
    }
  }

  function updateAgentByTool(toolName, status) {
    const mappings = {
      plan: 'planner', planner: 'planner',
      list_dir: 'planner', search_code: 'planner', read_file: 'planner',
      list_skills: 'planner', load_skill: 'planner',
      write_file: 'coder', edit_file: 'coder', code: 'coder',
      run_command: 'coder', shell: 'coder',
      review: 'reviewer', git_status: 'reviewer', git_diff: 'reviewer',
    }
    const agentId = mappings[toolName]
    if (agentId) {
      const agent = agentStates.find(a => a.id === agentId)
      if (agent) {
        agent.status = status
        agent.active = true
      }
    }
  }

  return {
    messages, isProcessing, statusText, conversationId,
    messagesRef, agentStates,
    sendMessage, reset, scrollToBottom,
  }
}
