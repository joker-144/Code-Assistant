"""
长期记忆 — 基于 Milvus 的向量记忆
存储项目架构、历史经验、解决方案，支持语义检索
降级策略：Milvus 不可用时降级为 JSON 文件存储
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from dev_agent.config import MemoryConfig


class LongTermMemory:
    """长期语义记忆 — Milvus 向量存储 + JSON 降级"""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._milvus_available = False
        self._collection = None
        self._fallback_path = Path("data") / "long_term_fallback.json"
        self._fallback_data: list[dict] = []

        # 尝试连接 Milvus
        try:
            self._connect_milvus()
        except Exception:
            print("[Memory] Milvus 不可用，使用 JSON 文件降级存储")

        # 加载降级数据
        self._load_fallback()

    # ── 公共 API ──

    def remember(
        self,
        text: str,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
    ) -> str:
        """存储一条记忆"""
        entry = {
            "text": text,
            "metadata": metadata or {},
            "timestamp": time.time(),
            "embedding": embedding or [],
        }

        if self._milvus_available:
            return self._milvus_insert(entry)
        else:
            return self._fallback_insert(entry)

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """语义搜索相关记忆"""
        if self._milvus_available:
            return self._milvus_search(query, top_k)
        else:
            return self._fallback_search(query, top_k)

    def recall_lessons(self, task_keywords: str, top_k: int = 5) -> list[dict]:
        """搜索相关经验教训"""
        return self.recall(f"经验教训: {task_keywords}", top_k)

    def remember_project_context(self, description: str) -> str:
        """记录项目架构信息"""
        return self.remember(description, metadata={"type": "project_context"})

    def remember_lesson(self, text: str, tags: Optional[list[str]] = None) -> str:
        """记录经验教训"""
        return self.remember(text, metadata={"type": "lesson", "tags": tags or []})

    def stats(self) -> dict:
        """获取记忆统计"""
        if self._milvus_available:
            try:
                count = self._collection.num_entities
                return {"backend": "milvus", "total_entries": count}
            except Exception:
                pass

        return {
            "backend": "json_fallback",
            "total_entries": len(self._fallback_data),
            "fallback_path": str(self._fallback_path),
        }

    # ── Milvus 实现 ──

    def _connect_milvus(self) -> None:
        """连接 Milvus"""
        from pymilvus import (
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            connections,
            utility,
        )

        connections.connect(
            alias="default",
            host=self.config.milvus_host,
            port=self.config.milvus_port,
        )

        collection_name = self.config.milvus_collection

        if not utility.has_collection(collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.config.embedding_dim),
                FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="timestamp", dtype=DataType.DOUBLE),
            ]
            schema = CollectionSchema(fields, description="DevAgent 长期记忆")
            collection = Collection(name=collection_name, schema=schema)

            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            collection.create_index(field_name="embedding", index_params=index_params)
        else:
            collection = Collection(name=collection_name)

        collection.load()
        self._collection = collection
        self._milvus_available = True

    def _milvus_insert(self, entry: dict) -> str:
        """插入 Milvus"""
        embedding = entry.get("embedding") or [0.0] * self.config.embedding_dim
        data = [
            [entry["text"]],
            [embedding],
            [json.dumps(entry.get("metadata", {}), ensure_ascii=False)],
            [entry["timestamp"]],
        ]
        result = self._collection.insert(data)
        return str(result.primary_keys[0])

    def _milvus_search(self, query: str, top_k: int) -> list[dict]:
        """Milvus 语义搜索"""
        # 使用空向量做全量搜索 + 文本匹配（无 embedding 模型时的降级方案）
        # 生产环境应使用真实的 embedding 模型
        try:
            self._collection.load()
            # 使用随机向量模拟搜索（实际应使用 embedding 模型生成 query vector）
            # 这里降级为文本关键词匹配
            results = self._collection.query(
                expr="",
                output_fields=["text", "metadata_json", "timestamp"],
                limit=top_k * 10,
            )

            # 文本匹配过滤
            keywords = query.lower().split()
            scored = []
            for r in results:
                text_lower = r.get("text", "").lower()
                score = sum(1 for kw in keywords if kw in text_lower)
                if score > 0:
                    scored.append((score, r))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [
                {
                    "text": r["text"],
                    "metadata": json.loads(r.get("metadata_json", "{}")),
                    "score": s,
                }
                for s, r in scored[:top_k]
            ]
        except Exception:
            return []

    # ── JSON 降级实现 ──

    def _fallback_insert(self, entry: dict) -> str:
        """JSON 文件降级存储"""
        entry_id = f"mem_{int(time.time() * 1000)}"
        entry["id"] = entry_id
        self._fallback_data.append(entry)
        self._save_fallback()
        return entry_id

    def _fallback_search(self, query: str, top_k: int) -> list[dict]:
        """JSON 文件降级搜索（简单关键词匹配）"""
        keywords = query.lower().split()
        scored = []

        for entry in self._fallback_data:
            text_lower = entry.get("text", "").lower()
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "text": e["text"],
                "metadata": e.get("metadata", {}),
                "score": s,
                "timestamp": e.get("timestamp", 0),
            }
            for s, e in scored[:top_k]
        ]

    def _load_fallback(self) -> None:
        """加载降级存储"""
        if self._fallback_path.exists():
            try:
                self._fallback_data = json.loads(self._fallback_path.read_text("utf-8"))
            except (json.JSONDecodeError, Exception):
                self._fallback_data = []

    def _save_fallback(self) -> None:
        """保存降级存储"""
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_path.write_text(
            json.dumps(self._fallback_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )