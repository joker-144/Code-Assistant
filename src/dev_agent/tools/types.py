"""工具类型定义 — ToolResult 等共享类型"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """工具操作统一返回格式"""
    success: bool
    data: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """供 AgentLoop 展示的摘要"""
        if self.success:
            text = self.data
            return text[:200] + "..." if len(text) > 200 else text
        return f"错误: {self.error}"
