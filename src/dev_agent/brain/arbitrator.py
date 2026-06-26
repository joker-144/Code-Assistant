"""
大脑层 — 质量仲裁器
DeepSeek-V4-Pro 审查 worker 执行结果，做出 pass/retry/retry_with_feedback 决策
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from dev_agent.llm_client import LLMClient


@dataclass
class ReviewResult:
    """仲裁结果"""
    verdict: str          # "pass" | "retry" | "retry_with_feedback" | "abort"
    feedback: str = ""    # 修改意见
    score: int = 0        # 1-10
    issues: list[str] = field(default_factory=list)


class Arbitrator:
    """质量仲裁器 — 用 DeepSeek-V4-Pro 做最终质量决策"""

    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self.llm = llm_client
        self.prompt_template = prompt_template

    def review_code(
        self,
        task_description: str,
        code: str,
        review_result: dict,
    ) -> ReviewResult:
        """审查代码，做出最终判决"""
        prompt = self.prompt_template.format(
            task_description=task_description,
            code=code[:8000],  # 截断过长代码
            review_result=json.dumps(review_result, ensure_ascii=False, indent=2),
        )

        messages = [
            {"role": "system", "content": "你是质量仲裁官，只输出 JSON 格式的判决结果。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw = self.llm.chat_json(messages, temperature=0.2)
            return ReviewResult(
                verdict=raw.get("verdict", "pass"),
                feedback=raw.get("feedback", ""),
                score=raw.get("score", 0),
                issues=raw.get("issues", []),
            )
        except Exception as e:
            return ReviewResult(
                verdict="retry_with_feedback",
                feedback=f"仲裁解析失败: {e}",
                score=0,
                issues=[str(e)],
            )

    def decide_next_step(
        self,
        error_message: str,
        task_history: list[dict],
    ) -> str:
        """遇到错误时决定下一步：continue | retry | skip | replan | abort"""
        messages = [
            {"role": "system", "content": "你是系统决策者，根据错误信息决定下一步行动。"},
            {"role": "user", "content": f"""执行过程中遇到错误:
{error_message}

已完成的任务历史:
{json.dumps(task_history, ensure_ascii=False, indent=2)}

请决定下一步（只输出一个词）: continue | retry | skip | replan | abort"""},
        ]

        try:
            decision = self.llm.chat(messages, temperature=0.1, max_tokens=10)
            decision = decision.strip().lower()
            valid = {"continue", "retry", "skip", "replan", "abort"}
            return decision if decision in valid else "retry"
        except Exception:
            return "retry"


def _load_prompt(name: str) -> str:
    """加载 prompt 模板"""
    prompt_dir = Path(__file__).parent.parent.parent.parent / "prompts"
    prompt_path = prompt_dir / name
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "{}"