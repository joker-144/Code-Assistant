# DevAgent

多智能体协作代码助手 — **规划Agent** 拆解任务、**编码Agent** 生成代码、**审查Agent** 把控质量

三个 Agent 各司其职、协同工作，让复杂开发任务变得简单。

---

## 核心特性

- **多智能体协作**: 规划Agent、编码Agent、审查Agent 分工明确，端到端协作
- **自然语言驱动**: 用日常语言描述需求，Agent 们自动完成开发
- **双重接口**: CLI 交互 + Web 交互页面
- **持久记忆**: 支持 SQLite / PostgreSQL + Milvus / ChromaDB 向量存储
- **工具系统**: 内置 Git、文件系统、Shell 等开发工具

---

## 安装

```bash
pip install -e .
```

## 配置

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus

# 可选：向量记忆（默认使用 Milvus）
MEMORY_MILVUS_HOST=localhost
MEMORY_MILVUS_PORT=19530
```

---

## 快速开始

### Web 交互页面（推荐）

```bash
dev-agent web
```

打开浏览器访问 `http://localhost:8000`

### CLI 使用

```bash
dev-agent run "用 Python 写一个函数，返回列表的最大值和最小值之差"
```

### 启动 API 服务

```bash
dev-agent serve
```

---

## 多智能体架构

```
用户需求
    │
    ▼
┌─────────────┐
│  规划Agent  │ ← 分析需求，制定执行计划
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  编码Agent  │ ← 根据计划生成代码
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  审查Agent  │ ← 检查代码质量，提出改进建议
└──────┬──────┘
       │
       ▼
   最终交付
```

---

## 项目结构

```
src/dev_agent/
├── brain/           # 规划Agent(Planner)、仲裁Agent(Arbitrator)
├── workers/         # 编码Agent(CodeWorker)、审查Agent(ReviewWorker)
├── tools/           # 工具层：Git、文件系统、Shell 等
├── memory/          # 记忆层：短时记忆、结构化记忆、长期记忆
├── api.py           # FastAPI 入口
├── cli.py           # CLI 入口
├── orchestrator.py  # 核心编排器
└── config.py        # 配置系统
```

---

## 依赖

- Python >= 3.11
- DeepSeek API / Qwen API
- FastAPI + Uvicorn
- Pydantic + Pydantic-Settings
- Rich + Typer
- Milvus / ChromaDB（可选）

详见 `pyproject.toml`
