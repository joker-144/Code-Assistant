"""
统一 LLM 客户端 — 封装 OpenAI 兼容协议
DeepSeek-V4-Pro 和 Qwen-Plus 都走同一套接口
"""
from __future__ import annotations

import json
from typing import Any, Optional

from openai import OpenAI


class LLMClient:
    """统一的 LLM 调用客户端"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, str]] = None,
    ) -> str:
        """发送对话请求，返回文本响应"""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """发送对话请求，返回解析后的 JSON"""
        try:
            resp = self.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(resp)
        except (json.JSONDecodeError, Exception):
            # 降级：不用 JSON mode 再试一次
            resp = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
            # 尝试提取 JSON 块
            resp = resp.strip()
            if resp.startswith("```"):
                lines = resp.split("\n")
                resp = "\n".join(lines[1:-1])
            return json.loads(resp)


# ── 工厂函数 ──

def create_deepseek_client(config=None) -> LLMClient:
    """创建 DeepSeek-V4-Pro 客户端"""
    if config is None:
        from dev_agent.config import get_config
        config = get_config()
    return LLMClient(
        api_key=config.deepseek.api_key,
        base_url=config.deepseek.base_url,
        model=config.deepseek.model,
        temperature=0.2,   # 规划/仲裁：精确推理
        max_tokens=8192,
    )


def create_deepseek_code_client(config=None) -> LLMClient:
    """创建 DeepSeek-V4-Pro 代码生成客户端（temperature 略高）"""
    if config is None:
        from dev_agent.config import get_config
        config = get_config()
    return LLMClient(
        api_key=config.deepseek.api_key,
        base_url=config.deepseek.base_url,
        model=config.deepseek.model,
        temperature=0.3,   # 代码生成：平衡创造性和准确性
        max_tokens=8192,
    )


def create_qwen_client(config=None) -> LLMClient:
    """创建 Qwen-Plus 审查客户端"""
    if config is None:
        from dev_agent.config import get_config
        config = get_config()
    return LLMClient(
        api_key=config.qwen.api_key,
        base_url=config.qwen.base_url,
        model=config.qwen.model,
        temperature=0.1,   # 审查：追求稳定性
        max_tokens=4096,
    )