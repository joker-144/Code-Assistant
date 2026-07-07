"""
长期记忆系统 — Long-Term Memory

在现有 MemoryStore SQLite 基础上增强:
- 经验教训的语义检索（基于向量相似度）
- 会话关键节点提取与存储
- 项目知识图谱构建（文件间依赖关系）
- 跨会话记忆召回

参考 2026 标准：向量数据库 + 知识图谱混合架构
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from dev_agent.memory.store import MemoryStore


@dataclass
class KnowledgeNode:
    """知识图谱节点"""
    node_type: str  # "file" | "function" | "class" | "concept"
    name: str
    description: str = ""
    metadata: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class KnowledgeEdge:
    """知识图谱边"""
    source: str   # 源节点名称
    target: str   # 目标节点名称
    relation: str  # "imports" | "calls" | "inherits" | "depends_on" | "related_to"


class LongTermMemory:
    """长期记忆管理器

    功能:
    1. 经验教训管理 — 每次对话后提取关键经验
    2. 语义检索 — 基于向量相似度检索历史经验
    3. 知识图谱 — 项目文件/函数/类的依赖关系
    4. 会话摘要 — 跨会话的记忆召回
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or MemoryStore()
        self._graph_nodes: dict[str, KnowledgeNode] = {}
        self._graph_edges: list[KnowledgeEdge] = []

    # ── 经验教训 ──

    def learn(self, content: str, tags: str = "", embedding: Optional[np.ndarray] = None) -> int:
        """记录一条经验教训

        Args:
            content: 经验内容
            tags: 标签（逗号分隔）
            embedding: 向量（可选，用于后续语义检索）

        Returns:
            记录 ID
        """
        emb_bytes = embedding.tobytes() if embedding is not None else b""
        return self.store.add_lesson(content, tags, emb_bytes)

    def recall_lessons(self, tags: Optional[str] = None, limit: int = 10) -> list[dict]:
        """召回经验教训

        Args:
            tags: 按标签过滤（可选）
            limit: 最大返回数
        """
        if tags:
            rows = self.store.conn.execute(
                "SELECT * FROM lessons WHERE tags LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{tags}%", limit),
            ).fetchall()
        else:
            rows = self.store.conn.execute(
                "SELECT * FROM lessons ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def semantic_recall(self, query_embedding: np.ndarray, top_k: int = 5) -> list[dict]:
        """基于向量相似度检索经验

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
        """
        rows = self.store.conn.execute(
            "SELECT * FROM lessons WHERE embedding IS NOT NULL AND length(embedding) > 0"
        ).fetchall()

        scored = []
        for row in rows:
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
            if emb.shape[0] != query_embedding.shape[0]:
                continue
            score = float(np.dot(query_embedding, emb) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(emb) + 1e-8
            ))
            scored.append((score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    # ── 知识图谱 ──

    def add_node(self, node: KnowledgeNode):
        """添加知识图谱节点"""
        self._graph_nodes[node.name] = node

    def add_edge(self, edge: KnowledgeEdge):
        """添加知识图谱边"""
        if edge not in self._graph_edges:
            self._graph_edges.append(edge)

    def get_related_files(self, file_path: str, depth: int = 1) -> list[str]:
        """获取与指定文件相关联的其他文件

        Args:
            file_path: 文件路径
            depth: 关系深度（1=直接依赖，2=间接依赖）
        """
        related = set()
        current = {file_path}

        for _ in range(depth):
            next_level = set()
            for edge in self._graph_edges:
                if edge.source in current:
                    next_level.add(edge.target)
                if edge.target in current:
                    next_level.add(edge.source)
            related.update(next_level)
            current = next_level

        return sorted(related)

    def build_project_graph(self, workspace_files: list[str]):
        """从项目文件列表构建知识图谱（基于 import 分析）

        分析 Python import 语句建立文件间依赖关系。
        """
        import re

        import_pattern = re.compile(
            r"^(?:from\s+(\S+)\s+import|import\s+(\S+))",
            re.MULTILINE,
        )

        for fpath in workspace_files:
            node_name = fpath.replace("/", ".").replace(".py", "").replace("\\", ".")
            self.add_node(KnowledgeNode(
                node_type="file",
                name=node_name,
                description=fpath,
            ))

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            for match in import_pattern.finditer(content):
                imported = match.group(1) or match.group(2)
                if imported:
                    self.add_edge(KnowledgeEdge(
                        source=node_name,
                        target=imported.split(".")[0],
                        relation="imports",
                    ))

    def get_graph_stats(self) -> dict:
        """知识图谱统计"""
        return {
            "nodes": len(self._graph_nodes),
            "edges": len(self._graph_edges),
            "node_types": {
                t: sum(1 for n in self._graph_nodes.values() if n.node_type == t)
                for t in {n.node_type for n in self._graph_nodes.values()}
            },
            "top_relations": self._get_top_relations(),
        }

    def _get_top_relations(self) -> list[dict]:
        """获取最常见的边关系"""
        from collections import Counter
        counter = Counter(e.relation for e in self._graph_edges)
        return [{"relation": rel, "count": cnt} for rel, cnt in counter.most_common(5)]

    # ── 会话关键节点 ──

    def extract_session_insights(self, messages: list[dict]) -> str:
        """从对话消息中提取关键洞察

        启发式规则提取: 决策点、发现的问题、成功经验
        """
        insights = []

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # 跳过短消息
            if len(content) < 30:
                continue

            # 提取决策信息
            indicators = {
                "decision": ["决定", "选择", "采用", "最终方案"],
                "problem": ["错误", "失败", "问题", "bug", "异常"],
                "success": ["成功", "完成", "通过", "解决"],
                "learning": ["发现", "注意", "以后", "下次"],
            }

            for insight_type, keywords in indicators.items():
                if any(kw in content for kw in keywords):
                    if role == "assistant":
                        insights.append(f"[{insight_type}] Agent: {content[:200]}")
                    elif role == "user":
                        insights.append(f"[{insight_type}] User: {content[:200]}")

        return "\n".join(insights[-10:])  # 保留最近 10 条

    # ── 统计 ──

    def stats(self) -> dict:
        """长期记忆统计"""
        base = self.store.stats()
        base.update({
            "graph_nodes": len(self._graph_nodes),
            "graph_edges": len(self._graph_edges),
        })
        return base


def create_long_term_memory() -> LongTermMemory:
    return LongTermMemory()
