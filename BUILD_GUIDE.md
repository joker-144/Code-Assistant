# 🏗️ DevAgent 从零搭建全过程

> 手把手教你搭建一个多模型协作开发智能体  
> 涵盖：环境准备 → 项目初始化 → 核心模块开发 → 测试运行 → 生产部署

---

## 目录

1. [前置准备](#一前置准备)
2. [项目初始化](#二项目初始化)
3. [配置系统](#三配置系统)
4. [统一 LLM 客户端](#四统一-llm-客户端)
5. [大脑层 — 规划器](#五大脑层--规划器)
6. [大脑层 — 仲裁器](#六大脑层--仲裁器)
7. [手脚层 — GLM Worker](#七手脚层--glm-worker)
8. [手脚层 — Qwen Worker](#八手脚层--qwen-worker)
9. [工具层](#九工具层)
10. [记忆系统](#十记忆系统)
11. [核心编排器](#十一核心编排器)
12. [CLI 与 API](#十二cli-与-api)
13. [Prompt 模板](#十三prompt-模板)
14. [运行测试](#十四运行测试)
15. [Docker 部署](#十五docker-部署可选)
16. [代码助手模式](#十六代码助手模式code-assistant)
17. [生产化建议](#十七生产化建议)
18. [完整项目结构](#十八完整项目结构)

---

## 一、前置准备

### 1.1 环境要求

| 组件 | 最低版本 | 验证命令 |
|------|---------|---------|
| Python | 3.11+ | `python --version` |
| pip | 23.0+ | `pip --version` |
| Git | 2.30+ | `git --version` |

### 1.2 获取 API Key

在开始之前，你需要注册并获取三个模型的 API Key：

```
1. DeepSeek（大脑）
   → https://platform.deepseek.com
   → 注册 → API Keys → 创建 Key
   → 记下: DEEPSEEK_API_KEY

2. 智谱 GLM-4（代码手）
   → https://open.bigmodel.cn
   → 注册 → API Keys → 创建 Key
   → 记下: ZHIPU_API_KEY

3. 阿里百炼 Qwen（审查手）
   → https://dashscope.aliyun.com
   → 注册 → API-KEY 管理 → 创建 Key
   → 记下: QWEN_API_KEY
```

### 1.3 创建项目目录

```bash
# 在你想放项目的地方执行:
mkdir dev-agent-multi-model
cd dev-agent-multi-model

# 创建源码目录结构
mkdir -p src/dev_agent/brain
mkdir -p src/dev_agent/workers
mkdir -p src/dev_agent/tools
mkdir -p src/dev_agent/memory
mkdir -p config
mkdir -p prompts
mkdir -p scripts
mkdir -p docker
mkdir -p docs
```

---

## 二、项目初始化

### 2.1 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活
# Windows:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate
```

### 2.2 创建 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dev-agent"
version = "0.1.0"
description = "多模型协作开发智能体"
requires-python = ">=3.11"

dependencies = [
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "langchain-community>=0.3.0",
    "chromadb>=0.5.0",
    "tiktoken>=0.7.0",
    "openai>=1.50.0",
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.5.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",
    "typer>=0.12.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "gitpython>=3.1.0",
]

[project.scripts]
dev-agent = "dev_agent.cli:app"

[tool.setuptools.packages.find]
where = ["src"]
```

### 2.3 创建 .env 配置文件

```bash
# .env — 填入你在 1.2 中获取的 API Key
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

ZHIPU_API_KEY=your-zhipu-key-here
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPU_MODEL=glm-4-plus

QWEN_API_KEY=sk-your-qwen-key-here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max

CHROMA_PERSIST_DIR=D:/Study/Code-Assistant/data/chroma
DEV_AGENT_WORKSPACE=D:/Study/Code-Assistant/workspace
DEV_AGENT_MAX_RETRIES=3
```

### 2.4 安装依赖

```bash
pip install --upgrade pip
pip install -e .
```

---

## 三、配置系统

### 3.1 创建 `src/dev_agent/__init__.py`

```python
# DevAgent — 多模型协作开发智能体
```

### 3.2 创建 `src/dev_agent/config.py`

这是配置系统，负责从 `.env` 和环境变量加载所有配置：

```python
"""
DevAgent 配置系统
基于 pydantic-settings，从 .env 和环境变量加载所有配置
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """单个模型的 API 配置"""
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class DeepSeekConfig(ModelConfig):
    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_")


class GLMConfig(ModelConfig):
    model_config = SettingsConfigDict(env_prefix="ZHIPU_")


class QwenConfig(ModelConfig):
    model_config = SettingsConfigDict(env_prefix="QWEN_")


class MemoryConfig(BaseSettings):
    chroma_persist_dir: str = "D:/Study/Code-Assistant/data/chroma"
    chroma_collection: str = "dev_agent_memory"
    model_config = SettingsConfigDict(env_prefix="CHROMA_")


class AgentConfig(BaseSettings):
    deepseek: DeepSeekConfig = DeepSeekConfig()
    zhipu: GLMConfig = GLMConfig()
    qwen: QwenConfig = QwenConfig()
    memory: MemoryConfig = MemoryConfig()
    workspace: Path = Path("D:/Study/Code-Assistant/workspace")
    max_retries: int = 3
    verbose: bool = True
    max_context_tokens: int = 60000
    summary_trigger_tokens: int = 45000

    model_config = SettingsConfigDict(
        env_prefix="DEV_AGENT_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_api_keys(self) -> list[str]:
        """检查哪些 API Key 缺失"""
        missing = []
        if not self.deepseek.api_key or "your-" in self.deepseek.api_key:
            missing.append("DeepSeek (DEEPSEEK_API_KEY)")
        if not self.zhipu.api_key or "your-" in self.zhipu.api_key:
            missing.append("GLM-4 / 智谱 (ZHIPU_API_KEY)")
        if not self.qwen.api_key or "your-" in self.qwen.api_key:
            missing.append("Qwen / 百炼 (QWEN_API_KEY)")
        return missing


_config: Optional[AgentConfig] = None

def get_config() -> AgentConfig:
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config
```

## 四、统一 LLM 客户端

### 4.1 创建 `src/dev_agent/llm_client.py`

这是所有模型调用的统一入口。DeepSeek、GLM、Qwen 都支持 OpenAI 兼容协议，所以可以用同一个客户端：

```python
"""
统一 LLM 客户端 — 封装 OpenAI 兼容协议
"""

from __future__ import annotations
import json
from typing import Any, Optional
from openai import OpenAI
from dev_agent.config import AgentConfig


class LLMClient:
    """统一的 LLM 调用客户端"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, str]] = None,
    ) -> str:
        """发送对话请求，返回文本响应"""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """发送对话请求，返回解析后的 JSON"""
        try:
            resp = self.chat(
                messages, temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(resp)
        except (json.JSONDecodeError, Exception):
            resp = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
            return json.loads(resp)


# ── 工厂函数：从配置创建各模型客户端 ──

def create_deepseek_client(config=None) -> LLMClient:
    if config is None:
        from dev_agent.config import get_config
        config = get_config()
    return LLMClient(
        api_key=config.deepseek.api_key,
        base_url=config.deepseek.base_url,
        model=config.deepseek.model,
        temperature=0.2,   # 大脑：精确推理
        max_tokens=8192,
    )

def create_glm_client(config=None) -> LLMClient:
    if config is None:
        from dev_agent.config import get_config
        config = get_config()
    return LLMClient(
        api_key=config.zhipu.api_key,
        base_url=config.zhipu.base_url,
        model=config.zhipu.model,
        temperature=0.3,   # 代码生成：平衡创造性和准确性
        max_tokens=8192,
    )

def create_qwen_client(config=None) -> LLMClient:
    if config is None:
        from dev_agent.config import get_config
        config = get_config()
    return LLMClient(
        api_key=config.qwen.api_key,
        base_url=config.qwen.base_url,
        model=config.qwen.model,
        temperature=0.1,   # 审查：追求稳定性
        max_tokens=4096,
    )
```

**设计要点**：
- 三个模型走同一套 `LLMClient` 接口（OpenAI 兼容协议）
- `temperature` 按用途区分：大脑 0.2（精确） / 代码 0.3（平衡） / 审查 0.1（稳定）
- `chat_json()` 自动处理 JSON 解析失败的情况

---

## 五、大脑层 — 规划器

### 5.1 创建 `src/dev_agent/brain/__init__.py`

```python
# DevAgent 大脑层
```

### 5.2 创建 `src/dev_agent/brain/planner.py`

这是整个系统的第一关：大脑拿到用户需求后，分析并输出结构化的执行计划。

**核心数据结构**：

```python
@dataclass
class SubTask:
    id: str              # "task-1"
    description: str     # "定义 User 数据模型"
    worker: str          # brain / glm / qwen — 谁来做
    input_context: str   # 给 worker 的上下文
    expected_output: str # 期望产出格式
    depends_on: list[str]# 依赖的前置任务
    status: str          # pending / running / done / failed
    result: Optional[str]# 执行结果

@dataclass
class ExecutionPlan:
    user_request: str
    overall_approach: str    # 整体方案
    architecture_notes: str  # 架构决策
    sub_tasks: list[SubTask]
    estimated_files: list[str]
```

**核心方法 `planner.plan()`**：
1. 搜索长期记忆，获取相关历史经验
2. 用 DeepSeek-V4 调用规划 prompt
3. 解析返回的 JSON 为 `ExecutionPlan`
4. 返回给编排器使用

**Prompt 设计**：这是最关键的一步。规划器 prompt 要包含：
- 角色定义（你是技术负责人，不是程序员）
- 可用资源（有两个工程师：GLM 写代码、Qwen 审查）
- 用户需求
- 严格的 JSON 输出格式
- 规划原则（先分析后编码、小步验证、接口优先...）

---

## 六、大脑层 — 仲裁器

### 6.1 创建 `src/dev_agent/brain/arbitrator.py`

仲裁器负责审核 worker 的执行结果，做出三种决策：

```python
@dataclass
class ReviewResult:
    verdict: str  # "pass" | "retry" | "retry_with_feedback" | "abort"
    feedback: str # 如果打回，附上具体改进意见
    score: int    # 1-10 质量评分
    issues: list[str] # 发现的问题列表
```

**核心方法**：
- `review_code()` — 审查代码质量（5个维度：正确性/规范性/安全性/可维护性/错误处理）
- `review_architecture()` — 审查架构方案
- `decide_next_step()` — 遇到错误时决定下一步（continue / retry / skip / replan / abort）

**为什么需要仲裁器**：
- Worker 可能生成有问题的代码（幻觉、安全漏洞、逻辑错误）
- 需要在进入下一步之前做质量把关
- 具体反馈让 worker 能针对性地修复，而不是"从头开始"

---

## 七、手脚层 — GLM Worker

### 7.1 创建 `src/dev_agent/workers/__init__.py`

```python
# DevAgent 手脚层
```

### 7.2 创建 `src/dev_agent/workers/glm_worker.py`

GLM-4 负责所有代码相关的体力活：

**方法列表**：
| 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `generate_code()` | 根据规格写代码 | 任务描述 + 上下文 + 已有文件 | 可运行的代码 |
| `fix_code()` | 根据反馈修复代码 | 原代码 + 审查反馈 | 修复后的代码 |
| `generate_tests()` | 生成单元测试 | 源代码 | 测试代码 |

**关键设计**：
- `existing_files` 参数：可以传入已经生成的文件作为上下文，避免前后矛盾
- `_extract_code()` 方法：自动从 LLM 回复中提取代码块（处理有无 markdown 包裹的情况）
- temperature = 0.3：平衡创造性和准确性

---

## 八、手脚层 — Qwen Worker

### 8.1 创建 `src/dev_agent/workers/qwen_worker.py`

Qwen-Max 负责质量保障相关工作：

**方法列表**：
| 方法 | 功能 | 输出 |
|------|------|------|
| `review_code()` | 代码审查 | 结构化 JSON（5维度评分 + 问题清单） |
| `generate_docs()` | API 文档生成 | Markdown 文档 |
| `generate_pr_description()` | PR 描述 | Markdown |
| `analyze_bug_report()` | Bug 诊断 | JSON（根因 + 修复建议） |

**为什么选 Qwen 做审查**：
- Qwen 的指令遵循能力强，结构化输出（JSON）格式非常稳定
- temperature = 0.1：审查需要确定性，每次输出应该一致
- 成本低：审查一次 ¥0.02 vs DeepSeek ¥0.2

---

## 九、工具层

### 9.1 创建 `src/dev_agent/tools/__init__.py`

```python
# DevAgent 统一工具层
```

### 9.2 创建 `src/dev_agent/tools/tool_system.py`

**三个工具类**：

```
1. FileTool (文件操作)
   ├─ read(path)     → 读取文件
   ├─ write(path, content) → 写入文件
   ├─ list_dir(path) → 列出目录
   ├─ exists(path)   → 检查存在
   ├─ snapshot(path) → 项目文件树（给 LLM 理解结构）
   └─ delete(path)   → 删除文件
   
   安全：所有路径限制在 workspace 内

2. ShellTool (命令执行)
   ├─ run(command)   → 执行 Shell 命令
   └─ run_python(code) → 执行 Python 片段
   
   安全：危险命令黑名单 + 超时控制(60s) + 输出截断(10000字符)

3. GitTool (版本控制)
   ├─ status()       → 查看状态
   ├─ diff()         → 查看差异
   ├─ log(count)     → 查看历史
   └─ commit(msg)    → 提交变更
```

**统一接口**：
```python
@dataclass
class ToolResult:
    success: bool
    data: str
    error: str
    metadata: dict
```

**ToolRegistry**：
```python
class ToolRegistry:
    def __init__(self, workspace):
        self.file = FileTool(workspace)
        self.shell = ShellTool(workspace)
        self.git = GitTool(workspace)
```

---

## 十、记忆系统

### 10.1 创建 `src/dev_agent/memory/__init__.py`

```python
# DevAgent 记忆层
```

### 10.2 短期记忆 `src/dev_agent/memory/short_term.py`

```python
class ShortTermMemory:
    """
    管理对话上下文窗口
    
    策略：
    1. 保留最近的消息在窗口内
    2. 当 token 估算超过阈值（45K/60K）时：
       → 早期消息压缩为摘要
       → 摘要 + 最近消息 = 新上下文
    3. 上下文获取：get_context() 返回摘要+最近20条
    """
```

### 10.3 长期记忆 `src/dev_agent/memory/long_term.py`

```python
class LongTermMemory:
    """
    基于 ChromaDB 的向量记忆
    
    存储内容：
    - 项目架构信息（remember_project_context）
    - 历史经验教训（remember_lesson）
    - 常见问题的解决方案
    
    检索方式：
    - recall(query) → 语义搜索
    - recall_lessons(task_keywords) → 搜索相关经验
    
    如果 ChromaDB 不可用：
    → 自动降级为 JSON 文件存储（fallback）
    """
```

### 10.4 PostgreSQL 结构化记忆 `src/dev_agent/memory/structured.py` 🆕

> ChromaDB 管"语义相似"，PostgreSQL 管"关系查询"。两者互补。

#### 为什么需要 PostgreSQL

ChromaDB 适合"这句话和哪句话最像"，但搞不定：
- "过去一周失败最多的任务类型是什么？" → 需要 SQL 聚合
- "哪个模型做代码生成成功率最高？" → 需要结构化统计
- "这个错误 3 天前出现过，当时怎么解决的？" → 需要关联查询
- "glm worker 最近的重试率在上升吗？" → 需要时序分析

#### 5 张核心表

| 表 | 用途 | 典型查询 |
|---|------|---------|
| `tasks` | 每次完整任务执行 | 历史搜索、成本追踪、日报告 |
| `sub_tasks` | 子任务粒度记录 | 每个 worker 的单独表现、审查评分 |
| `model_metrics` | 按天聚合的模型性能 | `get_best_worker_for("code_gen")` |
| `conversations` | 多轮对话轨迹 | chat 模式的历史恢复 |
| `route_decisions` | 路由决策日志 | `analyze_route_accuracy()` 发现错误路由 |

#### 关键 API

```python
from dev_agent.memory.structured import PostgresMemory

pg = PostgresMemory("postgresql://user:pass@localhost:5432/dev_agent_memory")
pg.init_schema()

# 智能路由 — 根据历史成功率选择最佳模型
best = pg.get_best_worker_for("code_gen")  # → "glm"

# 搜索相似历史任务 — 复用经验
similar = pg.find_similar_tasks("创建 FastAPI 用户认证 API")

# 性能仪表盘
report = pg.get_daily_report()          # 今日任务总览
failed = pg.get_failed_tasks(hours=72)  # 最近 72h 失败

# 路由优化
worst = pg.get_worst_routes()           # 找出错误的路由规则
```

#### 三层记忆协作示例

```
用户请求 "修复数据库连接池泄漏"
         │
         ├─ 短期记忆（内存）：当前对话上下文，知道在讨论什么
         │
         ├─ 混合检索（PostgreSQL + ChromaDB 联手）：
         │     hybrid_search("数据库连接池泄漏",
         │       filter_type="code_fix", days=90, top_k=5)
         │     │
         │     ├─ Step 1: PostgreSQL 过滤
         │     │    SELECT * FROM tasks
         │     │    WHERE request_type='code_fix'
         │     │      AND created_at > now()-90d
         │     │    → 157 条候选
         │     │
         │     ├─ Step 2: ChromaDB 语义重排
         │     │    对 157 条候选做 embedding cos-sim 排序
         │     │    → 返回最相关的 5 条
         │     │
         │     └─ 结果: 3 个月前有一次 SQLAlchemy 连接池修复，
         │            方案可直接复用（语义相似度 0.94）
         │
         └─ 纯语义搜索（ChromaDB）：
               recall("连接池泄漏") → 最佳实践、常见根因
```

#### 配置与退化

```bash
# .env
POSTGRES_DSN=postgresql://dev_agent:password@localhost:5432/dev_agent_memory
```

```yaml
# docker-compose 一键启动 PostgreSQL
dev-agent-postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_USER: dev_agent
    POSTGRES_PASSWORD: password
    POSTGRES_DB: dev_agent_memory
  ports: ["5432:5432"]
```

**退化策略**：PostgreSQL 不可用时，结构化记忆自动降级为 SQLite，不阻塞功能。

---

## 十一、核心编排器

### 11.1 创建 `src/dev_agent/orchestrator.py`

这是整个系统的心脏。编排器串联大脑、手脚、工具、记忆四层。

**执行流程**（`execute()` 方法）：

```python
def execute(self, user_request: str) -> dict:
    # Step 1: 搜索长期记忆，获取相关经验
    lessons = self.long_memory.recall_lessons(user_request)
    context = self._build_context(lessons)

    # Step 2: 大脑规划
    plan = self.planner.plan(user_request, context)

    # Step 3: 执行计划（逐个或并行执行子任务）
    self._execute_plan(plan)

    # Step 4: 存储经验教训
    for task in plan.sub_tasks:
        self.long_memory.remember_lesson(...)

    # Step 5: 生成摘要 → 返回结果
    return {...}
```

**任务执行逻辑**（`_execute_task()` 方法）：

```
开始执行子任务
  ↓
分派到对应 worker (brain/glm/qwen)
  ↓
如果是代码生成 → 写完后 Qwen 初审 → 大脑终审
  ↓
pass: 完成 ✅
retry_with_feedback: 带着反馈重新生成 ♻️
retry: 完全重来 ♻️
   ↓
超过最大重试次数(3次)?
  → 接受当前结果 (避免死循环)
```

**任务分派**（`_dispatch()` 方法）：
- `worker == "glm"` → GLMWorker.generate_code()
- `worker == "qwen"` → QwenWorker.review_code() / generate_docs()
- `worker == "brain"` → 直接返回架构决策

---

## 十二、CLI 与 API

### 12.1 创建 CLI `src/dev_agent/cli.py`

使用 Typer + Rich 构建命令行界面：

```bash
# 四个核心命令
dev-agent run "需求描述"     # 执行一次开发任务
dev-agent chat               # 交互式对话
dev-agent review ./src/      # 审查目录代码
dev-agent serve              # 启动 API 服务

# 辅助命令
dev-agent version            # 版本信息
```

**交互模式**（`chat` 命令）：
```
🧠 DevAgent 交互模式
输入开发需求，我来规划并执行
输入 'exit' 退出 | 'status' 查看状态 | 'help' 帮助

💬 需求> 用 FastAPI 写一个带 JWT 认证的用户管理 API

🧠 大脑分析需求中...
📋 Plan: 整体方案是使用 FastAPI + SQLAlchemy + JWT...
🔧 Executing 5 tasks...
  ✅ task-1: 定义 User 数据模型
  ✅ task-2: 实现 CRUD API
  ✅ task-3: 实现 JWT 认证
  ✅ task-4: 代码审查
  ✅ task-5: 生成单元测试
✅ 执行完成
```

### 12.2 创建 API `src/dev_agent/api.py`

使用 FastAPI 构建 REST API：

```python
# 核心接口
POST /execute          → 执行开发任务
POST /review           → 审查代码
POST /generate-docs    → 生成文档
POST /generate-code    → 仅生成代码（不含审查）
GET  /memory/stats     → 记忆系统统计
GET  /health           → 健康检查
WS   /ws               → WebSocket 流式输出
```

---

## 十三、Prompt 模板

### 13.1 规划器 Prompt `prompts/planner.txt`

这是整个系统的"灵魂"——大脑怎么分析需求取决于这个 prompt：

```
核心结构:
  1. 角色定位: "你是资深技术负责人"
  2. 能力边界: "你只规划不写代码"
  3. 团队说明: "你有两个工程师: GLM(写代码) 和 Qwen(审查)"
  4. 用户需求: {user_request}
  5. 项目上下文: {context}
  6. 输出格式: 严格 JSON
  7. 规划原则: 先分析后编码、小步验证、接口优先、质量内置...
  8. 最后强调: "只输出 JSON"
```

### 13.2 代码生成 Prompt `prompts/code_gen.txt`

```
核心结构:
  1. 角色: "你是一位资深 X 语言工程师"
  2. 编码规范: 7条硬性要求 (类型提示/docstring/错误处理/PEP8...)
  3. 项目上下文 + 已有文件
  4. 具体任务 + 约束
  5. 输出: "只输出代码，不要解释"
```

---

## 十四、运行测试

### 14.1 配置 API Key

```bash
# 确保 .env 中的三个 API Key 都已填入真实值
cat .env | grep API_KEY
```

### 14.2 验证安装

```bash
# 应该输出版本信息
dev-agent version
# → DevAgent v0.1.0
```

### 14.3 首次测试 — 最简单的任务

```bash
dev-agent run "用 Python 写一个函数，接收一个数字列表，返回最大值和最小值的差值"

# 预期输出：
# 🧠 大脑分析需求中...
# 📋 Plan: 这是一个简单函数...
# 🔧 Executing...
# ✅ 执行完成
# ## 执行摘要
# **需求**: 用 Python 写一个函数...
# **结果**: 2/2 完成
```

### 14.4 中等复杂度测试

```bash
dev-agent run "创建一个 FastAPI 应用，有一个 /health 端点返回 {'status': 'ok'}，包含完整的错误处理和 logging"
```

### 14.5 代码审查测试

```bash
dev-agent review D:/Study/Code-Assistant/workspace/
```

### 14.6 交互模式测试

```bash
dev-agent chat
# 进入后在提示符下输入需求
```

---

## 十五、Docker 部署（可选）

### 15.1 Dockerfile

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" uvicorn

COPY src/ src/
COPY prompts/ prompts/
RUN mkdir -p workspace data/chroma

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "dev_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 15.2 docker-compose.yaml

```yaml
version: "3.9"
services:
  dev-agent:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - ZHIPU_API_KEY=${ZHIPU_API_KEY}
      - QWEN_API_KEY=${QWEN_API_KEY}
    volumes:
      - dev-agent-workspace:/app/workspace
      - dev-agent-data:/app/data
    restart: unless-stopped
```

### 15.3 启动

```bash
# 基础模式
docker-compose -f docker/docker-compose.yaml up -d

# 完整模式（含独立 ChromaDB）
docker-compose -f docker/docker-compose.yaml --profile full up -d
```

---

## 十六、代码助手模式（Code Assistant）

> 前面的章节描述的是"代码生成器"（给需求→吐代码）。
> 本章专门覆盖"代码助手"场景：理解已有代码、重构建议、Bug 诊断、技术问答。

### 16.1 "代码生成器" vs "代码助手"

| 维度 | 代码生成器 | 代码助手 ⭐ |
|------|-----------|------------|
| **输入** | 自然语言需求 | 已有代码 + 自然语言问题 |
| **核心动作** | 从零生成新代码 | 理解→分析→建议→修改 |
| **对代码库的感知** | 无（每次从头开始） | 深度理解已有项目结构 |
| **典型场景** | "写一个用户管理API" | "这段代码在做什么？" / "这个函数有什么问题？" / "如何重构这个模块？" |
| **输出** | 新的代码文件 | 解释、诊断报告、重构方案、或少量精准修改 |

**你需要的是代码助手，而不仅是代码生成器。** 本章补全代码助手所需的全部能力。

### 16.2 代码理解（Code Understanding）

**场景**：你接手一个陌生项目，想快速理解某个模块。

```bash
# 解释一个文件
dev-agent explain src/models/user.py

# 解释一个函数
dev-agent explain src/models/user.py::create_user

# 解释一个类的设计意图
dev-agent explain src/services/order_service.py --class OrderService
```

**Agent 内部做了什么**：
1. 读取目标代码 + 相关依赖文件
2. Qwen 做第一轮分析（快速梳理结构）
3. DeepSeek 做深度解读（设计意图、潜在风险、改进建议）
4. 返回：代码功能概述 + 关键逻辑流程图 + 依赖关系 + 注意事项

**核心 Prompt 设计**（新增 `prompts/code_explain.txt`）：
```
角色: 你是资深代码审查专家，擅长解释复杂代码逻辑
上下文: 项目框架={framework}，相关文件={related_files}
任务: 解释以下代码的用途、关键逻辑、设计模式
约束:
  - 先给一句话总结再展开
  - 标注关键行号和决策点
  - 如有潜在问题要明确指出
  - 对新人友好但不过度简化
```

### 16.3 重构建议（Refactoring）

**场景**：代码能跑但难维护，想要重构方案。

```bash
# 分析整个模块的重构机会
dev-agent refactor src/services/ --analyze-only

# 分析具体文件
dev-agent refactor src/utils/helpers.py

# 执行重构（生成新代码+对比报告）
dev-agent refactor src/services/user_service.py --execute
```

**Agent 分析维度**：
1. 代码坏味道检测：长函数、重复代码、过深嵌套、God Class
2. 设计模式匹配：Factory/Strategy/Observer 缺失的机会
3. 可测试性：依赖注入缺失、硬编码依赖
4. 性能瓶颈：N+1查询、不必要的循环、缓存缺失
5. 安全风险：SQL注入、XSS、敏感信息泄露

**输出格式**：
```markdown
## 重构分析: src/services/user_service.py

### 问题总览
- 🔴 严重: 2 / 🟡 警告: 5 / 🔵 建议: 3

### 🔴 严重问题
1. **[L42-L68] create_user() 函数过长 (27行)**
   - 建议: 拆分为 validate_user_input() + save_user() + send_welcome_email()
   - 预期提升: 可测试性 +40%

2. **[L89] SQL 注入风险**
   - 原始: f"SELECT * FROM users WHERE name='{name}'"
   - 建议: 使用参数化查询
```

### 16.4 Bug 诊断（Bug Diagnosis）

**场景**：代码有 Bug，需要定位根因。

```bash
# 描述 Bug 现象，Agent 分析代码找根因
dev-agent diagnose "用户登录后偶尔返回 500 错误，日志显示 KeyError: 'session_id'"

# 指定相关文件范围
dev-agent diagnose "订单金额计算错误" --files src/services/order.py,src/models/pricing.py

# 附带错误堆栈
dev-agent diagnose --traceback "traceback.txt"
```

**Agent 诊断流程**：
```
Step 1: Qwen 解析错误信息和堆栈 → 定位可疑代码位置
Step 2: DeepSeek 分析可疑代码的上下文和依赖 → 推导根因
Step 3: GLM-4 生成修复方案（不直接修改）
Step 4: Qwen 审查修复方案 → 确保不会引入新问题
Step 5: 输出诊断报告 + 修复建议
```

**诊断报告格式**：
```markdown
## 诊断结果: KeyError 'session_id'

### 根因
`auth/middleware.py:73` — `request.session` 在并发场景下可能为 None，
因为 `SessionMiddleware` 的 `__call__` 不是线程安全的。

### 触发条件
1. 用户短时间内多次请求（如页面有多个异步API调用）
2. Session 中间件在处理第一个请求时，第二个请求的 session 尚未初始化

### 复现步骤
```bash
# 并发 10 个请求可稳定复现
ab -n 10 -c 10 http://localhost:8000/api/me
```

### 修复方案
```python
# auth/middleware.py:73 — 修改前
user_id = request.session["user_id"]

# 修改后
user_id = getattr(request, "session", {}).get("user_id")
if user_id is None:
    raise HTTPException(status_code=401)
```
```

### 16.5 代码审查（Review Existing Code）

**场景**：审查团队成员或 AI 生成的代码。

```bash
# 审查一个文件
dev-agent review D:/Study/Code-Assistant/workspace/src/services/payment.py

# 审查 Git diff（最近的改动）
dev-agent review --diff HEAD~3..HEAD

# 审查整个 PR
dev-agent review --pr

# 只检查安全
dev-agent review src/ --focus security
```

**与"生成器审查"的区别**：
| 维度 | 生成器审查（第6章） | 代码助手审查 ⭐ |
|------|-----|------|
| 审查对象 | AI刚生成的代码 | 人类或AI写的任何代码 |
| 关注点 | 是否符合需求 | 代码质量 + 安全性 + 可维护性 + 性能 |
| 审查深度 | 单层（Qwen初审） | 三层（Qwen安全检查 → DeepSeek逻辑审查 → 综合报告） |
| 输出 | pass/retry | 分级的审查报告 + 改进建议 |

### 16.6 技术问答（Technical Q&A）

**场景**：有关项目代码的具体技术问题。

```bash
# 项目相关
dev-agent ask "这个项目的认证流程是怎样的？"
dev-agent ask "为什么 order_service 用 Redis 而不是数据库锁？"
dev-agent ask "如果要加多租户支持，需要改哪些文件？"

# 通用技术（结合项目上下文）
dev-agent ask "FastAPI 的 dependency injection 在这个项目中是怎么用的？"
```

**和普通 ChatGPT 问答的区别**：
- Agent 会**实际读取你的项目代码**来回答问题
- 答案基于真实代码，不是训练数据的泛泛之谈
- 可以引用具体文件和行号

### 16.7 已有代码库上下文注入

这是代码助手最关键的能力：让 Agent **真正理解**你的已有项目。

**3 种注入方式**：

```
方式1: 启动时自动扫描（默认）
  dev-agent 启动时会自动执行：
  ├─ 扫描 workspace 下所有 .py/.js/.ts/.java 文件
  ├─ 提取模块结构、类/函数签名、导入关系
  ├─ 构建项目索引存入长期记忆
  └─ 后续每次请求自动检索相关代码上下文

方式2: 按需增量扫描
  dev-agent scan --since "2024-06-01"  # 只扫描变更
  dev-agent scan --path src/services/   # 只扫描指定目录

方式3: Git 感知
  dev-agent 自动检测 Git 仓库：
  ├─ 理解分支结构
  ├─ 跟踪文件变更历史
  └─ diff 对比 → 知道"改了什么"
```

**上下文注入到 Prompt 的策略**：
```
Step 1: 解析用户问题，提取关键词
  例: "order_service 的支付逻辑" → [order_service, payment, logic]

Step 2: 在长期记忆中语义搜索最相关的代码
  找到: src/services/order_service.py (相似度 0.92)
        src/models/payment.py (相似度 0.85)
        src/services/order_service.py:L120-180 (支付函数)

Step 3: 按 token 预算注入
  - 高相关: 直接放完整代码到 prompt
  - 中相关: 放函数签名 + 关键逻辑摘要
  - 低相关: 只放文件路径（后续按需读取）

Step 4: 拼接最终 prompt
  [系统角色] + [项目上下文(注入的代码)] + [用户问题] + [指令]
```

### 16.8 CLI 命令完整清单

```bash
# ── 代码生成 ──
dev-agent run "需求描述"          # 从需求生成代码

# ── 代码理解 ──
dev-agent explain <file>          # 解释文件/函数/类
dev-agent ask "问题"              # 结合项目的技术问答

# ── 代码审查 ──
dev-agent review <path>           # 审查代码质量
dev-agent review --diff HEAD~3    # 审查Git变更

# ── 重构 ──
dev-agent refactor <path>         # 分析重构机会
dev-agent refactor <path> --execute # 执行重构

# ── Bug诊断 ──
dev-agent diagnose "现象描述"     # 定位Bug根因

# ── 项目感知 ──
dev-agent scan                    # 扫描并索引项目

# ── 交互模式 ──
dev-agent chat                    # 多轮对话

# ── 服务 ──
dev-agent serve                   # API服务
```

---

## 十七、生产化建议

### 16.1 当前 MVP vs 生产级

| 维度 | 当前 MVP | 生产级需要 |
|------|---------|-----------|
| **错误处理** | 基础 try/except | 完善的错误分类和自动恢复 |
| **日志** | logging 模块 | 结构化日志 + 链路追踪 |
| **监控** | 无 | Prometheus metrics + 告警 |
| **认证** | API Key | JWT + 多租户 |
| **限流** | 无 | Token bucket + 并发控制 |
| **持久化** | ChromaDB 本地 | 分布式向量数据库 + 备份 |
| **测试** | 无 | 单元测试 + 集成测试 + E2E |
| **文档** | Markdown | API 文档 + Swagger + 使用手册 |

### 16.2 成本优化

```
策略1: 模型分层
  - 简单任务（<100行代码）→ Qwen-Turbo（约 ¥0.001）
  - 中等任务（100-500行）  → GLM-4（约 ¥0.05）
  - 复杂任务（>500行）     → DeepSeek-V4（约 ¥0.50）

策略2: 结果缓存
  - 相同/相似需求 → 直接从长期记忆取方案
  - 节省 30-50% 的 API 调用

策略3: 提前终止
  - 大脑判定需求不可行 → 直接告知用户
  - 不做无效尝试

策略4: 批量审查
  - 多个文件一次提交审查
  - 减少 API 调用次数
```

### 16.3 扩展路径

```
可用 → 可靠 → 智能 → 自主

可用阶段（当前）:
  - 基本执行流程跑通
  - 能完成简单到中等的开发任务

可靠阶段:
  - 任务成功率 > 90%
  - 完善的错误恢复机制
  - CI/CD 集成

智能阶段:
  - 从历史经验自动优化策略
  - 自适应选择模型
  - 主动发现优化机会

自主阶段:
  - 对外提供 API 服务
  - 多用户/多项目管理
  - 自动学习新框架和工具
```

---

## 十八、完整项目结构

搭建完成后，你的项目目录应该长这样：

```
dev-agent-multi-model/
│
├── .venv/                          # Python 虚拟环境（自动生成）
├── .env                            # API Key 配置（需手动填入）
├── .env.example                    # 配置模板
├── .gitignore
├── pyproject.toml                  # 项目元数据和依赖
├── README.md                       # 项目说明
│
├── src/
│   └── dev_agent/
│       ├── __init__.py
│       ├── config.py               # 全局配置
│       ├── llm_client.py           # 统一 LLM 客户端
│       ├── orchestrator.py         # 核心编排器 ⭐
│       ├── graph.py                # LangGraph 工作流
│       ├── cli.py                  # CLI 入口
│       ├── api.py                  # FastAPI 接口
│       │
│       ├── brain/                  # 🧠 大脑层
│       │   ├── __init__.py
│       │   ├── planner.py         # 任务规划器
│       │   └── arbitrator.py      # 质量仲裁器
│       │
│       ├── workers/                # ✋ 手脚层
│       │   ├── __init__.py
│       │   ├── glm_worker.py      # GLM-4 代码生成
│       │   └── qwen_worker.py     # Qwen 审查/文档
│       │
│       ├── tools/                  # 🔧 工具层
│       │   ├── __init__.py
│       │   └── tool_system.py     # File/Shell/Git 工具
│       │
│       └── memory/                 # 💾 记忆层
│           ├── __init__.py
│           ├── short_term.py      # 短期记忆（上下文窗口管理）
│           ├── long_term.py       # 长期语义记忆（ChromaDB）
│           └── structured.py      # 🆕 结构化记忆（PostgreSQL）
│
├── config/
│   └── routes.py                   # 任务-模型路由规则
│
├── prompts/
│   ├── planner.txt                 # 规划器 prompt
│   └── code_gen.txt                # 代码生成 prompt
│
├── scripts/
│   ├── setup.ps1                   # Windows 安装脚本
│   └── setup.sh                    # Linux/macOS 安装脚本
│
├── docker/
│   ├── Dockerfile                  # Docker 镜像
│   └── docker-compose.yaml        # Docker 编排
│
├── docs/
│   ├── AI_AGENT_KNOWLEDGE_MANUAL.md  # 智能体知识手册
│   ├── AGENT_CONCEPTS.md             # 智能体概念
│   ├── ARCHITECTURE.md               # 系统架构
│   ├── PROMPT_DESIGN.md              # Prompt 设计
│   ├── SETUP_GUIDE.md                # 搭建指南
│   └── TOOL_SYSTEM.md                # 工具系统
│
├── D:\Study\Code-Assistant\
│   ├── workspace/                  # 代码生成工作目录（运行后自动创建）
│   └── data/
│       └── chroma/                 # 向量数据库存储（运行后自动创建）
```

---

## 附录：关键代码片段索引

项目中每个文件的核心代码都可以在项目目录中找到完整版本。以下是各文件的行数和核心职责速查：

| 文件 | 行数 | 核心职责 |
|------|------|---------|
| `config.py` | ~90 | 配置加载、API Key 校验 |
| `llm_client.py` | ~121 | OpenAI 兼容协议封装 |
| `brain/planner.py` | ~157 | DeepSeek 任务规划 |
| `brain/arbitrator.py` | ~131 | 质量仲裁决策 |
| `workers/glm_worker.py` | ~131 | GLM-4 代码生成 |
| `workers/qwen_worker.py` | ~130 | Qwen 审查/文档 |
| `tools/tool_system.py` | ~230 | 文件/Shell/Git 工具 |
| `memory/short_term.py` | ~92 | 上下文管理 |
| `memory/long_term.py` | ~230 | ChromaDB 记忆 |
| `orchestrator.py` | ~290 | 核心编排循环 |
| `graph.py` | ~210 | LangGraph 备选引擎 |
| `cli.py` | ~200 | CLI 界面 |
| `api.py` | ~150 | REST API |

---

> 📌 **提示**：本文档配套的完整可运行代码位于项目目录中，可以直接复制使用。建议从 `orchestrator.py` 开始阅读，理解整体流程后再深入各模块。
