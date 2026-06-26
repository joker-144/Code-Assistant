"""
短期记忆 — 对话上下文窗口管理
当 token 超过阈值时自动压缩早期消息为摘要
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    """单条消息"""
    role: str      # "system" | "user" | "assistant"
    content: str


class ShortTermMemory:
    """管理对话上下文窗口"""

    def __init__(
        self,
        max_tokens: int = 60000,
        summary_trigger: int = 45000,
    ):
        self.max_tokens = max_tokens
        self.summary_trigger = summary_trigger
        self.messages: list[Message] = []
        self.summary: str = ""

    def add_message(self, role: str, content: str) -> None:
        """添加一条消息"""
        self.messages.append(Message(role=role, content=content))

        # 检查是否需要压缩
        if self._estimate_tokens() > self.summary_trigger:
            self._compress()

    def get_context(self, recent_count: int = 20) -> list[dict[str, str]]:
        """获取当前上下文（摘要 + 最近 N 条消息）"""
        result = []

        if self.summary:
            result.append({
                "role": "system",
                "content": f"[对话历史摘要]\n{self.summary}",
            })

        recent = self.messages[-recent_count:] if recent_count > 0 else self.messages
        for msg in recent:
            result.append({"role": msg.role, "content": msg.content})

        return result

    def get_full_history(self) -> list[dict[str, str]]:
        """获取完整对话历史"""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def clear(self) -> None:
        """清空记忆"""
        self.messages.clear()
        self.summary = ""

    def stats(self) -> dict:
        """获取记忆状态"""
        return {
            "message_count": len(self.messages),
            "estimated_tokens": self._estimate_tokens(),
            "has_summary": bool(self.summary),
            "summary_length": len(self.summary) if self.summary else 0,
        }

    # ── 内部方法 ──

    def _estimate_tokens(self) -> int:
        """估算当前消息的总 token 数（粗略：1 字符 ≈ 0.5 token 用于中文）"""
        total = 0
        for msg in self.messages:
            # 中文每个字符约 1-2 tokens，英文约 0.25 tokens
            # 取粗略平均: 1 字符 ≈ 0.6 token
            total += len(msg.content) * 0.6
        return int(total)

    def _compress(self) -> None:
        """将早期消息压缩为摘要"""
        # 保留最近 10 条，其余压缩
        if len(self.messages) <= 10:
            return

        old = self.messages[:-10]
        recent = self.messages[-10:]

        # 生成摘要
        summary_parts = []
        for msg in old:
            summary_parts.append(f"[{msg.role}]: {msg.content[:200]}")

        self.summary = " | ".join(summary_parts[-20:])  # 只保留最后 20 条的摘要
        self.messages = recent