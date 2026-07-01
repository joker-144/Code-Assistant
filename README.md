# DevAgent

AI 编码智能体 — **Agent + 工具集**范式（Cursor / Claude Code 风格）

单核心 AgentLoop + Function Calling 工具集，LLM 自主决策执行路径。

---

## 核心特性

- **Agentic Loop** — 单核心循环替代固定流水线，LLM 自主决定何时读文件、编辑代码、运行命令
- **Function Calling** — LLM 通过标准工具调用协议自主选择工具和参数
- **项目代码库理解** — 文件分块 + 本地 Embedding + 语义搜索，Agent 能"看到"整个项目
- **流式输出** — CLI 和 Web 实时展示 Agent 的思考和工具调用过程
- **SQLite 统一存储** — 对话历史 + 代码库索引 + 经验教训，单一数据库
- **Provider 可切换** — 通过 OpenAI 兼容协议接入 DeepSeek / Qwen / OpenAI / 本地模型

---

## 架构

```
src/dev_agent/
├── agent/              # Agent 核心
│   ├── loop.py         # Agentic Loop — LLM 自主决策的核心循环
│   └── system_prompt.py
├── llm/                # LLM 客户端层
│   ├── client.py       # function calling + streaming
│   └── provider.py     # Provider 预设（DeepSeek/Qwen/OpenAI/本地）
├── tools/              # 工具层（function calling schema + 执行）
│   ├── engine.py       # 工具引擎 — 注册/schema 生成/调度
│   ├── file_ops.py     # read_file / write_file / edit_file / list_dir
│   ├── search.py       # search_code — 语义搜索代码库
│   ├── shell.py        # run_command
│   └── git.py          # git_status / git_diff / git_log / git_commit
├── context/            # 上下文管理
│   ├── manager.py      # 上下文管理器
│   ├── history.py      # 对话历史 + 摘要压缩
│   ├── tokenizer.py    # tiktoken 精确计数
│   └── index.py        # ProjectIndex — 代码库 Embedding 索引
├── memory/
│   └── store.py        # SQLite 统一存储
├── config.py           # 配置（单模型 + Provider 可切换）
├── cli.py              # CLI 交互式 REPL
└── api.py              # FastAPI + SSE 流式接口
```

---

## 安装

```bash
pip install -e .
```

## 配置

在项目根目录创建 `.env` 文件：

```env
# LLM 配置（通过 OpenAI 兼容协议，切换 Provider 只需改这三行）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 可选参数
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=8192
LLM_MAX_TOOL_ROUNDS=20

# 记忆系统
MEMORY_SQLITE_PATH=data/memory.db
MEMORY_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
```

### 切换 Provider

| Provider | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| 本地 | `http://localhost:11434/v1` | `qwen2.5` |

---

## 快速开始

### 1. 索引项目（启用语义搜索）

```bash
dev-agent index
```

首次运行会下载 Embedding 模型（~100MB），之后离线可用。后续增量索引，仅处理修改过的文件。

### 2. Web 界面（推荐）

```bash
dev-agent serve
```

打开浏览器访问 `http://localhost:8000`，实时查看 Agent 的工具调用过程。

### 3. CLI 交互

```bash
dev-agent chat
```

支持的命令：

| 命令 | 说明 |
|---|---|
| `/help` | 显示帮助 |
| `/clear` | 清空当前对话上下文 |
| `/tokens` | 查看当前 token 使用情况 |
| `/index` | 索引项目代码库 |
| `/stats` | 查看记忆系统统计 |
| `/exit` | 退出 |

---

## Agent 工具集

Agent 可自主调用以下工具：

| 工具 | 说明 |
|---|---|
| `read_file` | 读取文件内容（支持行号范围） |
| `write_file` | 创建或覆写文件 |
| `edit_file` | 搜索-替换精准编辑（diff，优于整文件重写） |
| `list_dir` | 列出目录内容 |
| `search_code` | 语义搜索代码库（基于 Embedding） |
| `run_command` | 执行 Shell 命令 |
| `git_status` | 查看 Git 状态 |
| `git_diff` | 查看代码变更 |
| `git_log` | 查看提交历史 |
| `git_commit` | 提交变更 |

---

## API

启动 API 服务后，访问 `http://localhost:8000/docs` 查看完整文档。

### SSE 流式对话

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "查看项目结构"}'
```

事件类型：`tool_start` / `tool_result` / `text` / `error` / `done`

### 其他接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | Web 界面 |
| `GET` | `/health` | 健康检查 |
| `POST` | `/chat/stream` | SSE 流式对话 |
| `POST` | `/conversations` | 创建对话 |
| `GET` | `/conversations/{id}/messages` | 获取对话消息 |
| `POST` | `/index` | 索引项目代码库 |
| `GET` | `/memory/stats` | 记忆系统统计 |

---

## 工作原理

DevAgent 的核心是一个 **Agentic Loop**：

```
用户输入 → ContextManager.add_user_message()
    ↓
┌─ 循环 ─────────────────────────────────────┐
│  1. build_messages() 构建 LLM 输入          │
│  2. llm.chat_with_tools() 调用 LLM          │
│  3. if response.has_tool_calls:             │
│       → 执行工具 → 结果加入上下文 → 继续循环  │
│     else:                                   │
│       → 返回文本 → 结束循环                  │
└─────────────────────────────────────────────┘
```

**关键差异**：LLM 自主决定下一步做什么——是否读文件？是否搜索代码？是否运行测试？何时认为任务完成？这些决策不再是 Python 硬编码的 `if/elif`，而是 LLM 的推理结果。

---

## 技术栈

| 组件 | 技术 |
|---|---|
| LLM 协议 | OpenAI 兼容（function calling + streaming） |
| Embedding | sentence-transformers + BAAI/bge-small-zh-v1.5 |
| 存储 | SQLite |
| Token 计数 | tiktoken |
| CLI | Typer + Rich |
| API | FastAPI + SSE |
| Web | 原生 HTML/CSS/JS |

---

## License

MIT
