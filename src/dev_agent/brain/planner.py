"""
大脑层 — 任务规划器
DeepSeek-V4-Pro 分析需求，输出结构化执行计划
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dev_agent.llm_client import LLMClient


@dataclass
class SubTask:
    """子任务"""
    id: str
    description: str
    worker: str               # "code_worker" | "review_worker" | "brain"
    input_context: str
    expected_output: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"   # pending | running | done | failed
    result: Optional[str] = None


@dataclass
class ExecutionPlan:
    """执行计划"""
    user_request: str
    overall_approach: str
    architecture_notes: str
    sub_tasks: list[SubTask]
    estimated_files: list[str] = field(default_factory=list)


class Planner:
    """任务规划器 — 用 DeepSeek-V4-Pro 将需求拆解为可执行计划"""

    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self.llm = llm_client
        self.prompt_template = prompt_template

    def plan(self, user_request: str, context: str = "") -> ExecutionPlan:
        """分析需求，输出执行计划"""
        # 构建 prompt
        prompt = self.prompt_template.format(
            user_request=user_request,
            context=context or "无历史经验",
        )

        messages = [
            {"role": "system", "content": "你是一个技术负责人，只输出 JSON 格式的执行计划。"},
            {"role": "user", "content": prompt},
        ]

        # 调用 DeepSeek-V4-Pro
        raw = self.llm.chat_json(messages, temperature=0.2)

        # 解析为 ExecutionPlan
        return self._parse_plan(raw, user_request)

    def _parse_plan(self, raw: dict, user_request: str) -> ExecutionPlan:
        """将 LLM 返回的 JSON 解析为 ExecutionPlan"""
        sub_tasks = []
        for task_data in raw.get("sub_tasks", []):
            sub_tasks.append(SubTask(
                id=task_data["id"],
                description=task_data["description"],
                worker=task_data.get("worker", "code_worker"),
                input_context=task_data.get("input_context", ""),
                expected_output=task_data.get("expected_output", ""),
                depends_on=task_data.get("depends_on", []),
            ))

        return ExecutionPlan(
            user_request=user_request,
            overall_approach=raw.get("overall_approach", ""),
            architecture_notes=raw.get("architecture_notes", ""),
            sub_tasks=sub_tasks,
            estimated_files=raw.get("estimated_files", []),
        )


def load_prompt(name: str) -> str:
    """加载 prompt 模板文件"""
    prompt_dir = Path(__file__).parent.parent.parent.parent / "prompts"
    prompt_path = prompt_dir / name
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    # 降级：返回空模板
    return "{}"