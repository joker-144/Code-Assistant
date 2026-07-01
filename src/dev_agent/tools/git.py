"""
Git 版本控制工具 — status / diff / log / commit / branch
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from dev_agent.tools.engine import ToolResult


class GitTool:
    """Git 操作工具"""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def _run_git(self, *args: str) -> ToolResult:
        """执行 git 命令"""
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.workspace),
            )
            return ToolResult(
                success=result.returncode == 0,
                data=result.stdout or result.stderr,
                metadata={"exit_code": result.returncode},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def git_status(self) -> ToolResult:
        """查看 Git 状态"""
        return self._run_git("status", "--short")

    async def git_diff(self, cached: bool = False) -> ToolResult:
        """查看代码变更"""
        args = ["diff"]
        if cached:
            args.append("--cached")
        return self._run_git(*args)

    async def git_log(self, count: int = 10) -> ToolResult:
        """查看提交历史"""
        return self._run_git("log", f"-{count}", "--oneline")

    async def git_branch(self) -> ToolResult:
        """查看分支"""
        return self._run_git("branch")

    async def git_add(self, path: str = ".") -> ToolResult:
        """添加文件到暂存区"""
        return self._run_git("add", path)

    async def git_commit(self, message: str) -> ToolResult:
        """提交变更"""
        return self._run_git("commit", "-m", message)

    async def git_create_branch(self, name: str) -> ToolResult:
        """创建并切换到新分支"""
        return self._run_git("checkout", "-b", name)
