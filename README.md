# DevAgent

> AI 编码智能体 v0.5.0 — 从零到可用的日常开发助手

DevAgent 是一个命令行 AI 编码助手，集成代码审查、代码解释、Bug 修复、测试生成、Git 提交流程等日常开发场景。基于 Agentic Loop 架构，LLM 自主选择工具完成开发任务；支持多 Agent 协同模式处理复杂需求。

---

## 安装

### 方式 1：下载安装程序（Windows，推荐）

前往 [GitHub Releases](https://github.com/your-org/Code-Assistant/releases) 页面，下载最新版本的 `DevAgent-*-Setup.exe`，双击运行即可完成安装。安装后 `dev-agent` 命令会自动添加到 PATH。

### 方式 2：从 PyPI 安装（跨平台）

```bash
pip install dev-agent
```

支持 `dev-agent update` 自动升级到最新版本。

### 方式 3：从源码安装

```bash
git clone https://github.com/your-org/Code-Assistant.git
cd Code-Assistant
pip install -e .
```

### 方式 4：从 wheel 安装

```bash
# 构建
python -m build --wheel --outdir dist

# 安装
pip install dist/dev_agent-*.whl
```

### 配置私有 PyPI 源（可选）

如果你使用私有 PyPI 仓库（如 Nexus、Artifactory、GitLab Package Registry）：

```bash
# 发布到私有 PyPI
python -m twine upload --repository-url https://your-private-pypi.example.com/simple/ dist/*

# 用户安装时指定源
pip install dev-agent --index-url https://your-private-pypi.example.com/simple/
```

## 5 分钟上手

### 1. 配置

运行交互式配置向导，按提示填入 API Key：

```bash
dev-agent init
```

支持 DeepSeek、Qwen、OpenAI 及任意 OpenAI 兼容提供商。

### 3. 开始使用

```bash
# 代码审查
dev-agent review src/main.py

# 解释代码逻辑
dev-agent explain src/utils.py

# 修复 Bug
dev-agent fix src/broken.py

# 生成单元测试
dev-agent test src/calculator.py

# 结合管道使用
git diff | dev-agent review
cat mystery.py | dev-agent explain

# 交互式对话（完全自主模式）
dev-agent chat
```

---

## 日常开发场景

### 代码审查 (`dev-agent review`)

对文件或 git diff 做全面审查，关注逻辑正确性、安全隐患、性能问题、代码风格、可维护性。

```bash
# 审查单个文件
dev-agent review src/main.py

# 审查当前未提交的变更
git diff | dev-agent review

# 审查 staged 变更
git diff --cached | dev-agent review

# JSON 输出（方便集成到其他工具）
dev-agent review --json src/main.py
```

### 解释代码 (`dev-agent explain`)

用通俗语言解释代码逻辑、数据流和设计思路。

```bash
dev-agent explain src/complex_algorithm.py
```

### 修复问题 (`dev-agent fix`)

分析并修复语法错误、逻辑 bug、lint 警告、代码异味。

```bash
dev-agent fix src/broken.py
```

### 生成测试 (`dev-agent test`)

为源代码生成完整的 pytest 单元测试，覆盖正常路径、异常路径、边界条件。

```bash
dev-agent test src/calculator.py
```

### 自动生成 Commit Message (`dev-agent commit`)

分析 git diff 生成符合 Conventional Commits 规范的提交信息。

```bash
dev-agent commit
```

### Git Pre-commit Hook (`dev-agent hook install`)

安装后每次 `git commit` 自动审查代码变更，发现致命问题阻止提交。

```bash
dev-agent hook install        # 安装
git commit --no-verify        # 跳过审查
rm .git/hooks/pre-commit      # 卸载
```

### 交互式对话 (`dev-agent chat`)

不传参数进入 REPL 模式，传入参数直接执行后退出：

```bash
dev-agent chat                        # 交互模式
dev-agent chat "重构这个模块"          # 单次执行模式
dev-agent chat --json "分析项目结构"   # JSON 输出
```

---

## 完整命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `dev-agent init` | 首次配置向导 | `dev-agent init` |
| `dev-agent chat [PROMPT]` | 交互式对话 | `dev-agent chat "重构 utils.py"` |
| `dev-agent review [FILE]` | 代码审查 | `dev-agent review src/main.py` |
| `dev-agent explain [FILE]` | 解释代码逻辑 | `dev-agent explain src/algorithm.py` |
| `dev-agent fix [FILE]` | 修复代码问题 | `dev-agent fix src/broken.py` |
| `dev-agent test [FILE]` | 生成单元测试 | `dev-agent test src/calc.py` |
| `dev-agent commit` | 自动生成 commit message | `dev-agent commit` |
| `dev-agent hook install` | 安装 git pre-commit hook | `dev-agent hook install` |
| `dev-agent update` | 自动升级到最新版本 | `dev-agent update` |
| `dev-agent version` | 显示版本 + 远程对比 | `dev-agent version` |
| `dev-agent index` | 索引项目代码库 | `dev-agent index --force` |
| `dev-agent collaborate` | 多 Agent 协同模式 | `dev-agent collaborate` |
| `dev-agent serve` | 启动 API 服务 | `dev-agent serve --port 9000` |
| `dev-agent stats` | 查看可观测性统计 | `dev-agent stats` |
| `dev-agent version` | 显示版本信息 | `dev-agent version` |

---

## 管道输入与 JSON 输出

所有场景命令（review/explain/fix/test）均支持：

```bash
# 管道输入
git diff | dev-agent review
cat file.py | dev-agent explain

# JSON 输出（结构化，方便脚本解析）
dev-agent review --json src/main.py
dev-agent commit --json
```

Exit code 规范：
- `0` — 成功
- `1` — 配置错误
- `2` — Agent 执行失败
- `3` — API 调用失败
- `4` — 文件未找到
- `5` — Git 操作失败

---

## 配置参考

通过 `dev-agent init` 生成 `.env` 文件，或手动创建（参考 `.env.example`）：

```env
# 对话模型（必填）
LLM_CHAT_API_KEY=your-api-key
LLM_CHAT_BASE_URL=https://api.deepseek.com
LLM_CHAT_MODEL=deepseek-chat

# Embedding 模型（语义搜索，可选）
LLM_EMBEDDING_API_KEY=your-zhipu-api-key
LLM_EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_EMBEDDING_MODEL=embedding-3
```

---

## 架构设计 (2026 六层体系)

```
6. 运维与治理层: 可观测性 + 弹性重试 + 断路器
5. 多 Agent 协同层: Supervisor-Worker 编排
4. 工具与集成层: 13 内置工具 + MCP 协议桥接
3. 记忆与上下文层: SQLite + 向量 Embedding + 知识图谱
2. 开发框架层: Agentic Loop + 反思引擎
1. 基础模型层: DeepSeek / Qwen / OpenAI (可切换)
```

### Agentic Loop 工作原理

```
用户输入 → Agentic Loop
  ├─ LLM Client (自主决策)
  ├─ Tool Engine (13+MCP 工具)
  ├─ Reflection Engine (执行后反思修正)
  ├─ Resilience (断路器 + 重试)
  └─ Observability (全链路追踪)
→ 输出 (CLI / Web / API SSE)
```

### 多 Agent 协同

```
Supervisor (判断复杂度)
  ├─ 简单任务 → 单 Agent 直接处理
  └─ 复杂任务 → Planner → Coder → Reviewer → Debugger
```

### 目录结构

```
src/dev_agent/
├── agent/                  # Agentic Loop + System Prompt
├── agents/                 # 多 Agent 协同 (orchestrator + reflection)
├── llm/                    # LLM 客户端 (OpenAI 兼容协议)
├── core/                   # 弹性 + 可观测 + MCP 协议
├── tools/                  # 13 内置工具 (文件/搜索/Shell/Git)
├── context/                # 上下文管理 + 代码索引
├── memory/                 # SQLite 存储 + 长期记忆
├── config.py               # pydantic-settings 配置
├── cli.py                  # Typer CLI 入口 (12 命令)
└── api.py                  # FastAPI + SSE 流式接口
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| LLM | OpenAI 兼容协议 (DeepSeek/Qwen/OpenAI) |
| Embedding | 智谱 Embedding-3 (1024 维) |
| 存储 | SQLite |
| CLI | Typer + Rich |
| API | FastAPI + Uvicorn + SSE |

---

## License

MIT
