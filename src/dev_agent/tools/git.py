"""
Git 版本控制工具 — status / diff / log / commit / branch
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from dev_agent.tools.types import ToolResult


class GitTool:
    """Git 操作工具"""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    async def _run_git(self, *args: str) -> ToolResult:
        """执行 git 命令"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(success=False, error="git 命令超时 (30s)")

            return ToolResult(
                success=proc.returncode == 0,
                data=(stdout + stderr).decode("utf-8", errors="replace"),
                metadata={"exit_code": proc.returncode},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def git_status(self) -> ToolResult:
        """查看 Git 状态"""
        return await self._run_git("status", "--short")

    async def git_diff(self, cached: bool = False) -> ToolResult:
        """查看代码变更"""
        args = ["diff"]
        if cached:
            args.append("--cached")
        return await self._run_git(*args)

    async def git_log(self, count: int = 10) -> ToolResult:
        """查看提交历史"""
        return await self._run_git("log", f"-{count}", "--oneline")

    async def git_branch(self) -> ToolResult:
        """查看分支"""
        return await self._run_git("branch")

    async def git_add(self, path: str = ".") -> ToolResult:
        """添加文件到暂存区"""
        return await self._run_git("add", path)

    async def git_commit(self, message: str) -> ToolResult:
        """提交变更"""
        return await self._run_git("commit", "-m", message)

    async def git_create_branch(self, name: str) -> ToolResult:
        """创建并切换到新分支"""
        return await self._run_git("checkout", "-b", name)
