"""
工具引擎 — 注册、schema 生成、执行调度

每个工具定义为标准 OpenAI function calling schema，
LLM 可以在推理过程中自主决定调用哪个工具、传递什么参数。

工具执行流程:
  LLM 返回 tool_calls → ToolEngine.execute() → 查找注册的工具 → 调用 → 返回 ToolResult
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Awaitable

from dev_agent.tools.types import ToolResult
from dev_agent.tools.file_ops import FileOps
from dev_agent.tools.git import GitTool
from dev_agent.tools.search import SearchTool
from dev_agent.tools.shell import ShellTool
from dev_agent.tools.skill_ops import SkillOps


@dataclass
class ToolDef:
    """工具定义 — 函数 + JSON schema"""
    func: Callable[..., Awaitable[ToolResult]]
    schema: dict[str, Any]


class ToolEngine:
    """工具引擎 — 注册、schema 生成、执行调度"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._tools: dict[str, ToolDef] = {}
        self._register_defaults()

    def _register_defaults(self):
        """注册内置工具"""
        file_ops = FileOps(self.workspace)
        shell = ShellTool(self.workspace)
        git = GitTool(self.workspace)
        search = SearchTool(self.workspace)
        skills = SkillOps(self.workspace)

        self.register("read_file", file_ops.read_file, READ_FILE_SCHEMA)
        self.register("write_file", file_ops.write_file, WRITE_FILE_SCHEMA)
        self.register("edit_file", file_ops.edit_file, EDIT_FILE_SCHEMA)
        self.register("list_dir", file_ops.list_dir, LIST_DIR_SCHEMA)

        self.register("search_code", search.search_code, SEARCH_CODE_SCHEMA)

        self.register("run_command", shell.run_command, RUN_COMMAND_SCHEMA)

        self.register("git_status", git.git_status, GIT_STATUS_SCHEMA)
        self.register("git_diff", git.git_diff, GIT_DIFF_SCHEMA)
        self.register("git_log", git.git_log, GIT_LOG_SCHEMA)
        self.register("git_commit", git.git_commit, GIT_COMMIT_SCHEMA)
        self.register("git_branch", git.git_branch, GIT_BRANCH_SCHEMA)
        self.register("git_add", git.git_add, GIT_ADD_SCHEMA)
        self.register("git_create_branch", git.git_create_branch, GIT_CREATE_BRANCH_SCHEMA)

        # 技能管理工具
        self.register("list_skills", skills.list_skills, LIST_SKILLS_SCHEMA)
        self.register("load_skill", skills.load_skill, LOAD_SKILL_SCHEMA)
        self.register("install_skill", skills.install_skill, INSTALL_SKILL_SCHEMA)

    def register(self, name: str, func: Callable[..., Awaitable[ToolResult]], schema: dict[str, Any]):
        """注册工具"""
        self._tools[name] = ToolDef(func=func, schema=schema)

    def get_schemas(self) -> list[dict[str, Any]]:
        """返回所有工具的 JSON schema（供 LLM function calling 使用）"""
        return [t.schema for t in self._tools.values()]

    async def execute(self, tool_call) -> ToolResult:
        """执行 LLM 请求的工具调用

        Args:
            tool_call: 包含 id, name, arguments 的工具调用对象
                       (dev_agent.llm.client.ToolCall 或 OpenAI tool_call 对象)
        """
        name = tool_call.name if hasattr(tool_call, "name") else tool_call.function.name
        arguments = (
            tool_call.arguments
            if hasattr(tool_call, "arguments")
            else json.loads(tool_call.function.arguments)
        )

        if name not in self._tools:
            return ToolResult(success=False, error=f"未知工具: {name}")

        tool = self._tools[name]
        try:
            return await tool.func(**arguments)
        except TypeError as e:
            return ToolResult(success=False, error=f"参数错误: {e}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ── 工具 JSON Schema 定义 ──

READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取指定文件的内容。支持通过行号范围读取部分内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要读取的文件路径（相对 workspace）"},
                "start_line": {"type": "integer", "description": "起始行号（从 1 开始），默认从头读", "default": 0},
                "end_line": {"type": "integer", "description": "结束行号，默认读到末尾", "default": 0},
            },
            "required": ["path"],
        },
    },
}

WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "创建或覆写文件。如果文件已存在会被覆盖，父目录自动创建。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要写入的文件路径（相对 workspace）"},
                "content": {"type": "string", "description": "文件完整内容"},
            },
            "required": ["path", "content"],
        },
    },
}

EDIT_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "通过搜索-替换的方式编辑文件的指定部分。"
            "old_str 必须是文件中唯一匹配的文本片段，否则会报错要求提供更多上下文。"
            "相比 write_file 整文件重写，edit_file 只修改需要改的部分，节省 token 且更安全。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要编辑的文件路径（相对 workspace）"},
                "old_str": {"type": "string", "description": "要替换的原文（必须精确匹配文件中的内容）"},
                "new_str": {"type": "string", "description": "替换后的新文本"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
}

LIST_DIR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "列出指定目录下的文件和子目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径（相对 workspace），默认为根目录", "default": "."},
            },
            "required": [],
        },
    },
}

SEARCH_CODE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_code",
        "description": (
            "在项目代码库中语义搜索相关代码。支持自然语言查询，返回最相关的代码片段。"
            "用于了解项目结构、查找相关实现、定位需要修改的代码。"
            "首次使用前需运行 `dev-agent index` 索引项目。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询（自然语言描述要找的代码）"},
                "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
            },
            "required": ["query"],
        },
    },
}

RUN_COMMAND_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "执行 Shell 命令（Windows 上为 PowerShell/cmd）。用于运行测试、构建、安装依赖等。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {"type": "integer", "description": "超时秒数，默认 60", "default": 60},
            },
            "required": ["command"],
        },
    },
}

GIT_STATUS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_status",
        "description": "查看 Git 工作区状态（哪些文件被修改/新增/删除）。",
        "parameters": {"type": "object", "properties": {}},
    },
}

GIT_DIFF_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_diff",
        "description": "查看代码变更内容（未暂存或已暂存）。",
        "parameters": {
            "type": "object",
            "properties": {
                "cached": {"type": "boolean", "description": "是否查看已暂存的变更", "default": False},
            },
        },
    },
}

GIT_LOG_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_log",
        "description": "查看 Git 提交历史。",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "返回的提交数量", "default": 10},
            },
        },
    },
}

GIT_COMMIT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_commit",
        "description": "提交代码变更。注意：提交前需要先调用 git add（可通过 run_command 执行）。",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "提交信息"},
            },
            "required": ["message"],
        },
    },
}

GIT_BRANCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_branch",
        "description": "查看所有 Git 分支。",
        "parameters": {"type": "object", "properties": {}},
    },
}

GIT_ADD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_add",
        "description": "将文件添加到 Git 暂存区。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要添加的文件路径，默认为当前目录所有变更", "default": "."},
            },
        },
    },
}

GIT_CREATE_BRANCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "git_create_branch",
        "description": "创建并切换到新的 Git 分支。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "新分支名称"},
            },
            "required": ["name"],
        },
    },
}

# ── 技能管理工具 Schema ──

LIST_SKILLS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_skills",
        "description": "列出当前 skills 目录中所有已安装的技能。",
        "parameters": {"type": "object", "properties": {}},
    },
}

LOAD_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": "加载指定技能的详细信息（能力清单、工具列表）。不传 name 则列出所有技能。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称（skills 目录下的子目录名）"},
            },
        },
    },
}

INSTALL_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "install_skill",
        "description": "从 skillhub.cn 安装技能，安装位置为项目 skills/ 目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称（如 self-improving-agent）"},
            },
            "required": ["name"],
        },
    },
}
