"""
工具层 — 文件/Shell/Git 操作
统一 ToolResult 返回格式，所有路径限制在 workspace 内
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class ToolResult:
    """工具操作统一返回格式"""
    success: bool
    data: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)


class FileTool:
    """文件操作工具 — 所有路径自动限制在 workspace 内"""

    DANGEROUS_PATTERNS = ["..", "~", "$", "`"]

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """安全解析路径，防止目录穿越"""
        # 清理路径
        clean = Path(path).as_posix().lstrip("/")
        resolved = (self.workspace / clean).resolve()

        # 确保在 workspace 内
        if not str(resolved).startswith(str(self.workspace)):
            raise ValueError(f"路径越界: {path}")

        return resolved

    def read(self, path: str) -> ToolResult:
        """读取文件内容"""
        try:
            target = self._resolve(path)
            if not target.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}")
            content = target.read_text(encoding="utf-8")
            return ToolResult(success=True, data=content)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def write(self, path: str, content: str) -> ToolResult:
        """写入文件（自动创建父目录）"""
        try:
            target = self._resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(success=True, data=f"已写入: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def list_dir(self, path: str = ".") -> ToolResult:
        """列出目录内容"""
        try:
            target = self._resolve(path)
            if not target.is_dir():
                return ToolResult(success=False, error=f"不是目录: {path}")

            items = []
            for item in sorted(target.iterdir()):
                prefix = "[DIR] " if item.is_dir() else "[FILE]"
                items.append(f"{prefix} {item.name}")

            return ToolResult(success=True, data="\n".join(items))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def exists(self, path: str) -> ToolResult:
        """检查文件/目录是否存在"""
        try:
            target = self._resolve(path)
            exists = target.exists()
            return ToolResult(success=True, data=str(exists))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def snapshot(self, path: str = ".") -> ToolResult:
        """获取项目文件树（排除 __pycache__、.git 等）"""
        try:
            target = self._resolve(path)
            if not target.is_dir():
                return ToolResult(success=False, error=f"不是目录: {path}")

            EXCLUDE = {"__pycache__", ".git", ".venv", "node_modules", ".egg-info", "data"}

            lines = []
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in EXCLUDE]
                level = Path(root).relative_to(target)
                indent = "  " * (len(level.parts))

                if level != Path("."):
                    lines.append(f"{indent[:-2]}📁 {level.name}/")

                for f in sorted(files):
                    if f.endswith((".pyc", ".pyo", ".DS_Store")):
                        continue
                    lines.append(f"{indent}  📄 {f}")

            return ToolResult(success=True, data="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def delete(self, path: str) -> ToolResult:
        """删除文件"""
        try:
            target = self._resolve(path)
            if not target.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}")
            target.unlink()
            return ToolResult(success=True, data=f"已删除: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ShellTool:
    """Shell 命令执行工具"""

    DANGEROUS_COMMANDS = [
        "rm -rf /",
        "rm -rf --no-preserve-root",
        "dd if=",
        "mkfs",
        ":(){ :|:& };:",  # fork bomb
        "> /dev/sda",
        "format c:",
    ]

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def run(self, command: str, timeout: int = 60) -> ToolResult:
        """执行 Shell 命令"""
        # 安全检查
        cmd_lower = command.lower()
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return ToolResult(
                    success=False,
                    error=f"拒绝执行危险命令（匹配: {dangerous}）",
                )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace),
            )

            output = result.stdout
            if result.stderr:
                output += "\n[STDERR]\n" + result.stderr

            # 输出截断
            if len(output) > 10000:
                output = output[:10000] + "\n... (输出已截断)"

            return ToolResult(
                success=result.returncode == 0,
                data=output,
                metadata={"exit_code": result.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"命令超时 ({timeout}s)")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def run_python(self, code: str) -> ToolResult:
        """执行 Python 代码片段"""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp_path = f.name

            try:
                result = subprocess.run(
                    ["python", tmp_path],
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
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GitTool:
    """Git 版本控制工具"""

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

    def status(self) -> ToolResult:
        return self._run_git("status", "--short")

    def diff(self) -> ToolResult:
        return self._run_git("diff")

    def log(self, count: int = 10) -> ToolResult:
        return self._run_git("log", f"-{count}", "--oneline")

    def branch(self) -> ToolResult:
        return self._run_git("branch")

    def add(self, path: str = ".") -> ToolResult:
        return self._run_git("add", path)

    def commit(self, message: str) -> ToolResult:
        return self._run_git("commit", "-m", message)

    def create_branch(self, name: str) -> ToolResult:
        return self._run_git("checkout", "-b", name)


class WebTool:
    """联网工具 — WebSearch/WebFetch"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DevAgent/1.0 (Python Requests)"
        })

    def search(self, query: str, num_results: int = 5) -> ToolResult:
        """搜索网页获取信息"""
        try:
            # 使用 DuckDuckGo 搜索（无需 API Key）
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}

            response = self.session.post(url, data=params, timeout=10)
            response.raise_for_status()

            # 解析结果
            content = response.text
            # 简单提取搜索结果
            results = []
            lines = content.split("\n")
            for line in lines:
                if "<a href=" in line and "uddg=" in line:
                    # 提取链接和标题
                    import re
                    match = re.search(r'href="(.*?)".*?>(.*?)</a>', line)
                    if match:
                        url_part, title = match.groups()
                        title = re.sub(r'<[^>]+>', '', title).strip()
                        if title and url_part:
                            results.append(f"- {title}: {url_part}")

            if not results:
                return ToolResult(success=True, data="未找到相关结果")

            return ToolResult(
                success=True,
                data=f"搜索「{query}」结果：\n" + "\n".join(results[:num_results])
            )
        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {str(e)}")

    def fetch(self, url: str) -> ToolResult:
        """获取网页内容"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            # 提取纯文本内容
            soup = BeautifulSoup(response.text, "html.parser")

            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator="\n", strip=True)
            # 清理空行
            lines = [line for line in text.split("\n") if line.strip()]
            content = "\n".join(lines[:100])  # 限制行数

            return ToolResult(
                success=True,
                data=content if content else "页面内容为空",
                metadata={"url": url, "title": soup.title.string if soup.title else ""}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"获取失败: {str(e)}")


class ToolRegistry:
    """工具注册表 — 统一工具访问入口"""

    def __init__(self, workspace: Path):
        self.file = FileTool(workspace)
        self.shell = ShellTool(workspace)
        self.git = GitTool(workspace)
        self.web = WebTool()

    def get_tools_description(self) -> str:
        """获取工具列表描述（供 LLM 使用）"""
        return """
## 可用工具

### 文件操作 (file)
- file.read("path") → 读取文件内容
- file.write("path", "content") → 写入文件
- file.list_dir("path") → 列出目录
- file.exists("path") → 检查是否存在
- file.snapshot("path") → 获取项目文件树
- file.delete("path") → 删除文件

### Shell 命令 (shell)
- shell.run("command") → 执行命令
- shell.run_python("code") → 执行 Python 片段

### Git 操作 (git)
- git.status() → 查看状态
- git.diff() → 查看差异
- git.log(10) → 查看历史
- git.commit("msg") → 提交变更

### 联网操作 (web)
- web.search("query") → 搜索网页获取信息
- web.fetch("url") → 获取网页内容
"""