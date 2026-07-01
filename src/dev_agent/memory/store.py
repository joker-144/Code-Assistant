"""
记忆层 — SQLite 统一存储

存储内容:
  - conversations: 对话会话
  - messages: 对话消息（含工具调用）
  - file_index: 代码库文件索引（含 Embedding 向量）
  - lessons: 经验教训

从旧的"Milvus + PostgreSQL + SQLite"三套系统简化为单一 SQLite + 本地 Embedding。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from dev_agent.config import get_config


# ── Schema DDL ──

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_call_id TEXT,
    tool_name TEXT,
    tool_args TEXT,
    tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS file_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    content TEXT NOT NULL,
    embedding BLOB,
    file_hash TEXT,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    tags TEXT,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_file_index_path ON file_index(file_path);
"""


class MemoryStore:
    """SQLite 统一存储 — 线程安全的单例

    注意：单例以第一次初始化的 db_path 为准。
    如需切换数据库（如测试），调用 reset_store() 重置单例。
    """

    _instance: Optional["MemoryStore"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return
        config = get_config()
        self.db_path = db_path or config.memory_sqlite_path
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        self._initialized = True

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # ── 对话 ──

    def create_conversation(self, conv_id: str, title: str = "") -> None:
        """创建新对话"""
        self._conn.execute(
            "INSERT OR IGNORE INTO conversations (id, title) VALUES (?, ?)",
            (conv_id, title),
        )
        self._conn.commit()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_call_id: str = "",
        tool_name: str = "",
        tool_args: str = "",
        tokens: int = 0,
    ) -> int:
        """添加消息，返回消息 id"""
        cur = self._conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, tool_call_id, tool_name, tool_args, tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (conversation_id, role, content, tool_call_id or None,
             tool_name or None, tool_args or None, tokens),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict]:
        """获取对话的消息列表"""
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 文件索引 ──

    def store_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str,
        embedding: bytes,
        file_hash: str,
    ) -> None:
        """存储代码块（含向量）"""
        self._conn.execute(
            """INSERT INTO file_index
               (file_path, start_line, end_line, content, embedding, file_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (file_path, start_line, end_line, content, embedding, file_hash),
        )
        self._conn.commit()

    def delete_file_chunks(self, file_path: str) -> None:
        """删除指定文件的所有索引块（用于重新索引前清理）"""
        self._conn.execute(
            "DELETE FROM file_index WHERE file_path = ?",
            (file_path,),
        )
        self._conn.commit()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """获取文件已索引的 hash（用于增量更新判断）"""
        row = self._conn.execute(
            "SELECT file_hash FROM file_index WHERE file_path = ? LIMIT 1",
            (file_path,),
        ).fetchone()
        return row["file_hash"] if row else None

    def load_all_embeddings(self) -> list[dict]:
        """加载所有代码块向量（供向量搜索）

        Returns:
            list of {"id", "file_path", "start_line", "end_line", "content", "embedding"}
        """
        rows = self._conn.execute(
            "SELECT id, file_path, start_line, end_line, content, embedding FROM file_index"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 经验教训 ──

    def add_lesson(self, content: str, tags: str = "", embedding: bytes = b"") -> int:
        """添加经验教训"""
        cur = self._conn.execute(
            "INSERT INTO lessons (content, tags, embedding) VALUES (?, ?, ?)",
            (content, tags, embedding),
        )
        self._conn.commit()
        return cur.lastrowid

    # ── 统计 ──

    def stats(self) -> dict[str, Any]:
        """获取记忆系统统计"""
        conv_count = self._conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msg_count = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        chunk_count = self._conn.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
        lesson_count = self._conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
        return {
            "conversations": conv_count,
            "messages": msg_count,
            "file_chunks": chunk_count,
            "lessons": lesson_count,
            "db_path": self.db_path,
        }


def get_store() -> MemoryStore:
    """获取 MemoryStore 单例"""
    return MemoryStore()


def reset_store():
    """重置 MemoryStore 单例（用于测试或切换数据库）"""
    with MemoryStore._lock:
        if MemoryStore._instance is not None:
            try:
                MemoryStore._instance._conn.close()
            except Exception:
                pass
        MemoryStore._instance = None
