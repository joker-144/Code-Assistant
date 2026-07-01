"""
AgentLoop — 核心智能体循环

这是新架构最核心的组件，替代旧 Orchestrator 的固定流水线。

工作循环:
  1. 构建 LLM 输入（system prompt + 上下文 + 工具定义）
  2. 调用 LLM（支持 function calling）
  3. 若 LLM 请求工具调用 → 执行工具 → 结果加入上下文 → 继续循环
  4. 若 LLM 返回纯文本 → 任务完成，结束循环

LLM 自主决定：是否需要读文件？是否需要搜索代码？是否需要运行测试？
何时认为任务完成？这些决策不再是 Python 硬编码的 if/elif，而是 LLM 的推理结果。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from dev_agent.agent.system_prompt import get_system_prompt
from dev_agent.config import get_config
from dev_agent.context.manager import ContextManager
from dev_agent.llm.client import LLMClient
from dev_agent.tools.engine import ToolEngine


@dataclass
class LoopEvent:
    """AgentLoop 产生的事件（供 CLI/API 展示）"""
    type: str  # "tool_start" | "tool_result" | "text" | "error" | "done"
    content: str = ""
    tool_name: str = ""
    tool_args: dict = None

    def __post_init__(self):
        if self.tool_args is None:
            self.tool_args = {}


class AgentLoop:
    """核心 Agent 循环 — LLM 自主决策执行路径"""

    def __init__(
        self,
        workspace: Optional[Path] = None,
        llm: Optional[LLMClient] = None,
        tools: Optional[ToolEngine] = None,
        context: Optional[ContextManager] = None,
        system_prompt: Optional[str] = None,
    ):
        config = get_config()
        self.workspace = workspace or config.workspace
        self.llm = llm or LLMClient()
        self.tools = tools or ToolEngine(self.workspace)
        self.system_prompt = system_prompt or get_system_prompt()
        self.context = context or ContextManager(
            workspace=self.workspace,
            system_prompt=self.system_prompt,
        )
        self.max_tool_rounds = config.llm.max_tool_rounds

    async def run(self, user_input: str) -> AsyncIterator[LoopEvent]:
        """运行 Agent 循环，流式输出事件

        Args:
            user_input: 用户输入

        Yields:
            LoopEvent: 工具调用、工具结果、文本回复等事件
        """
        self.context.add_user_message(user_input)

        rounds = 0
        while rounds < self.max_tool_rounds:
            rounds += 1

            # 1. 构建 LLM 输入
            messages = self.context.build_messages()
            tool_schemas = self.tools.get_schemas()

            # 检查 token 预算，必要时压缩
            await self.context.maybe_compress(self.llm)

            # 2. 调用 LLM（支持 function calling）
            try:
                response = self.llm.chat_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                )
            except Exception as e:
                yield LoopEvent(type="error", content=f"LLM 调用失败: {e}")
                return

            # 3. 判断 LLM 是否要调用工具
            if response.has_tool_calls:
                # 记录助手消息（含 tool_calls）
                tool_calls_openai = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in response.tool_calls
                ]
                self.context.add_assistant_message(response.content, tool_calls_openai)

                # 4. 逐个执行工具
                for call in response.tool_calls:
                    yield LoopEvent(
                        type="tool_start",
                        tool_name=call.name,
                        tool_args=call.arguments,
                        content=self._format_tool_call(call.name, call.arguments),
                    )

                    result = await self.tools.execute(call)

                    # 将结果加入上下文
                    self.context.add_tool_result(call.id, call.name, result.summary)

                    yield LoopEvent(
                        type="tool_result",
                        tool_name=call.name,
                        content=result.summary,
                    )

                # 继续循环，让 LLM 看到工具结果后决定下一步
                continue
            else:
                # 5. LLM 返回最终文本回复，循环结束
                self.context.add_assistant_message(response.content)
                yield LoopEvent(type="text", content=response.content)
                yield LoopEvent(type="done")
                return

        # 超过最大轮数
        yield LoopEvent(
            type="error",
            content=f"已达到最大工具调用轮数 ({self.max_tool_rounds})，强制停止",
        )

    def _format_tool_call(self, name: str, args: dict) -> str:
        """格式化工具调用用于展示"""
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        return f"[工具 {name}]({args_str})"


def create_agent(workspace: Optional[Path] = None) -> AgentLoop:
    """创建 Agent 实例（工厂函数）"""
    return AgentLoop(workspace=workspace)
