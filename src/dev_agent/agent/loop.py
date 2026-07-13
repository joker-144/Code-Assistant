"""
AgentLoop — 核心智能体循环

2026 增强版 — 集成反思、可观测性、弹性重试、MCP 支持

工作循环:
  1. 构建 LLM 输入（system prompt + 上下文 + 工具定义）
  2. 调用 LLM（支持 function calling，异步不阻塞，带重试）
  3. 若 LLM 请求工具调用 → 执行工具 → 反思结果 → 必要时修正 → 加入上下文 → 继续循环
  4. 若 LLM 返回纯文本 → 任务完成，结束循环

LLM 自主决定：是否需要读文件？是否需要搜索代码？是否需要运行测试？
何时认为任务完成？这些决策不再是 Python 硬编码的 if/elif，而是 LLM 的推理结果。

v0.5.0 增强:
  - 反思机制：工具失败后自动分析原因并修正
  - 可观测性：完整的 Trace、Token 统计、工具调用记录
  - 弹性重试：LLM 调用失败自动指数退避重试
  - MCP 支持：通过 MCP 协议注册外部工具
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from dev_agent.agent.system_prompt import get_system_prompt
from dev_agent.agents.reflection import ReflectionEngine, ReflectionContext, create_reflection_engine
from dev_agent.config import get_config
from dev_agent.context.manager import ContextManager
from dev_agent.core.observability import get_observability
from dev_agent.core.resilience import (
    CircuitBreaker,
    RetryConfig,
    RetryExhaustedError,
    classify_error,
    ErrorSeverity,
    get_resilience_tracker,
)
from dev_agent.llm.client import LLMClient
from dev_agent.memory.store import get_store
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
    """核心 Agent 循环 — LLM 自主决策执行路径 (v0.5.0 增强)

    每个实例维护独立的对话上下文，支持多轮对话。
    对话历史持久化到 SQLite（通过 MemoryStore）。

    v0.5.0 新增:
      - 反思引擎：工具执行后自动反思，失败自动修正
      - 可观测性：Trace + Token 统计 + 工具调用记录
      - 弹性重试：LLM 调用失败自动指数退避重试
      - 断路器：防止级联失败
    """

    def __init__(
        self,
        workspace: Optional[Path] = None,
        llm: Optional[LLMClient] = None,
        tools: Optional[ToolEngine] = None,
        context: Optional[ContextManager] = None,
        system_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
        enable_reflection: bool = True,
        enable_observability: bool = True,
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
        self.max_tool_rounds = config.llm_chat_max_tool_rounds
        self.conversation_id = conversation_id

        # v0.5.0 新增：反思引擎
        self.enable_reflection = enable_reflection
        self.reflection_engine = create_reflection_engine(max_retries=2) if enable_reflection else None

        # v0.5.0 新增：可观测性
        self.enable_observability = enable_observability
        self.observability = get_observability() if enable_observability else None

        # v0.5.0 新增：弹性重试
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        self.resilience_tracker = get_resilience_tracker()

        # 初始化对话持久化
        self._init_conversation()

    def _init_conversation(self):
        """初始化对话记录到 SQLite"""
        try:
            store = get_store()
            if self.conversation_id is None:
                self.conversation_id = str(uuid.uuid4())
            store.create_conversation(self.conversation_id)
        except Exception:
            # 持久化失败不影响核心功能
            pass

    async def run(self, user_input: str) -> AsyncIterator[LoopEvent]:
        """运行 Agent 循环，流式输出事件 (v0.5.0 增强)

        增强: LLM 调用失败自动重试、工具执行后反思、可观测性统计

        Args:
            user_input: 用户输入

        Yields:
            LoopEvent: 工具调用、工具结果、文本回复等事件
        """
        session_id = self.conversation_id or str(uuid.uuid4())[:8]
        request_start = time.time()

        # 可观测性：初始化会话
        if self.observability:
            self.observability.init_session(session_id)

        self.context.add_user_message(user_input)
        self._persist_message("user", user_input)

        # 重置反思状态（新任务开始）
        if self.reflection_engine:
            self.reflection_engine.reset()

        rounds = 0
        total_tool_calls = 0

        while rounds < self.max_tool_rounds:
            rounds += 1

            # 1. 检查 token 预算，必要时压缩
            await self.context.maybe_compress(self.llm)

            # 2. 构建 LLM 输入
            messages = self.context.build_messages()
            tool_schemas = self.tools.get_schemas()

            # 3. 调用 LLM（带弹性重试）
            llm_start = time.time()
            try:
                response = await self._call_llm_with_retry(
                    messages=messages,
                    tools=tool_schemas,
                    session_id=session_id,
                )
            except RetryExhaustedError as e:
                yield LoopEvent(type="error", content=f"LLM 调用重试耗尽: {e}")
                if self.observability:
                    self.observability.record_request(session_id, time.time() - request_start, error=True)
                return
            except Exception as e:
                yield LoopEvent(type="error", content=f"LLM 调用失败: {e}")
                if self.observability:
                    self.observability.record_request(session_id, time.time() - request_start, error=True)
                return

            llm_duration = (time.time() - llm_start) * 1000
            # 可观测性：记录 LLM 调用
            if self.observability and response.usage:
                self.observability.record_llm_call(
                    session_id,
                    tokens_in=response.usage.get("prompt_tokens", 0),
                    tokens_out=response.usage.get("completion_tokens", 0),
                    duration_ms=llm_duration,
                )

            # 4. 判断 LLM 是否要调用工具
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
                self._persist_message("assistant", response.content, tool_calls_openai)

                # 5. 逐个执行工具（带反思修正）
                for call in response.tool_calls:
                    yield LoopEvent(
                        type="tool_start",
                        tool_name=call.name,
                        tool_args=call.arguments,
                        content=self._format_tool_call(call.name, call.arguments),
                    )

                    result = await self._execute_tool_with_reflection(
                        call=call,
                        session_id=session_id,
                    )

                    # 将结果加入上下文
                    self.context.add_tool_result(call.id, call.name, result.summary)
                    self._persist_message(
                        "tool", result.summary,
                        tool_call_id=call.id,
                        tool_name=call.name,
                    )

                    yield LoopEvent(
                        type="tool_result",
                        tool_name=call.name,
                        content=result.summary,
                    )
                    total_tool_calls += 1

                continue
            else:
                # 6. LLM 返回最终文本回复，循环结束
                self.context.add_assistant_message(response.content)
                self._persist_message("assistant", response.content)
                yield LoopEvent(type="text", content=response.content)
                yield LoopEvent(type="done")

                # 可观测性：记录请求
                if self.observability:
                    self.observability.record_request(
                        session_id,
                        time.time() - request_start,
                    )
                    self.observability.record_tool_metrics(session_id, total_tool_calls)
                return

        # 超过最大轮数
        yield LoopEvent(
            type="error",
            content=f"已达到最大工具调用轮数 ({self.max_tool_rounds})，强制停止",
        )
        if self.observability:
            self.observability.record_request(session_id, time.time() - request_start, error=True)

    async def _call_llm_with_retry(self, messages: list, tools: list, session_id: str):
        """带弹性重试的 LLM 调用

        使用 resilience.py 统一的 RetryConfig + CircuitBreaker 组合，
        指数退避公式和断路器逻辑与 retry_with_backoff 装饰器保持一致。
        """
        retry_cfg = RetryConfig(max_retries=3, base_delay=1.0, max_delay=30.0)
        last_error = None

        for attempt in range(retry_cfg.max_retries + 1):
            if self.circuit_breaker.is_open:
                raise RetryExhaustedError("断路器开启，拒绝 LLM 调用")

            try:
                response = await self.llm.achat_with_tools(
                    messages=messages,
                    tools=tools,
                )
                self.circuit_breaker.record_success()
                self.resilience_tracker.record("llm_call", success=True)
                return response

            except Exception as e:
                last_error = e
                severity = classify_error(e)
                self.circuit_breaker.record_failure()
                self.resilience_tracker.record("llm_call", success=False)

                if attempt >= retry_cfg.max_retries or severity in (ErrorSeverity.PERMANENT, ErrorSeverity.FATAL):
                    raise RetryExhaustedError(
                        f"LLM 调用重试 {retry_cfg.max_retries} 次后仍失败: {e}"
                    ) from e

                delay = min(
                    retry_cfg.base_delay * (retry_cfg.backoff_multiplier ** attempt),
                    retry_cfg.max_delay,
                )
                if retry_cfg.jitter:
                    import random
                    delay *= (0.5 + random.random())
                await asyncio.sleep(delay)

        raise RetryExhaustedError(f"LLM 调用异常: {last_error}") from last_error

    async def _execute_tool_with_reflection(self, call, session_id: str):
        """执行工具并触发反思修正（v0.5.0 新增）

        流程:
          1. 执行工具
          2. 记录结果到反思引擎
          3. 分析结果 → 决定是否需要修正
          4. 如需要且未超过重试上限 → 重新执行
        """
        tool_start = time.time()

        # 首次执行
        result = await self.tools.execute(call)
        tool_duration = (time.time() - tool_start) * 1000

        # 可观测性：记录工具调用
        if self.observability:
            self.observability.record_tool_call(
                tool_name=call.name,
                args=call.arguments,
                duration_ms=tool_duration,
                success=result.success,
                result_summary=result.summary if result.success else "",
                error=result.error if not result.success else "",
            )

        # 无反思引擎或结果成功 → 直接返回
        if not self.reflection_engine:
            return result

        # 记录上下文
        self.reflection_engine.record(ReflectionContext(
            step=len(self.reflection_engine._contexts) + 1,
            tool_name=call.name,
            tool_args=call.arguments,
            result=result.summary,
            success=result.success,
            error=result.error,
            timestamp=time.time(),
        ))

        # 反思分析
        reflection = self.reflection_engine.reflect(
            tool_name=call.name,
            result=result.summary,
            success=result.success,
            error=result.error,
        )

        if not reflection.needs_correction:
            return result

        # 需要修正 → 最多重试 2 次
        for retry_idx in range(2):
            await asyncio.sleep(0.5 * (retry_idx + 1))  # 短暂等待

            retry_start = time.time()
            retry_result = await self.tools.execute(call)
            retry_duration = (time.time() - retry_start) * 1000

            if self.observability:
                self.observability.record_tool_call(
                    tool_name=f"{call.name}(retry{retry_idx + 1})",
                    args=call.arguments,
                    duration_ms=retry_duration,
                    success=retry_result.success,
                )

            if retry_result.success:
                return retry_result

        return result  # 返回最后一次结果

    def _persist_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict] = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ):
        """持久化消息到 SQLite（失败不影响主流程）"""
        try:
            store = get_store()
            tool_args = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else ""
            store.add_message(
                conversation_id=self.conversation_id,
                role=role,
                content=content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_args=tool_args,
            )
        except Exception:
            pass

    def _format_tool_call(self, name: str, args: dict) -> str:
        """格式化工具调用用于展示"""
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        return f"[工具 {name}]({args_str})"


def create_agent(
    workspace: Optional[Path] = None,
    conversation_id: Optional[str] = None,
    llm_overrides: Optional[dict] = None,
) -> AgentLoop:
    """创建 Agent 实例（工厂函数）

    Args:
        workspace: 工作目录
        conversation_id: 对话 ID（传入已有 ID 可恢复上下文，但上下文本身在内存中）
        llm_overrides: LLM 配置覆盖（api_key, base_url, model, temperature, max_tokens）
    """
    llm = None
    if llm_overrides:
        llm = LLMClient(
            api_key=llm_overrides.get("api_key", ""),
            base_url=llm_overrides.get("base_url", ""),
            model=llm_overrides.get("model", ""),
            temperature=llm_overrides.get("temperature"),
            max_tokens=llm_overrides.get("max_tokens"),
        )
    return AgentLoop(workspace=workspace, conversation_id=conversation_id, llm=llm)
