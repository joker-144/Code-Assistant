"""
代码库语义搜索工具 — search_code

让 Agent 能在代码库中语义搜索相关代码——这是 Cursor "理解你的项目"的核心机制。
基于 ProjectIndex 的 Embedding 向量检索。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from dev_agent.context.index import ProjectIndex
from dev_agent.tools.types import ToolResult


class SearchTool:
    """代码库语义搜索工具"""

    def __init__(self, workspace: Path, index: Optional[ProjectIndex] = None):
        self.workspace = workspace
        self._index = index  # 延迟初始化，首次调用时才加载

    @property
    def index(self) -> ProjectIndex:
        """延迟加载 ProjectIndex（首次使用时初始化智谱 Embedder）"""
        if self._index is None:
            self._index = ProjectIndex(self.workspace)
        return self._index

    async def search_code(self, query: str, top_k: int = 5) -> ToolResult:
        """语义搜索代码库

        Args:
            query: 自然语言搜索查询
            top_k: 返回结果数量
        """
        try:
            # 用 to_thread 包装避免同步网络请求阻塞事件循环
            results = await asyncio.to_thread(self.index.search, query, top_k=top_k)

            if not results:
                return ToolResult(
                    success=True,
                    data="未找到相关代码。提示：可先运行 `dev-agent index` 索引项目。",
                )

            # 格式化结果
            chunks = []
            for r in results:
                chunks.append(
                    f"--- {r.file_path}:{r.start_line}-{r.end_line} "
                    f"(相似度: {r.score:.2f}) ---\n{r.content}"
                )

            return ToolResult(
                success=True,
                data="\n\n".join(chunks),
                metadata={"count": len(results), "query": query},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {e}")
