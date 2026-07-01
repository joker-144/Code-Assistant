"""
LLM 客户端 — 支持 function calling + streaming

核心能力:
  - chat_with_tools(): 支持 OpenAI tools/tool_choice 参数，返回含 tool_calls 的完整 message
  - chat_stream(): 流式输出，实时返回生成内容
  - chat(): 基础文本对话（兼容旧调用方式）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI, OpenAI

from dev_agent.config import LLMConfig, get_config


@dataclass
class ToolCall:
    """LLM 请求的工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """LLM 返回的完整消息（含工具调用）"""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClient:
    """LLM 客户端 — 支持 function calling + streaming

    通过 OpenAI 兼容协议接入 DeepSeek / Qwen / OpenAI 等服务商
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_config().llm
        self.model = self.config.model
        # 同步客户端（用于简单调用）
        self._sync = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )
        # 异步客户端（用于流式 + AgentLoop）
        self._async = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    # ── 基础文本对话 ──

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """基础对话，返回纯文本"""
        response = self._sync.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    # ── Function Calling ──

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: str = "auto",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatMessage:
        """支持 function calling 的对话

        Args:
            messages: 对话消息列表
            tools: OpenAI function calling schema 列表
            tool_choice: "auto" | "none" | {"type": "function", "function": {"name": "..."}}

        Returns:
            ChatMessage: 含 content 和 tool_calls 的完整消息
        """
        response = self._sync.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )

        msg = response.choices[0].message
        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments) if call.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"_raw": call.function.arguments}
                tool_calls.append(ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=args,
                ))

        return ChatMessage(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
        )

    # ── 流式输出 ──

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """流式输出 — 实时返回生成内容

        Yields:
            文本片段（delta content）
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        stream = await self._async.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def create_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """创建 LLM 客户端（工厂函数）"""
    return LLMClient(config)
