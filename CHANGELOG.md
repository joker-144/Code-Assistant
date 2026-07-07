# Changelog

All notable changes to DevAgent will be documented in this file.

## [0.5.0] — 2026-07-07

### Added
- **多 Agent 协同编排**：Supervisor-Worker 五角色编排器，自动判断需求复杂度
- **反思引擎**：6 种触发条件的反思引擎，最多自动修正重试 2 次
- **弹性工程**：指数退避重试 + 断路器三状态机 + 错误四级别分类
- **可观测性监控**：TraceSpan 追踪 + Token 统计 + 工具调用记录 + 会话报告
- **MCP 协议支持**：MCPRegistry 注册中心 + LocalToolBridge 本地工具桥接
- **长期记忆系统**：语义召回 + 知识图谱 + 会话洞察提取
- **场景化 CLI 命令**：`review` / `explain` / `fix` / `test` / `commit` / `hook install` / `init`
- **配置向导**：`dev-agent init` 交互式首次配置
- **自动更新**：`dev-agent update` 检查 PyPI 新版本并升级
- **版本检查提示**：启动时异步检查新版本
- **管道输入 + JSON 输出**：所有场景命令支持管道和 `--json` 标志
- **Git 集成**：pre-commit hook + 自动 commit message

### Changed
- `agent/loop.py`：集成反思、可观测、弹性重试
- `cli.py`：从 5 个命令扩展至 13 个，新增 8 个场景命令
- `README.md`：重写为面向实际使用的文档

### Fixed
- `llm/client.py`：修复 `ChatMessage` 缺少 `usage` 字段导致崩溃
- `core/mcp.py`：修复 `ToolDef` dataclass 对象当 dict 调用的 `AttributeError`
- `core/mcp.py`：修复 `execute` 签名与 `ToolEngine` 不匹配
- `context/tokenizer.py`：修复缺少 `import json`
- 运行时正确性审查：修复全部 4 个致命 bug、7 个警告、1 个建议

## [0.4.0] — 2026-06

### Added
- Agentic Loop 架构：LLM 自主工具调用循环
- 13 内置工具：文件 / Shell / Git / 搜索
- 上下文管理 + token 计数 + LLM 摘要压缩
- 代码库语义索引（智谱 Embedding-3）
- FastAPI + SSE 流式 API
- CLI (Typer + Rich) 交互式 REPL
- DeepSeek / Qwen / OpenAI 多 Provider 支持
