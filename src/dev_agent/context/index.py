"""
项目代码库索引 — 文件分块 + Embedding + 向量检索

这是新架构最关键的新增组件。它让 Agent 能"看到"整个代码库的内容，
并根据用户需求检索相关文件——这是 Cursor "理解你的项目"的核心机制。

工作流程:
  1. index_project(): 遍历项目源文件 → 按函数/类边界分块 → Embedding → 存入 SQLite
  2. search(): 将查询转为 Embedding → 在 SQLite 中做余弦相似度搜索 → 返回相关代码块

Embedding: 本地 sentence-transformers（all-MiniLM-L6-v2，384 维）
  - 模型约 80MB，首次使用时通过 huggingface-hub 官方源下载
  - 可在 .env 中设置 HF_ENDPOINT=https://hf-mirror.com 切换国内镜像
  - 纯本地推理，无网络调用开销，无 API Key 依赖
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from dev_agent.memory.store import MemoryStore


@dataclass
class CodeChunk:
    """代码块"""
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float = 0.0  # 搜索时的相似度得分


# ── 本地 Embedder（sentence-transformers）──

class LocalEmbedder:
    """本地 Embedder — 基于 sentence-transformers 的 all-MiniLM-L6-v2

    特点:
      - 纯本地推理，无 API 调用，无网络开销
      - 模型约 80MB，首次使用通过 huggingface-hub 官方源下载
      - 输出 384 维向量，适合语义搜索和记忆检索
      - 可在 .env 中设置 HF_ENDPOINT=https://hf-mirror.com 切换国内镜像
    """

    _model = None  # 类级单例（避免重复加载模型）

    def __init__(self):
        # 优先从 .env 读取 HF_ENDPOINT，未设置时默认走国内镜像（避免连接超时）
        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    def _ensure_model(self):
        """延迟加载模型（类级单例，所有实例共享）"""
        if LocalEmbedder._model is None:
            from sentence_transformers import SentenceTransformer
            from dev_agent.config import get_config
            config = get_config()
            model_name = config.llm_embedding_model
            LocalEmbedder._model = SentenceTransformer(model_name)
        return LocalEmbedder._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """批量生成向量

        Args:
            texts: 待编码的文本列表

        Returns:
            np.ndarray: shape=(len(texts), 384)，dtype=float32
        """
        if not texts:
            return np.array([], dtype=np.float32)

        model = self._ensure_model()
        # sentence-transformers 的 encode 直接返回 numpy 数组
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=64,
        )
        return np.array(embeddings, dtype=np.float32)


# 兼容别名 — 旧代码中引用 ZhipuEmbedder 的地方仍可正常 import
ZhipuEmbedder = LocalEmbedder


# ── 项目索引 ──

class ProjectIndex:
    """项目代码库索引 — 文件分块 + Embedding + 向量检索"""

    # 支持索引的文件扩展名
    INDEXABLE_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
        ".kt", ".scala", ".sh", ".bash", ".ps1",
        ".md", ".txt", ".rst",
        ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
        ".html", ".css", ".scss", ".sql",
    }

    # 索引时排除的目录
    EXCLUDE_DIRS = {
        "__pycache__", ".git", ".venv", "venv", "env", "node_modules",
        ".egg-info", "data", "dist", "build", ".idea", ".vscode",
        "devagent-architecture-review",  # 排除架构评估文档
    }

    # 单文件最大块数（防止超大文件拖慢索引）
    MAX_CHUNKS_PER_FILE = 50
    # 单块最大行数
    MAX_CHUNK_LINES = 80

    def __init__(self, workspace: Path, store: Optional[MemoryStore] = None):
        self.workspace = workspace.resolve()
        self.store = store or MemoryStore()
        self._embedder = None  # 延迟初始化（首次使用时创建）
        self._embeddings_cache: list[dict] | None = None  # 向量缓存（索引后失效）

    @property
    def embedder(self) -> LocalEmbedder:
        """延迟创建本地 Embedder"""
        if self._embedder is None:
            self._embedder = LocalEmbedder()
        return self._embedder

    # ── 索引 ──

    def index_project(self, force: bool = False) -> dict:
        """索引整个项目

        Args:
            force: 是否强制重新索引（忽略 hash 跳过逻辑）

        Returns:
            统计信息 {"files": N, "chunks": N, "skipped": N}
        """
        stats = {"files": 0, "chunks": 0, "skipped": 0}

        # 索引后向量缓存失效
        self._embeddings_cache = None

        for file_path in self._walk_source_files():
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            rel_path = str(file_path.relative_to(self.workspace)).replace("\\", "/")
            file_hash = hashlib.md5(content.encode()).hexdigest()

            # 增量更新：跳过未修改的文件
            if not force and self.store.get_file_hash(rel_path) == file_hash:
                stats["skipped"] += 1
                continue

            # 清理旧索引，重新分块
            self.store.delete_file_chunks(rel_path)

            chunks = self._chunk_file(content, rel_path)
            if not chunks:
                continue

            # 批量生成 Embedding（本地 sentence-transformers）
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embedder.encode(chunk_texts)

            for chunk, emb in zip(chunks, embeddings):
                emb_bytes = emb.tobytes()
                self.store.store_chunk(
                    file_path=rel_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    embedding=emb_bytes,
                    file_hash=file_hash,
                )
                stats["chunks"] += 1

            stats["files"] += 1

        return stats

    def _walk_source_files(self):
        """遍历项目中所有可索引的源文件"""
        for root, dirs, files in os.walk(self.workspace):
            # 过滤排除目录（原地修改 dirs 实现 prune）
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() in self.INDEXABLE_EXTENSIONS:
                    # 跳过二进制和大文件（> 1MB）
                    try:
                        if fpath.stat().st_size > 1024 * 1024:
                            continue
                    except OSError:
                        continue
                    yield fpath

    def _chunk_file(self, content: str, file_path: str) -> list[CodeChunk]:
        """将文件分块（按函数/类边界，兼顾行数上限）

        对 Python/JS/TS 等尝试按 def/class/function 边界切分；
        其他文件按固定行数切分。
        """
        lines = content.splitlines()
        if not lines:
            return []

        # 按语义边界分块（函数/类定义处切分）
        boundary_re = re.compile(
            r"^\s*(def |class |function |export function |export default function |"
            r"public |private |protected |static |async )",
            re.MULTILINE,
        )

        chunks: list[CodeChunk] = []
        current_start = 0
        chunk_count = 0

        for i, line in enumerate(lines):
            # 达到行数上限或遇到新的语义边界（非首行）
            is_boundary = i > 0 and boundary_re.match(line)
            is_full = (i - current_start) >= self.MAX_CHUNK_LINES

            if (is_boundary or is_full) and i > current_start:
                chunk_content = "\n".join(lines[current_start:i])
                chunks.append(CodeChunk(
                    file_path=file_path,
                    start_line=current_start + 1,
                    end_line=i,
                    content=chunk_content,
                ))
                current_start = i
                chunk_count += 1
                if chunk_count >= self.MAX_CHUNKS_PER_FILE:
                    break

        # 收尾：最后一块
        if current_start < len(lines) and chunk_count < self.MAX_CHUNKS_PER_FILE:
            chunk_content = "\n".join(lines[current_start:])
            chunks.append(CodeChunk(
                file_path=file_path,
                start_line=current_start + 1,
                end_line=len(lines),
                content=chunk_content,
            ))

        return chunks

    # ── 搜索 ──

    def search(self, query: str, top_k: int = 5) -> list[CodeChunk]:
        """语义搜索代码库

        余弦相似度计算与维度无关，自动适配本地 Embedder 的向量维度。

        Args:
            query: 自然语言查询
            top_k: 返回结果数量

        Returns:
            最相关的代码块列表（按相似度降序）
        """
        # 1. 将 query 转为 embedding
        query_vec = self.embedder.encode([query])[0]

        # 2. 加载所有向量做余弦相似度搜索（带缓存）
        if self._embeddings_cache is None:
            self._embeddings_cache = self.store.load_all_embeddings()
        rows = self._embeddings_cache
        if not rows:
            return []

        # 计算相似度（维度自动适配）
        scored: list[CodeChunk] = []
        for row in rows:
            if row["embedding"] is None:
                continue
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
            if emb.shape[0] != query_vec.shape[0]:
                # 维度不匹配（旧索引数据），跳过
                continue
            score = float(np.dot(query_vec, emb) / (
                np.linalg.norm(query_vec) * np.linalg.norm(emb) + 1e-8
            ))
            scored.append(CodeChunk(
                file_path=row["file_path"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                content=row["content"],
                score=score,
            ))

        # 3. 按相似度降序，返回 top_k
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]