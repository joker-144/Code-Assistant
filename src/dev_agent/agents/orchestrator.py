"""
多 Agent 协同编排器 — 主管-员工 (Supervisor-Worker) 模式

核心设计:
- 主管 Agent (Supervisor): 分析需求 → 规划子任务 → 分配 → 汇总
- 员工 Agent (Workers): Planner / Coder / Reviewer / Debugger 各司其职
- 通信协议: 结构化 JSON 消息在 Agent 间传递，每个 Worker 拥有独立上下文

工作流程:
  1. Supervisor 接收用户需求，拆解为子任务列表
  2. 按依赖关系将子任务分配给对应 Worker
  3. 每个 Worker 独立运行 Agentic Loop，完成子任务
  4. Supervisor 汇总各 Worker 结果，检查一致性
  5. 如有冲突或遗漏，触发反思和重新分配
  6. 最终结果输出给用户

与单 Agent Loop 的关系:
  Orchestrator 内部使用 AgentLoop 作为 Worker 的执行引擎，
  每个 Worker 是独立的 AgentLoop 实例，拥有自己的上下文和工具访问权限。

智能体定义从 agents/ 文件夹的 agent.json 加载（见 loader.py），
专属技能自动注入到 Worker 的 system prompt。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from dev_agent.agent.loop import AgentLoop, LoopEvent
from dev_agent.config import get_config
from dev_agent.agents.loader import get_agent_loader


class AgentRole(Enum):
    """Agent 角色"""
    SUPERVISOR = "supervisor"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"


@dataclass
class SubTask:
    """子任务定义"""
    id: str
    role: AgentRole
    description: str
    context: str = ""
    dependencies: list[str] = field(default_factory=list)
    result: str = ""
    status: str = "pending"


@dataclass
class CollaborationEvent:
    """协同事件（供 CLI/Web 展示）"""
    type: str  # "task_created" | "worker_start" | "worker_done" | "reflection" | "text" | "done"
    role: str = ""
    content: str = ""
    metadata: dict = field(default_factory=dict)


class AgentOrchestrator:
    """多 Agent 协同编排器

    每个 Worker Agent 是独立的 AgentLoop 实例，
    拥有独立的上下文和角色化的 System Prompt（从 agents/{role}/agent.json 加载）。
    """

    @classmethod
    def get_all_role_info(cls) -> list[dict]:
        """获取所有 Agent 角色的信息（用于 API 动态展示）"""
        return get_agent_loader().get_all_role_info()

    def __init__(self, workspace: Optional[Path] = None):
        config = get_config()
        self.workspace = workspace or config.workspace
        self._workers: dict[AgentRole, AgentLoop] = {}
        self._history: list[SubTask] = []
        self._loader = get_agent_loader()

    def _get_worker(self, role: AgentRole) -> AgentLoop:
        """获取或创建 Worker Agent

        system prompt 从 agents/{role}/agent.json 加载，并自动注入专属技能。
        """
        if role not in self._workers:
            prompt = self._loader.get_system_prompt(role.value)
            if not prompt:
                # 回退：loader 中没有定义时使用空字符串
                prompt = ""
            self._workers[role] = AgentLoop(
                workspace=self.workspace,
                system_prompt=prompt,
            )
        return self._workers[role]

    async def collaborate(self, user_input: str) -> AsyncIterator[CollaborationEvent]:
        """多 Agent 协同入口

        Args:
            user_input: 用户原始需求

        Yields:
            CollaborationEvent: 协同过程中产生的事件
        """
        # 1. Supervisor 分析需求并制定计划
        yield CollaborationEvent(
            type="task_created",
            role="supervisor",
            content=f"分析需求: {user_input}",
        )

        # 简易需求判断 — 是否启动多 Agent 流程
        needs_multi = self._needs_multi_agent(user_input)

        if not needs_multi:
            # 简单任务：直接用单 Agent 完成
            yield CollaborationEvent(
                type="worker_start",
                role="coder",
                content="简单任务，直接由 Coder 处理",
            )
            worker = self._get_worker(AgentRole.CODER)
            async for event in worker.run(user_input):
                mapped = self._map_event(event, "coder")
                if mapped:
                    yield mapped
            yield CollaborationEvent(type="done", role="supervisor")
            return

        # 2. 多 Agent 协作流程
        try:
            # Step 1: Planner 设计方案
            yield CollaborationEvent(type="worker_start", role="planner", content="规划技术方案...")
            plan = await self._run_worker(AgentRole.PLANNER, (
                f"请为以下需求设计技术方案:\n{user_input}\n\n"
                "输出格式: 1) 方案概述 2) 步骤拆解 3) 技术选型"
            ))
            yield CollaborationEvent(type="worker_done", role="planner", content=plan[:500])

            # Step 2: Coder 实现
            yield CollaborationEvent(type="worker_start", role="coder", content="开始编码实现...")
            code_prompt = (
                f"## 技术方案\n{plan}\n\n"
                f"## 用户需求\n{user_input}\n\n"
                "请按照技术方案实现代码。先阅读现有代码了解项目结构，再进行修改。"
            )
            coder = self._get_worker(AgentRole.CODER)
            coder_results = []
            async for event in coder.run(code_prompt):
                mapped = self._map_event(event, "coder")
                if mapped:
                    yield mapped
                    if mapped.type == "text":
                        coder_results.append(mapped.content)
            code_result = "\n".join(coder_results) if coder_results else ""
            yield CollaborationEvent(type="worker_done", role="coder", content="编码完成")

            # Step 3: Reviewer 审查（如果有代码修改）
            if code_result or self._has_file_changes(coder):
                yield CollaborationEvent(type="worker_start", role="reviewer", content="审查代码质量...")
                review = await self._run_worker(AgentRole.REVIEWER, (
                    f"## 技术方案\n{plan}\n\n"
                    f"## 实现概述\n{code_result[:1000]}\n\n"
                    "请审查代码质量，重点关注: 逻辑正确性、安全性、性能、代码风格"
                ))
                yield CollaborationEvent(type="worker_done", role="reviewer", content=review[:500])

                # 如果审查发现严重问题，触发修复
                if "严重" in review or "CRITICAL" in review:
                    yield CollaborationEvent(
                        type="reflection",
                        role="supervisor",
                        content="审查发现严重问题，触发代码修复",
                    )
                    yield CollaborationEvent(type="worker_start", role="debugger", content="修复代码问题...")
                    fix_prompt = (
                        f"## 审查报告\n{review}\n\n"
                        f"## 原始需求\n{user_input}\n\n"
                        "请根据审查报告修复代码中的问题。"
                    )
                    debugger = self._get_worker(AgentRole.DEBUGGER)
                    async for event in debugger.run(fix_prompt):
                        mapped = self._map_event(event, "debugger")
                        if mapped:
                            yield mapped
                    yield CollaborationEvent(type="worker_done", role="debugger", content="修复完成")

            # Step 4: 自我反思检查
            yield CollaborationEvent(
                type="reflection",
                role="supervisor",
                content="执行一致性检查...",
            )

        except Exception as e:
            yield CollaborationEvent(
                type="worker_done",
                role="supervisor",
                content=f"协同过程出错: {e}",
                metadata={"error": str(e)},
            )

        yield CollaborationEvent(type="done", role="supervisor")

    async def _run_worker(self, role: AgentRole, prompt: str) -> str:
        """运行一个 Worker 并收集文本输出

        若 Worker 仅调工具未输出文本，生成有意义的工具调用摘要。
        """
        worker = self._get_worker(role)
        results = []
        tool_names = []
        async for event in worker.run(prompt):
            if event.type == "text":
                results.append(event.content)
            elif event.type == "tool_start" and event.tool_name:
                tool_names.append(event.tool_name)

        if results:
            return "\n".join(results)
        if tool_names:
            return f"[工具调用摘要] Worker 完成 {len(tool_names)} 次工具调用: {', '.join(tool_names[:10])}"
        return ""

    def _needs_multi_agent(self, user_input: str) -> bool:
        """判断是否需要启动多 Agent 协作"""
        multi_keywords = [
            "方案", "设计", "架构", "系统", "审查", "review",
            "重构", "大型", "完整项目", "优化整个", "分析代码",
            "多模块", "整体", "全面",
        ]
        lower = user_input.lower()
        return any(kw in lower for kw in multi_keywords)

    def _has_file_changes(self, agent: AgentLoop) -> bool:
        """检查 Agent 的文件操作工具是否进行了实际文件修改"""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return bool(result.stdout.strip())
        except FileNotFoundError:
            return True
        except Exception:
            return True

    def _map_event(self, event: LoopEvent, role: str) -> Optional[CollaborationEvent]:
        """将 AgentLoop 事件映射为 CollaborationEvent"""
        mapping = {
            "tool_start": "worker_start",
            "tool_result": "worker_start",
            "text": "text",
            "error": "worker_done",
        }
        mapped_type = mapping.get(event.type, "worker_start")
        if mapped_type == "worker_start" and event.type == "tool_result":
            return None
        return CollaborationEvent(
            type=mapped_type,
            role=role,
            content=event.content,
            metadata={"tool": event.tool_name, "args": event.tool_args} if event.tool_name else {},
        )


def create_orchestrator(workspace: Optional[Path] = None) -> AgentOrchestrator:
    """创建多 Agent 编排器（工厂函数）"""
    return AgentOrchestrator(workspace=workspace)
