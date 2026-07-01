# DevAgent

> AI 编码智能体 — 基于 **Agent + 工具集** 范式（Cursor / Claude Code 风格），让 LLM 自主决策执行路径。

DevAgent 是一个面向 Windows 本地开发的 AI 编码助手。它采用单核心 **Agentic Loop** 架构，通过 Function Calling 让 LLM 自主选择和调用工具（读文件、编辑代码、搜索代码库、运行命令、Git 操作），实现从自然语言到代码生成、错误修复、项目理解的完整开发辅助流程。

与传统的"固定流水线"多智能体系统不同，DevAgent 中的 LLM 拥有完整的自主决策能力——它会在每一轮推理中根据当前上下文，决定下一步做什么：是读取一个文件了解现有代码？是搜索代码库找到相关实现？是运行测试验证结果？还是直接给出最终回复？这些决策由 LLM 实时推理完成，而非 Python 硬编码的流程分支。

---

## 核心特性

### Agent 自主决策

- **Agentic Loop** — 单核心循环替代固定流水线，LLM 自主决定何时读文件、编辑代码、运行命令
- **Function Calling** — LLM 通过标准 OpenAI 工具调用协议自主选择工具和参数，无需人工编排
- **多轮工具调用** — 单次任务中可连续调用多个工具（如读文件 → 分析 → 编辑 → 运行测试 → 修复），最多 20 轮

### 项目理解能力

- **代码库语义索引** — 文件分块 + 向量检索，基于智谱云端 Embedding-3
- **`search_code` 工具** — Agent 可用自然语言搜索代码库，找到相关实现，而非盲目猜测
- **增量索引** — 首次索引后仅处理修改过的文件，通过文件 hash 检测变更

### 开发体验

- **流式输出** — CLI 和 Web 实时展示 Agent 的思考过程和工具调用详情，无需等待完整执行
- **diff 精准编辑** — `edit_file` 工具通过搜索-替换方式只修改指定行，保留文件其余部分（优于整文件重写）
- **交互式 REPL** — CLI 支持多轮对话，上下文自动关联
- **SSE 流式 API** — Web 前端通过 Server-Sent Events 实时接收 Agent 输出

### 轻量部署

- **SQLite 统一存储** — 对话历史 + 代码库索引 + 经验教训，单一数据库文件，零外部依赖
- **Provider 可切换** — 通过 OpenAI 兼容协议接入 DeepSeek / Qwen / OpenAI / 本地模型，一行配置切换


---

## 架构设计

### 整体架构

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                   Agentic Loop                       │
│                                                      │
│  ┌─────────────┐    tool_calls    ┌──────────────┐  │
│  │  LLM Client  │ ──────────────→ │  Tool Engine  │  │
│  │  (DeepSeek)  │ ←────────────── │  (13 个工具)  │  │
│  └─────────────┘   tool_result    └──────────────┘  │
│         ↑                                            │
│         │ messages                                    │
│  ┌─────────────┐                                     │
│  │   Context    │ ┌─ ChatHistory (对话历史+摘要)      │
│  │  Manager     │ ├─ ProjectIndex (代码库Embedding)   │
│  │              │ └─ TokenBudget  (token预算管理)     │
│  └─────────────┘                                     │
│                                                      │
│  输出 ──→ CLI / Web / API (SSE 流式)                  │
└─────────────────────────────────────────────────────┘
```

### Agentic Loop 工作原理

DevAgent 的核心是一个 **Agentic Loop（智能体循环）**，替代了传统多智能体系统的固定流水线：

1. **接收用户输入** — 将用户需求加入对话上下文
2. **构建 LLM 输入** — ContextManager 组装 system prompt + 对话历史 + 工具定义
3. **调用 LLM** — 通过 Function Calling 协议发送给 LLM（如 DeepSeek）
4. **判断响应** — LLM 返回 `tool_calls`（要调用工具）还是纯文本（最终回复）
5. **执行工具** — 若 LLM 请求调用工具，ToolEngine 执行对应工具（如 `read_file`）
6. **结果回传** — 工具执行结果加入上下文，回到步骤 2 继续循环
7. **结束** — LLM 返回纯文本回复，流式输出给用户，循环结束

**关键差异**：在循环中，LLM 自主决定下一步做什么——是否读文件、是否搜索代码、是否运行测试、何时任务完成。这些决策不再是 Python 硬编码的 `if/elif` 分支，而是 LLM 根据上下文的推理结果。

### 目录结构

```
src/dev_agent/
├── agent/                  # Agent 核心
│   ├── loop.py             # Agentic Loop — LLM 自主决策的核心循环
│   └── system_prompt.py     # System prompt 模板管理
├── llm/                    # LLM 客户端层
│   ├── client.py           # 支持 function calling + streaming 的客户端
│   └── provider.py         # Provider 预设（DeepSeek/Qwen/OpenAI/本地）
├── tools/                  # 工具层（function calling schema + 执行）
│   ├── engine.py           # 工具引擎 — 注册 / schema 生成 / 调度
│   ├── file_ops.py         # read_file / write_file / edit_file / list_dir
│   ├── search.py           # search_code — 语义搜索代码库
│   ├── shell.py            # run_command — Shell 命令执行（asyncio）
│   └── git.py              # git_status / git_diff / git_log / git_commit / git_branch / git_add / git_create_branch
├── context/                # 上下文管理
│   ├── manager.py          # 上下文管理器 — 构建 LLM 输入 + token 预算
│   ├── history.py          # 对话历史 + LLM 摘要压缩
│   ├── tokenizer.py        # tiktoken 精确 token 计数
│   └── index.py            # ProjectIndex — 代码库 Embedding 索引
├── memory/
│   └── store.py            # SQLite 统一存储
├── config.py               # 配置（单模型 + Provider 可切换）
├── cli.py                  # CLI 交互式 REPL
└── api.py                  # FastAPI + SSE 流式接口
```

### Web 前端结构

```
web/
├── package.json            # Vue 3 + marked + highlight.js
├── vite.config.js          # Vite 构建 + 开发代理
├── index.html              # 入口 HTML
├── src/
│   ├── main.js             # 应用入口
│   ├── App.vue             # 主布局（侧边栏 + 聊天区）
│   ├── style.css           # 设计系统（浅色主题 + CSS 变量）
│   ├── composables/
│   │   └── useChat.js      # SSE 流式对话逻辑
│   └── components/
│       ├── Sidebar.vue       # 左侧栏（Logo/状态/操作按钮）
│       ├── ChatMessage.vue   # 消息渲染（Markdown + 代码高亮）
│       ├── ToolCall.vue      # 工具调用卡片（可折叠）
│       ├── ChatInput.vue     # 输入框（自适应高度）
│       ├── IndexModal.vue    # 索引模态框（增量/全量）
│       └── StatsModal.vue    # 记忆统计面板
└── dist/                   # 构建产物（FastAPI 托管）
```

### 数据存储

所有数据存储在单一 SQLite 数据库中，包含以下表：

| 表名 | 用途 |
|---|---|
| `conversations` | 对话会话记录 |
| `messages` | 消息历史（含工具调用日志） |
| `file_index` | 代码库文件分块索引 + Embedding 向量 |
| `lessons` | 经验教训（跨会话积累） |

---

## 环境要求

- **Python** >= 3.11
- **操作系统** — Windows 10/11（主要支持），兼容 Linux / macOS
- **LLM API Key** — DeepSeek / Qwen / OpenAI 任选其一
- **磁盘空间** — 约 100MB（SQLite 数据库及项目依赖）

---

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/yourname/dev-agent.git
cd dev-agent
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -e .
```

这会安装所有依赖，包括：
- `openai` — LLM 客户端（支持 function calling + streaming）
- `tiktoken` — 精确 token 计数
- `fastapi` + `uvicorn` — API 服务
- `typer` + `rich` — CLI 交互
- `pydantic-settings` — 配置管理
- `numpy` — 向量相似度计算

### 4. 构建前端（可选，使用 Web 界面时需要）

```bash
cd web
npm install
npm run build    # 构建到 web/dist/，FastAPI 自动托管
cd ..
```

> 开发模式下可用 `npm run dev` 启动 Vite 开发服务器（热更新），API 请求自动代理到 8000 端口。

### 5. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# ── 对话 LLM 配置 ──
# 通过 OpenAI 兼容协议，切换 Provider 只需改这三行
LLM_CHAT_API_KEY=your_api_key
LLM_CHAT_BASE_URL=https://api.deepseek.com
LLM_CHAT_MODEL=deepseek-chat

# 可选参数
LLM_CHAT_TEMPERATURE=0.3
LLM_CHAT_MAX_TOKENS=8192
LLM_CHAT_MAX_TOOL_ROUNDS=20

# ── 记忆系统 ──
MEMORY_SQLITE_PATH=data/memory.db

# ── Embedding LLM 配置（代码库语义搜索）──
# 使用智谱云端 Embedding-3，需申请 API Key
LLM_EMBEDDING_API_KEY=your_zhipu_api_key
LLM_EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_EMBEDDING_MODEL=embedding-3
LLM_EMBEDDING_DIMENSIONS=1024
```

### 切换 Provider

DevAgent 通过 OpenAI 兼容协议支持多个 LLM Provider，切换时只需修改 `.env` 中的三行配置：

| Provider | `LLM_CHAT_BASE_URL` | `LLM_CHAT_MODEL` | 获取 API Key |
|---|---|---|---|
| **DeepSeek**（推荐） | `https://api.deepseek.com` | `deepseek-chat` | [platform.deepseek.com](https://platform.deepseek.com) |
| **Qwen** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | [dashscope.aliyun.com](https://dashscope.aliyun.com) |
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o` | [platform.openai.com](https://platform.openai.com) |
| **本地 (Ollama)** | `http://localhost:11434/v1` | `qwen2.5` | 无需 Key |

> **注意**：Function Calling 能力因模型而异。DeepSeek 和 OpenAI 对 function calling 支持最稳定；本地模型（如 Ollama 跑 Qwen2.5）的 tool use 稳定性可能较差，建议优先使用 DeepSeek。

---

## 快速开始

### 1. 索引项目（启用语义搜索）

```bash
dev-agent index
```

#### 智谱云端模式
在 `.env` 中配置 `LLM_EMBEDDING_API_KEY`，直接调用智谱云端 API。

索引过程会：
- 遍历项目中的源代码文件（`.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.c`, `.cpp`, `.h`, `.md` 等）
- 按函数/类边界分块
- 为每个块生成 Embedding 向量
- 存入 SQLite 数据库

后续运行时仅索引修改过的文件（通过文件 hash 检测变更），实现增量更新。

### 2. Web 界面（推荐）

```bash
dev-agent serve
```

打开浏览器访问 `http://localhost:8000`，你可以：
- 输入自然语言描述开发需求
- 实时查看 Agent 的思考过程
- 查看每一步工具调用的详情和结果
- 支持多轮对话上下文关联

### 3. CLI 交互

```bash
# 交互式对话模式（推荐日常使用）
dev-agent chat

# 单次执行模式
dev-agent run "用 Python 写一个函数，返回列表的最大值和最小值之差"
```

#### CLI 命令列表

在交互式对话模式中，支持以下命令：

| 命令 | 说明 |
|---|---|
| `/help` | 显示帮助信息 |
| `/clear` | 清空当前对话上下文（开始新对话） |
| `/tokens` | 查看当前 token 使用情况 |
| `/index` | 重新索引项目代码库 |
| `/stats` | 查看记忆系统统计信息 |
| `/exit` | 退出程序 |

### 4. 使用示例

#### 示例 1：生成代码

```
❯ 帮我写一个 FastAPI 应用，包含 /health 健康检查端点和 /items 的 CRUD 接口

[工具 read_file] → 读取 pyproject.toml 了解项目依赖
[工具 search_code] → 搜索项目中是否已有类似的 API 实现
[工具 write_file] → 创建 src/api/main.py
[工具 edit_file] → 在 main.py 中添加 CRUD 端点
[工具 run_command] → 运行 uvicorn 验证应用启动

✅ 已创建 FastAPI 应用，包含健康检查和 CRUD 接口。
   启动命令：uvicorn src.api.main:app --reload
```

#### 示例 2：修复错误

```
❯ 运行测试报错了，帮我看看

[工具 run_command] → 运行 pytest 查看错误信息
[工具 read_file] → 读取报错的测试文件
[工具 read_file] → 读取被测的源代码文件
[工具 edit_file] → 修复源代码中的 bug
[工具 run_command] → 重新运行测试验证修复

✅ 问题已修复。原因是 xxx 函数在处理空列表时未做边界检查...
```

#### 示例 3：理解代码库

```
❯ 这个项目的认证逻辑在哪里？

[工具 search_code] → 语义搜索 "认证 auth login token"
[工具 read_file] → 读取 auth.py 文件内容
[工具 search_code] → 搜索 "JWT token verify"

✅ 项目的认证逻辑在 src/auth/jwt_handler.py 中，
   主要流程是：用户登录 → 生成 JWT → 中间件验证...
```

---

## Agent 工具集

Agent 在推理过程中可自主调用以下工具。每个工具都定义为标准 OpenAI Function Calling schema，LLM 根据上下文决定调用哪个工具、传递什么参数。

### 文件操作

| 工具 | 参数 | 说明 |
|---|---|---|
| `read_file` | `path`, `start_line?`, `end_line?` | 读取文件内容，支持指定行号范围 |
| `write_file` | `path`, `content` | 创建或覆写文件（自动创建父目录） |
| `edit_file` | `path`, `old_str`, `new_str` | 搜索-替换精准编辑（diff），只修改匹配部分 |
| `list_dir` | `path` | 列出目录内容 |

### 代码搜索

| 工具 | 参数 | 说明 |
|---|---|---|
| `search_code` | `query`, `top_k?` | 语义搜索代码库，返回最相关的代码片段 |

### 命令执行

| 工具 | 参数 | 说明 |
|---|---|---|
| `run_command` | `command`, `timeout?` | 执行 Shell 命令（如 pytest、npm install 等） |

### Git 操作

| 工具 | 参数 | 说明 |
|---|---|---|
| `git_status` | — | 查看工作区状态 |
| `git_diff` | `cached?` | 查看代码变更（支持 `--cached` 暂存区） |
| `git_log` | `count?` | 查看提交历史 |
| `git_commit` | `message` | 提交变更 |
| `git_branch` | — | 查看所有分支 |
| `git_add` | `path?` | 添加文件到暂存区 |
| `git_create_branch` | `name` | 创建并切换到新分支 |

### diff 编辑的优势

`edit_file` 工具采用搜索-替换（str_replace）模式，相比整文件重写有以下优势：

- **节省 token** — 只传输改动部分，不传输整个文件
- **保留未改动代码** — 避免整文件重写时丢失或误改
- **精确控制** — Agent 明确知道改了什么
- **可审查** — 用户可以清晰看到每一处改动

---

## API 文档

启动 API 服务后，访问 `http://localhost:8000/docs` 查看 Swagger 交互式文档。

### SSE 流式对话

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "查看项目结构并写一个 README"}'
```

SSE 事件类型：

| 事件 | 说明 |
|---|---|
| `tool_start` | Agent 开始调用工具（含工具名和参数） |
| `tool_result` | 工具执行完成（含结果摘要） |
| `text` | Agent 的文本输出（流式 token） |
| `error` | 执行出错 |
| `done` | 任务完成 |

### REST API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | Web 交互界面 |
| `GET` | `/health` | 健康检查 |
| `POST` | `/chat/stream` | SSE 流式对话 |
| `POST` | `/conversations` | 创建新对话 |
| `GET` | `/conversations/{id}/messages` | 获取对话消息历史 |
| `POST` | `/index` | 索引项目代码库 |
| `GET` | `/memory/stats` | 记忆系统统计 |

---

## 技术栈

| 组件 | 技术 | 说明 |
|---|---|---|
| LLM 协议 | OpenAI 兼容 | 支持 function calling + streaming |
| 默认模型 | DeepSeek (`deepseek-chat`) | 国内访问无障碍，性价比高 |
| Embedding | 智谱 Embedding-3（云端，1024 维） | 中英文支持，调用云端 API |
| 存储 | SQLite | 单文件数据库，零外部依赖 |
| Token 计数 | `tiktoken` | 精确计算，支持上下文窗口管理 |
| CLI | Typer + Rich | 交互式 REPL + 彩色输出 |
| API | FastAPI + Uvicorn | 高性能异步框架 |
| 流式输出 | SSE (Server-Sent Events) | 实时推送 Agent 输出 |
| Web 前端 | Vue 3 + Vite | 组件化 SPA，Markdown 渲染 + 代码高亮 |
| 配置管理 | pydantic-settings | 类型安全的环境变量加载 |
| Git 操作 | GitPython | Pythonic 的 Git 接口 |

---

## 配置参考

### 完整配置项

```env
# ── 对话 LLM 配置 ──
LLM_CHAT_API_KEY=your_api_key                    # API Key（必填）
LLM_CHAT_BASE_URL=https://api.deepseek.com       # API 地址（必填）
LLM_CHAT_MODEL=deepseek-chat                      # 模型名称（必填）
LLM_CHAT_TEMPERATURE=0.3                          # 生成温度（默认 0.3）
LLM_CHAT_MAX_TOKENS=8192                          # 单次最大 token（默认 8192）
LLM_CHAT_TIMEOUT=120.0                            # 请求超时秒数（默认 120）
LLM_CHAT_MAX_TOOL_ROUNDS=20                      # 最大工具调用轮数（默认 20）

# ── 记忆系统 ──
MEMORY_SQLITE_PATH=data/memory.db            # SQLite 数据库路径

# ── Embedding LLM 配置 ──
LLM_EMBEDDING_API_KEY=your_zhipu_api_key   # 智谱 API Key（必填）
LLM_EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4  # 智谱 API 地址
LLM_EMBEDDING_MODEL=embedding-3             # Embedding 模型
LLM_EMBEDDING_DIMENSIONS=1024               # 向量维度

# ── Agent 配置 ──
DEV_AGENT_MAX_CONTEXT_TOKENS=60000           # 上下文窗口上限（token）
DEV_AGENT_SUMMARY_TRIGGER_TOKENS=45000       # 触发摘要压缩的阈值
DEV_AGENT_WORKSPACE=.                         # 工作区路径
```

> **注意**：`verbose` 配置项已移除。

### 安全注意事项

- `run_command` 工具会执行 Shell 命令，Agent 可能执行任意命令。在生产环境中建议：
  - 限制工作区路径范围
  - 对危险命令设置确认机制
  - 在容器或沙箱中运行
- `.env` 文件包含 API Key，请确保已加入 `.gitignore`

---

## 开发指南

### 开发模式安装

```bash
pip install -e ".[dev]"
```

### 项目结构说明

| 目录 | 职责 |
|---|---|
| `src/dev_agent/agent/` | Agent 核心 — Agentic Loop 和 system prompt |
| `src/dev_agent/llm/` | LLM 客户端层 — function calling + streaming |
| `src/dev_agent/tools/` | 工具层 — 每个工具一个文件，通过 engine 注册 |
| `src/dev_agent/context/` | 上下文管理 — 历史管理、token 计数、代码库索引 |
| `src/dev_agent/memory/` | SQLite 统一存储 |
| `web/` | Web 前端（Vue 3 + Vite） |
| `prompts/` | Prompt 模板文件 |

### 添加自定义工具

1. 在 `src/dev_agent/tools/` 下创建新文件
2. 定义工具的 JSON schema（OpenAI function calling 格式）
3. 实现工具执行函数
4. 在 `tools/engine.py` 中注册

```python
# tools/custom.py
CUSTOM_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "描述这个工具做什么",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入参数"}
            },
            "required": ["input"]
        }
    }
}

class CustomTool:
    async def my_tool(self, input: str) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, data="结果")

# tools/engine.py 中注册
self.register("my_tool", custom_tool.my_tool, CUSTOM_TOOL_SCHEMA)
```

---

## License

本项目基于 **MIT 协议** 开源。你可以自由使用、修改、分发和商用，只需保留原始版权声明。

```
MIT License

Copyright (c) 2026 DevAgent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
