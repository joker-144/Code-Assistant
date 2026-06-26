"""
手脚层 — 代码生成 Worker
DeepSeek-V4-Pro 根据规格编写高质量代码
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from dev_agent.llm_client import LLMClient
from dev_agent.tools.tool_system import ToolRegistry


class CodeWorker:
    """代码生成器 — 用 DeepSeek-V4-Pro 编写代码"""

    def __init__(
        self,
        llm_client: LLMClient,
        tools: ToolRegistry,
        prompt_template: str,
    ):
        self.llm = llm_client
        self.tools = tools
        self.prompt_template = prompt_template

    def generate_code(
        self,
        task_description: str,
        context: str = "",
        existing_files: str = "",
        constraints: str = "",
    ) -> str:
        """根据任务描述生成代码"""
        prompt = self.prompt_template.format(
            context=context or "无",
            existing_files=existing_files or "无已有文件",
            task_description=task_description,
            constraints=constraints or "无额外约束",
        )

        messages = [
            {"role": "system", "content": "你是一位资深软件工程师，编写高质量的生产级代码。直接输出代码，不要解释。"},
            {"role": "user", "content": prompt},
        ]

        return self.llm.chat(messages, temperature=0.3, max_tokens=8192)

    def fix_code(self, original_code: str, feedback: str) -> str:
        """根据审查反馈修复代码"""
        messages = [
            {"role": "system", "content": "你是代码修复专家，根据反馈精准修改代码。只输出修复后的完整代码。"},
            {"role": "user", "content": f"""原始代码:
{original_code}

审查反馈:
{feedback}

请输出修复后的完整代码，保持原有文件结构。"""},
        ]

        return self.llm.chat(messages, temperature=0.2, max_tokens=8192)

    def generate_tests(self, source_code: str) -> str:
        """为源代码生成单元测试"""
        messages = [
            {"role": "system", "content": "你是测试专家，编写全面的单元测试。只输出测试代码。"},
            {"role": "user", "content": f"""为以下代码生成 pytest 单元测试:

{source_code}

要求:
1. 覆盖正常路径和边界条件
2. 包含异常情况测试
3. 使用 pytest 框架
4. 测试函数命名清晰"""},
        ]

        return self.llm.chat(messages, temperature=0.2, max_tokens=4096)

    # ── 辅助方法 ──

    @staticmethod
    def parse_multi_file(output: str) -> dict[str, str]:
        """解析多文件输出，返回 {文件路径: 文件内容}"""
        files = {}
        pattern = re.compile(r"//\s*FILE:\s*(.+?)\n(.*?)(?=\n//\s*FILE:|\Z)", re.DOTALL)
        matches = pattern.findall(output)

        if matches:
            for filepath, content in matches:
                files[filepath.strip()] = content.strip()
        else:
            # 没有多文件标记，整个输出作为单个文件
            files["output.py"] = output.strip()

        return files

    @staticmethod
    def extract_code(text: str) -> str:
        """从 LLM 回复中提取代码（处理有无 markdown 包裹的情况）"""
        text = text.strip()

        # 尝试提取 ``` 代码块
        match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取 ``` 代码块（无语言标记）
        match = re.search(r"```\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return text