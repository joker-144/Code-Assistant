"""
核心编排器 — 串联大脑、手脚、工具、记忆四层
执行流程: 回忆 → 规划 → 编码 → 审查 → 仲裁 → 记录
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Optional

from dev_agent.brain.arbitrator import Arbitrator
from dev_agent.brain.planner import ExecutionPlan, Planner, SubTask
from dev_agent.config import AgentConfig, get_config
from dev_agent.llm_client import (
    create_deepseek_client,
    create_deepseek_code_client,
    create_qwen_client,
)
from dev_agent.memory.long_term import LongTermMemory
from dev_agent.memory.short_term import ShortTermMemory
from dev_agent.memory.structured import StructuredMemory
from dev_agent.tools.tool_system import ToolRegistry
from dev_agent.workers.code_worker import CodeWorker
from dev_agent.workers.qwen_worker import ReviewWorker


def _load_prompt(name: str) -> str:
    """加载 prompt 模板"""
    prompt_path = Path(__file__).parent.parent / "prompts" / name
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "{}"


class Orchestrator:
    """核心编排器 — 串联所有模块"""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or get_config()
        self.workspace = Path(self.config.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 工具
        self.tools = ToolRegistry(self.workspace)

        # 记忆系统
        self.short_memory = ShortTermMemory(
            max_tokens=self.config.max_context_tokens,
            summary_trigger=self.config.summary_trigger_tokens,
        )
        self.long_memory = LongTermMemory(self.config.memory)
        self.structured_memory = StructuredMemory(
            db_path=self.config.memory.sqlite_path,
            postgres_dsn=self.config.memory.postgres_dsn,
        )

        # LLM 客户端
        self.deepseek = create_deepseek_client(self.config)
        self.deepseek_code = create_deepseek_code_client(self.config)
        self.qwen = create_qwen_client(self.config)

        # 大脑层
        self.planner = Planner(self.deepseek, _load_prompt("planner.txt"))
        self.arbitrator = Arbitrator(self.deepseek, _load_prompt("arbitrate.txt"))

        # 手脚层
        self.code_worker = CodeWorker(
            self.deepseek_code, self.tools, _load_prompt("code_gen.txt")
        )
        self.review_worker = ReviewWorker(self.qwen, _load_prompt("review.txt"))

    # ── 主执行入口 ──

    def execute(self, user_request: str, request_type: str = "code_gen") -> dict:
        """
        执行一次完整的开发任务

        流程:
        1. 搜索历史经验
        2. 大脑规划
        3. 执行子任务（编码 → 审查 → 仲裁 → 重试）
        4. 记录结果
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        if self.config.verbose:
            print(f"\n{'='*60}")
            print(f"  DevAgent 开始执行任务: {task_id}")
            print(f"  需求: {user_request}")
            print(f"{'='*60}\n")

        # Step 1: 搜索历史经验
        context = self._build_context(user_request)

        # Step 2: 大脑规划
        if self.config.verbose:
            print("🧠 大脑分析需求中...")

        plan = self.planner.plan(user_request, context)

        if self.config.verbose:
            print(f"  方案: {plan.overall_approach}")
            print(f"  子任务数: {len(plan.sub_tasks)}")
            print()

        # 记录任务
        self.structured_memory.record_task(
            task_id=task_id,
            request_type=request_type,
            user_request=user_request,
            overall_approach=plan.overall_approach,
            status="running",
        )

        # Step 3: 执行子任务
        results: dict[str, Any] = {}
        all_code = ""
        total_cost = 0

        for task in plan.sub_tasks:
            if self.config.verbose:
                print(f"🔧 执行 {task.id}: {task.description}")

            self.structured_memory.record_sub_task(
                sub_task_id=task.id,
                task_id=task_id,
                description=task.description,
                worker=task.worker,
                status="running",
            )

            try:
                if task.worker == "code_worker":
                    result = self._execute_code_task(task, plan, results)
                    all_code = result
                elif task.worker == "review_worker":
                    result = self._execute_review_task(task, plan, results, all_code)
                else:
                    result = f"brain task: {task.description}"

                task.status = "done"
                task.result = str(result)
                results[task.id] = result

                self.structured_memory.record_sub_task(
                    sub_task_id=task.id,
                    task_id=task_id,
                    description=task.description,
                    worker=task.worker,
                    status="done",
                    result=str(result)[:500],
                )

                if self.config.verbose:
                    print(f"  ✅ {task.id} 完成")

            except Exception as e:
                task.status = "failed"
                task.result = str(e)
                results[task.id] = {"error": str(e)}

                if self.config.verbose:
                    print(f"  ❌ {task.id} 失败: {e}")

                # 决定下一步
                decision = self.arbitrator.decide_next_step(
                    str(e),
                    [
                        {"id": t.id, "status": t.status}
                        for t in plan.sub_tasks
                    ],
                )
                if decision == "abort":
                    break

        # Step 4: 记录结果
        duration = time.time() - start_time
        final_verdict = results.get("review", {}).get("verdict", "completed")
        final_score = results.get("review", {}).get("score", 0)

        self.structured_memory.complete_task(
            task_id=task_id,
            verdict=final_verdict if isinstance(final_verdict, str) else "completed",
            score=final_score if isinstance(final_score, int) else 0,
            cost=total_cost,
            duration=duration,
        )

        # 存储经验
        self.long_memory.remember_lesson(
            f"任务: {user_request}\n方案: {plan.overall_approach}\n结果: {final_verdict}",
            tags=[request_type, final_verdict if isinstance(final_verdict, str) else "completed"],
        )

        if self.config.verbose:
            print(f"\n{'='*60}")
            print(f"  执行完成 | 耗时: {duration:.1f}s | 状态: {final_verdict}")
            print(f"{'='*60}\n")

        return self._build_summary(plan, results, task_id, duration)

    # ── 子任务执行 ──

    def _execute_code_task(
        self,
        task: SubTask,
        plan: ExecutionPlan,
        results: dict,
    ) -> str:
        """执行代码生成子任务"""
        # 收集已有文件上下文
        existing_files = self._get_existing_files_context()

        # 收集已完成任务的输出
        completed_context = ""
        for dep_id in task.depends_on:
            if dep_id in results:
                completed_context += f"\n前置任务 {dep_id} 的结果:\n{results[dep_id]}"

        return self.code_worker.generate_code(
            task_description=task.description,
            context=task.input_context + completed_context,
            existing_files=existing_files,
            constraints=plan.architecture_notes,
        )

    def _execute_review_task(
        self,
        task: SubTask,
        plan: ExecutionPlan,
        results: dict,
        all_code: str,
    ) -> dict:
        """执行审查 + 仲裁循环"""
        if not all_code:
            # 收集所有代码生成结果
            code_parts = []
            for subtask in plan.sub_tasks:
                if subtask.worker == "code_worker" and subtask.id in results:
                    code_parts.append(str(results[subtask.id]))
            all_code = "\n\n".join(code_parts)

        for attempt in range(self.config.max_retries):
            if self.config.verbose:
                print(f"    📝 审查尝试 {attempt + 1}/{self.config.max_retries}")

            # Qwen 审查
            review = self.review_worker.review_code(all_code, plan.user_request)

            if self.config.verbose:
                score = review.get("overall_score", "?")
                print(f"    审查评分: {score}/10")

            # DeepSeek 仲裁
            decision = self.arbitrator.review_code(
                plan.user_request, all_code, review
            )

            if self.config.verbose:
                print(f"    仲裁: {decision.verdict} (评分: {decision.score}/10)")

            if decision.verdict == "pass":
                return {
                    "review": review,
                    "decision": decision.verdict,
                    "score": decision.score,
                    "attempt": attempt + 1,
                }
            elif decision.verdict == "abort":
                return {
                    "review": review,
                    "decision": "abort",
                    "score": decision.score,
                    "attempt": attempt + 1,
                }
            elif decision.verdict == "retry_with_feedback":
                # 带着反馈修复
                all_code = self.code_worker.fix_code(all_code, decision.feedback)
            elif decision.verdict == "retry":
                # 完全重写
                all_code = self.code_worker.generate_code(
                    task_description=plan.user_request,
                    context=plan.architecture_notes,
                    constraints=decision.feedback,
                )

        # 超过最大重试次数，接受当前结果
        return {
            "review": review,
            "decision": "accepted_after_max_retries",
            "score": review.get("overall_score", 0),
            "attempt": self.config.max_retries,
        }

    # ── 辅助方法 ──

    def _build_context(self, user_request: str) -> str:
        """构建上下文（来自长期记忆）"""
        parts = []

        # 搜索相关经验
        lessons = self.long_memory.recall_lessons(user_request, top_k=3)
        if lessons:
            parts.append("## 历史相关经验")
            for lesson in lessons:
                parts.append(f"- {lesson['text'][:200]}")

        # 搜索相似任务
        similar = self.structured_memory.find_similar_tasks(user_request, limit=3)
        if similar:
            parts.append("\n## 相似历史任务")
            for task in similar:
                parts.append(
                    f"- [{task.get('verdict', '?')}] {task['user_request'][:100]}"
                )

        return "\n".join(parts) if parts else "无历史经验"

    def _get_existing_files_context(self) -> str:
        """获取工作区已有文件上下文"""
        result = self.tools.file.snapshot(".")
        if result.success:
            return f"当前项目文件结构:\n{result.data}"
        return "无已有文件"

    def _build_summary(
        self,
        plan: ExecutionPlan,
        results: dict,
        task_id: str,
        duration: float,
    ) -> dict:
        """构建执行摘要"""
        subtask_summaries = []
        for task in plan.sub_tasks:
            subtask_summaries.append({
                "id": task.id,
                "description": task.description,
                "worker": task.worker,
                "status": task.status,
            })

        return {
            "task_id": task_id,
            "user_request": plan.user_request,
            "overall_approach": plan.overall_approach,
            "architecture_notes": plan.architecture_notes,
            "estimated_files": plan.estimated_files,
            "sub_tasks": subtask_summaries,
            "duration_seconds": round(duration, 1),
            "results": {k: str(v)[:500] for k, v in results.items()},
        }

    def review_code(self, code: str, task_description: str = "") -> dict:
        """独立审查代码（不经过完整流程）"""
        return self.review_worker.review_code(code, task_description)

    def generate_docs(self, code: str) -> str:
        """为代码生成文档"""
        return self.review_worker.generate_docs(code)

    def memory_stats(self) -> dict:
        """获取记忆系统统计"""
        return {
            "short_term": self.short_memory.stats(),
            "long_term": self.long_memory.stats(),
            "structured": self.structured_memory.get_daily_report(),
        }


# ── 全局单例 ──

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """获取全局编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator