"""
DevAgent — 多 Agent 协同代码助手 (2026 标准)

核心能力:
  - 单/多 Agent 智能体循环
  - 反思与自我修正机制
  - 弹性重试 + 断路器保护
  - 长期记忆（向量检索 + 知识图谱）
  - 可观测性监控（Trace + Token 统计）
  - MCP 标准化协议支持

架构层次 (2026 六层体系):
  1. 基础模型层: DeepSeek / Qwen / OpenAI (Provider 可切换)
  2. 开发框架层: 自研 Agentic Loop + 多 Agent 协同编排
  3. 记忆与上下文层: SQLite + 向量 Embedding + 知识图谱
  4. 工具与集成层: 13 内置工具 + MCP 协议桥接
  5. 多 Agent 协同层: 主管-员工 (Supervisor-Worker) 模式
  6. 运维与治理层: 可观测性 + 弹性重试 + 断路器
"""
from __future__ import annotations

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("dev-agent")
except PackageNotFoundError:
    # 未通过 pip 安装时（开发模式 pip install -e . 也可以读到）
    __version__ = "0.5.0"
