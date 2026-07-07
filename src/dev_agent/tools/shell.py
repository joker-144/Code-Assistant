"""
Shell 命令执行工具 — run_command

针对 Windows PowerShell 环境适配。
危险命令通过黑名单拦截，超时自动终止。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from dev_agent.tools.types import ToolResult


class ShellTool:
    """Shell 命令执行工具"""

    # 危险命令黑名单（跨平台，匹配时忽略大小写）
    DANGEROUS_COMMANDS = [
        "rm -rf /",
        "rm -rf --no-preserve-root",
        "dd if=",
        "mkfs",
        ":(){ :|:& };:",  # fork bomb
        "> /dev/sda",
        "format c:",
        "del /f /s /q c:",
        "del /f /s /q c:\\",
        "rd /s /q c:",
        "rd /s /q c:\\",
        "rmdir /s /q c:",
        "rmdir /s /q c:\\",
    ]

    def __init__(self, workspace: Path):
        self.workspace = workspace
        # 预构建小写黑名单，避免每次匹配都重新调用 lower()
        self._dangerous_lower = [cmd.lower() for cmd in self.DANGEROUS_COMMANDS]

    async def run_command(self, command: str, timeout: int = 60) -> ToolResult:
        """执行 Shell 命令

        Args:
            command: 要执行的命令
            timeout: 超时秒数
        """
        # 安全检查（大小写不敏感）
        cmd_lower = command.lower()
        # 移除多余空白防止绕过
        cmd_normalized = " ".join(cmd_lower.split())
        for dangerous in self._dangerous_lower:
            if dangerous in cmd_normalized:
                return ToolResult(
                    success=False,
                    error=f"拒绝执行危险命令（匹配: {dangerous}）",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(success=False, error=f"命令超时 ({timeout}s)")

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")

            # 输出截断
            if len(output) > 10000:
                output = output[:10000] + "\n... (输出已截断)"

            return ToolResult(
                success=proc.returncode == 0,
                data=output,
                metadata={"exit_code": proc.returncode},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
