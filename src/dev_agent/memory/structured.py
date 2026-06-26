"""
结构化记忆 — 基于 SQLite 的关系型记忆存储
支持 PostgreSQL 可替换，存储任务历史、模型指标、路由决策
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


class StructuredMemory:
    """结构化记忆 — SQLite（默认）/ PostgreSQL（可选）"""

    def __init__(self, db_path: str = "data/memory.db", postgres_dsn: str = ""):
        self.db_path = db_path
        self.postgres_dsn = postgres_dsn
        self._use_postgres = bool(postgres_dsn)
        self._conn = None

        if self._use_postgres:
            self._init_postgres()
        else:
            self._init_sqlite()

    # ── 初始化 ──

    def _init_sqlite(self) -> None:
        """初始化 SQLite"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _init_postgres(self) -> None:
        """初始化 PostgreSQL（需要 psycopg2）"""
        try:
            import psycopg2
            self._conn = psycopg2.connect(self.postgres_dsn)
            self._create_tables()
        except ImportError:
            print("[StructuredMemory] psycopg2 未安装，降级为 SQLite")
            self._use_postgres = False
            self._init_sqlite()
        except Exception as e:
            print(f"[StructuredMemory] PostgreSQL 连接失败: {e}，降级为 SQLite")
            self._use_postgres = False
            self._init_sqlite()

    def _create_tables(self) -> None:
        """创建核心表"""
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                request_type TEXT NOT NULL,
                user_request TEXT NOT NULL,
                overall_approach TEXT,
                status TEXT DEFAULT 'pending',
                verdict TEXT,
                score INTEGER,
                cost REAL DEFAULT 0,
                duration REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sub_tasks (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                description TEXT,
                worker TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                review_score INTEGER,
                review_verdict TEXT,
                attempt_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS model_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0,
                avg_cost REAL DEFAULT 0,
                avg_duration REAL DEFAULT 0,
                date TEXT NOT NULL,
                UNIQUE(model_name, task_type, date)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS route_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_type TEXT NOT NULL,
                selected_model TEXT NOT NULL,
                was_correct BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

    # ── 任务记录 ──

    def record_task(
        self,
        task_id: str,
        request_type: str,
        user_request: str,
        overall_approach: str = "",
        status: str = "pending",
    ) -> None:
        """记录一个完整任务"""
        cur = self._conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO tasks (id, request_type, user_request, overall_approach, status)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, request_type, user_request, overall_approach, status),
        )
        self._conn.commit()

    def complete_task(
        self,
        task_id: str,
        verdict: str,
        score: int = 0,
        cost: float = 0,
        duration: float = 0,
    ) -> None:
        """标记任务完成"""
        cur = self._conn.cursor()
        cur.execute(
            """UPDATE tasks SET status='completed', verdict=?, score=?, cost=?, duration=?,
               completed_at=CURRENT_TIMESTAMP WHERE id=?""",
            (verdict, score, cost, duration, task_id),
        )
        self._conn.commit()

    def record_sub_task(
        self,
        sub_task_id: str,
        task_id: str,
        description: str,
        worker: str,
        status: str = "pending",
        result: str = "",
    ) -> None:
        """记录子任务"""
        cur = self._conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO sub_tasks (id, task_id, description, worker, status, result)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sub_task_id, task_id, description, worker, status, result),
        )
        self._conn.commit()

    def update_sub_task_review(
        self,
        sub_task_id: str,
        score: int,
        verdict: str,
        attempt: int,
    ) -> None:
        """更新子任务审查结果"""
        cur = self._conn.cursor()
        cur.execute(
            """UPDATE sub_tasks SET review_score=?, review_verdict=?, attempt_count=?, status='done'
               WHERE id=?""",
            (score, verdict, attempt, sub_task_id),
        )
        self._conn.commit()

    # ── 智能路由 ──

    def get_best_worker_for(self, request_type: str) -> str:
        """根据历史成功率推荐最佳 worker"""
        cur = self._conn.cursor()
        cur.execute(
            """SELECT model_name, success_count, fail_count
               FROM model_metrics
               WHERE task_type = ? AND date >= date('now', '-7 days')
               ORDER BY (success_count * 1.0 / MAX(success_count + fail_count, 1)) DESC
               LIMIT 1""",
            (request_type,),
        )
        row = cur.fetchone()
        if row:
            return row["model_name"]
        return "code_worker"  # 默认

    # ── 历史搜索 ──

    def find_similar_tasks(self, query: str, limit: int = 5) -> list[dict]:
        """查找相似的历史任务（关键词匹配）"""
        keywords = query.lower().split()
        cur = self._conn.cursor()
        cur.execute(
            """SELECT * FROM tasks WHERE status='completed'
               ORDER BY created_at DESC LIMIT 200"""
        )
        rows = cur.fetchall()

        scored = []
        for row in rows:
            text = (row["user_request"] + " " + (row["overall_approach"] or "")).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def get_failed_tasks(self, hours: int = 72) -> list[dict]:
        """获取最近 N 小时失败的任务"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """SELECT * FROM tasks WHERE verdict IN ('retry', 'abort')
               AND created_at >= ? ORDER BY created_at DESC""",
            (cutoff,),
        )
        return [dict(row) for row in cur.fetchall()]

    # ── 报告 ──

    def get_daily_report(self) -> dict:
        """获取今日任务报告"""
        today = datetime.now().strftime("%Y-%m-%d")
        cur = self._conn.cursor()

        cur.execute(
            """SELECT COUNT(*) as total, SUM(CASE WHEN verdict='pass' THEN 1 ELSE 0 END) as passed
               FROM tasks WHERE date(created_at) = ?""",
            (today,),
        )
        row = cur.fetchone()

        return {
            "date": today,
            "total_tasks": row["total"] or 0,
            "passed_tasks": row["passed"] or 0,
            "pass_rate": (row["passed"] or 0) / max(row["total"] or 1, 1) * 100,
        }

    # ── 模型指标 ──

    def update_model_metrics(
        self,
        model_name: str,
        task_type: str,
        success: bool,
        cost: float = 0,
        duration: float = 0,
    ) -> None:
        """更新模型性能指标"""
        today = datetime.now().strftime("%Y-%m-%d")
        cur = self._conn.cursor()

        cur.execute(
            """INSERT INTO model_metrics (model_name, task_type, success_count, fail_count, avg_score, avg_cost, avg_duration, date)
               VALUES (?, ?, ?, ?, 0, ?, ?, ?)
               ON CONFLICT(model_name, task_type, date) DO UPDATE SET
               success_count = success_count + ?,
               fail_count = fail_count + ?,
               avg_cost = (avg_cost + ?) / 2,
               avg_duration = (avg_duration + ?) / 2""",
            (
                model_name, task_type,
                1 if success else 0, 0 if success else 1,
                cost, duration, today,
                1 if success else 0, 0 if success else 1,
                cost, duration,
            ),
        )
        self._conn.commit()

    # ── 对话记录 ──

    def add_conversation(self, session_id: str, role: str, content: str) -> None:
        """记录对话"""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        self._conn.commit()

    def get_conversation(self, session_id: str, limit: int = 50) -> list[dict]:
        """获取对话历史"""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT role, content FROM conversations WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    # ── 路由决策 ──

    def record_route_decision(self, request_type: str, selected_model: str, was_correct: bool) -> None:
        """记录路由决策"""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO route_decisions (request_type, selected_model, was_correct) VALUES (?, ?, ?)",
            (request_type, selected_model, was_correct),
        )
        self._conn.commit()

    def get_worst_routes(self, limit: int = 5) -> list[dict]:
        """获取错误率最高的路由规则"""
        cur = self._conn.cursor()
        cur.execute(
            """SELECT request_type, selected_model,
               SUM(CASE WHEN was_correct=0 THEN 1 ELSE 0 END) as wrong_count,
               COUNT(*) as total
               FROM route_decisions
               GROUP BY request_type, selected_model
               ORDER BY wrong_count * 1.0 / total DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()