"""
手脚层 — 代码审查 Worker
Qwen-Plus 负责代码质量审查、文档生成
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dev_agent.llm_client import LLMClient


class ReviewWorker:
    """代码审查器 — 用 Qwen-Plus 做结构化代码审查"""

    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self.llm = llm_client
        self.prompt_template = prompt_template

    def review_code(self, code: str, task_description: str) -> dict[str, Any]:
        """审查代码，返回结构化评分"""
        prompt = self.prompt_template.format(
            code=code[:10000],  # 截断过长代码
            task_description=task_description,
        )

        messages = [
            {"role": "system", "content": "你是代码审查专家，只输出 JSON 格式的审查结果。"},
            {"role": "user", "content": prompt},
        ]

        try:
            return self.llm.chat_json(messages, temperature=0.1)
        except Exception as e:
            return {
                "overall_score": 0,
                "dimensions": {},
                "issues": [{"severity": "error", "location": "N/A", "message": str(e)}],
                "summary": f"审查失败: {e}",
            }

    def generate_docs(self, code: str) -> str:
        """为代码生成 API 文档"""
        messages = [
            {"role": "system", "content": "你是文档专家，生成清晰完整的 API 文档。"},
            {"role": "user", "content": f"""为以下代码生成 Markdown 格式的 API 文档:

{code}

文档应包含:
1. 模块概述
2. 类和函数列表
3. 每个公共 API 的参数说明、返回值、示例
4. 依赖关系"""},
        ]

        return self.llm.chat(messages, temperature=0.1, max_tokens=4096)

    def generate_pr_description(self, changes: str) -> str:
        """生成 PR 描述"""
        messages = [
            {"role": "system", "content": "你是 PR 描述专家，生成清晰简洁的 PR 描述。"},
            {"role": "user", "content": f"""根据以下变更生成 PR 描述:

{changes}

格式:
## 概述
## 变更内容
## 测试
## 注意事项"""},
        ]

        return self.llm.chat(messages, temperature=0.1, max_tokens=2048)

    def analyze_bug_report(self, error_description: str, traceback: str, code: str) -> dict:
        """分析 Bug 报告，给出诊断"""
        messages = [
            {"role": "system", "content": "你是调试专家，分析 Bug 报告并给出诊断。只输出 JSON 格式。"},
            {"role": "user", "content": f"""错误描述: {error_description}
堆栈跟踪: {traceback}
相关代码: {code[:8000]}

请输出 JSON 格式的诊断结果:
```json
{{
  "root_cause": "根因分析",
  "trigger_condition": "触发条件",
  "fix_suggestion": "修复建议",
  "affected_code": ["文件:行号"],
  "risk": "修复风险: low|medium|high"
}}
```"""},
        ]

        try:
            return self.llm.chat_json(messages, temperature=0.0)
        except Exception as e:
            return {"root_cause": str(e), "fix_suggestion": "诊断失败", "risk": "unknown"}