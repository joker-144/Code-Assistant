# DevAgent

多模型协作开发智能体 — **DeepSeek-V4-Pro**（大脑）+ **Qwen-Plus**（审查）

根据自然语言需求自动生成代码、修复 Bug、审查代码、生成文档。

---

## 核心特性

- **多模型协作**: DeepSeek 负责规划与生成，Qwen 负责审查，质量双检
- **四层架构**: 大脑（规划/仲裁）→ 手脚（编码/审查）→ 工具 → 记忆
- **双重接口**: CLI 交互 + FastAPI REST API
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

## CLI 使用

### 执行开发任务

```bash
dev-agent run "用 Python 写一个函数，返回列表的最大值和最小值之差"
```

### 代码审查

```bash
dev-agent review "要审查的代码"
```

### 启动 API 服务

```bash
dev-agent serve
```

---

## API 使用

启动服务后访问 `http://localhost:8000/docs`

### 执行任务

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"request": "创建 FastAPI 应用，包含 /health 端点"}'
```

### 代码审查

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{"code": "def foo(): pass", "task_description": "简单函数"}'
```

---

## 项目结构

```
src/dev_agent/
├── brain/           # 大脑层：规划器(Planner)、仲裁器(Arbitrator)
├── workers/         # 手脚层：代码生成器(CodeWorker)、审查器(ReviewWorker)
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
