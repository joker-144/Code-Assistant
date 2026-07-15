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

import os
from pathlib import Path


def _read_version() -> str:
    """读取统一版本号 — 优先级：VERSION 文件 > 环境变量 > 已安装包 > 默认值"""
    # 1. VERSION 文件（项目根目录与打包后的 _MEIPASS 都尝试）
    for candidate in (
        Path(__file__).parent.parent.parent / "VERSION",
        Path(__file__).parent.parent / "VERSION",
    ):
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    # 2. 环境变量（Electron 主进程可通过此注入）
    env_v = os.environ.get("DEVAGENT_VERSION")
    if env_v:
        return env_v.strip()

    # 3. 已安装包的 metadata
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("dev-agent")
    except (PackageNotFoundError, ImportError):
        # 4. 兜底
        return "0.5.10"


__version__ = _read_version()
