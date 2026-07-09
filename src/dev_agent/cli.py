"""
CLI 入口 — 基于 Typer + Rich

日常开发场景命令:
  dev-agent chat           交互式对话
  dev-agent review         代码审查
  dev-agent explain        解释代码
  dev-agent fix            修复问题
  dev-agent test           生成单元测试
  dev-agent commit         根据 diff 生成 commit message
  dev-agent hook install   安装 git pre-commit hook
  dev-agent init           首次配置向导
  dev-agent index          索引项目代码库
  dev-agent serve          启动 API 服务
  dev-agent stats          查看可观测性统计
  dev-agent version        显示版本信息
  dev-agent collaborate    多 Agent 协同模式
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

import httpx

from dev_agent import __version__
from dev_agent.config import get_config, reset_config

app = typer.Typer(
    name="dev-agent",
    help=f"DevAgent — AI 编码智能体 (v{__version__})",
    no_args_is_help=False,
)
console = Console()

# ── 共享的 exit code 常量 ──
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_AGENT_ERROR = 2
EXIT_API_ERROR = 3
EXIT_FILE_NOT_FOUND = 4
EXIT_GIT_ERROR = 5

# ── 共享的 JSON 输出标志 ──
_json_output: bool = False


def _get_json_flag() -> bool:
    """获取全局 JSON 输出标志"""
    return _json_output


def _set_json_flag(val: bool):
    global _json_output
    _json_output = val


def _output_result(data: dict, text: str = ""):
    """根据 --json 标志输出结果"""
    if _get_json_flag():
        console.print_json(data=data)
    elif text:
        console.print(Markdown(text))


def _check_config_or_exit():
    """检查配置，缺失时打印引导信息并退出"""
    config = get_config()
    missing = config.validate_api_keys()
    if not missing:
        return config

    console.print("[red]配置不完整:[/red]")
    for m in missing:
        console.print(f"  - {m}")
    console.print()

    has_env = Path(".env").exists()
    if not has_env:
        console.print("[yellow]未找到 .env 文件。运行 [bold]dev-agent init[/bold] 开始首次配置。[/yellow]")
    else:
        console.print("[yellow].env 文件已存在但缺少上述 Key。运行 [bold]dev-agent init[/bold] 重新配置。[/yellow]")

    raise typer.Exit(code=EXIT_CONFIG_ERROR)


async def _run_agent_prompt(user_prompt: str, workspace: Optional[Path] = None) -> str:
    """通用 Agent 执行：发送 prompt 并收集所有文本输出"""
    from dev_agent.agent.loop import create_agent

    ws = workspace or Path.cwd()
    agent = create_agent(workspace=ws)
    chunks = []

    try:
        async for event in agent.run(user_prompt):
            if event.type == "text":
                chunks.append(event.content)
            elif event.type == "error" and not _get_json_flag():
                console.print(f"[red]Agent 错误: {event.content}[/red]")
    except Exception as e:
        if not _get_json_flag():
            console.print(f"[red]执行失败: {e}[/red]")
        raise typer.Exit(code=EXIT_AGENT_ERROR)

    return "\n\n".join(chunks)


def _read_pipe_or_args(file_arg: Optional[str]) -> tuple[str, str]:
    """读取管道输入或文件参数，返回 (content, source_name)

    优先级: 管道 > 文件参数
    """
    # 检测管道输入
    if not sys.stdin.isatty():
        content = sys.stdin.read().strip()
        if content:
            return content, "<stdin>"

    if file_arg:
        fpath = Path(file_arg)
        if not fpath.exists():
            console.print(f"[red]文件不存在: {file_arg}[/red]")
            raise typer.Exit(code=EXIT_FILE_NOT_FOUND)
        try:
            content = fpath.read_text(encoding="utf-8")
            return content, str(fpath)
        except UnicodeDecodeError:
            console.print(f"[red]无法读取文件（可能为二进制）: {file_arg}[/red]")
            raise typer.Exit(code=EXIT_FILE_NOT_FOUND)
        except Exception as e:
            console.print(f"[red]读取文件失败: {e}[/red]")
            raise typer.Exit(code=EXIT_FILE_NOT_FOUND)

    console.print("[red]请通过管道传入内容或指定文件路径[/red]")
    console.print("[dim]用法: dev-agent review <文件路径>  或  cat file.py | dev-agent review[/dim]")
    raise typer.Exit(code=EXIT_FILE_NOT_FOUND)


# ══════════════════════════════════════════════════════════════════
# 命令: init — 首次配置向导
# ══════════════════════════════════════════════════════════════════

PROVIDER_PRESETS = {
    "1": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key_url": "https://platform.deepseek.com/api_keys",
    },
    "2": {
        "name": "Qwen (通义千问)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key_url": "https://dashscope.console.aliyun.com/apiKey",
    },
    "3": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "key_url": "https://platform.openai.com/api-keys",
    },
    "4": {
        "name": "自定义",
        "base_url": "",
        "model": "",
        "key_url": "",
    },
}


@app.command()
def init():
    """首次配置向导 — 选择模型提供商、填入 API Key

    引导你完成 DevAgent 的所有必要配置，生成 .env 文件。

    示例:
      dev-agent init
    """
    console.print(Panel(
        "[bold]欢迎使用 DevAgent v0.5.0[/bold]\n\n"
        "首次使用需要配置 LLM API Key，请按提示操作。\n"
        "所有配置保存在 .env 文件中（不会上传到 git）。",
        title="首次配置向导",
        border_style="green",
    ))

    # ── 步骤 1: 选择对话模型提供商 ──
    table = Table(title="可用的模型提供商")
    table.add_column("序号", style="cyan", width=6)
    table.add_column("提供商", style="green", width=20)
    table.add_column("API Key 获取地址", style="dim")

    for key, preset in PROVIDER_PRESETS.items():
        table.add_row(key, preset["name"], preset["key_url"] if preset["key_url"] else "（手动输入）")

    console.print()
    console.print(table)

    choice = Prompt.ask(
        "\n请选择对话模型提供商",
        choices=["1", "2", "3", "4"],
        default="1",
    )
    preset = PROVIDER_PRESETS[choice]

    if choice == "4":
        base_url = Prompt.ask("  API Base URL", default="https://api.deepseek.com")
        model = Prompt.ask("  模型名称", default="deepseek-chat")
        console.print(f"  [dim]API Key 获取: 请参考你的提供商文档[/dim]")
    else:
        base_url = preset["base_url"]
        model = preset["model"]
        console.print(f"  [dim]获取 API Key: {preset['key_url']}[/dim]")

    api_key = Prompt.ask("  API Key", password=True)

    # ── 步骤 2: Embedding 配置 ──
    console.print()
    console.print("[bold]Embedding 配置[/bold]（用于代码语义搜索 `dev-agent index`）")
    console.print("[dim]支持 OpenAI 兼容的 Embedding API（如智谱 Embedding-3）[/dim]")

    embed_choice = Confirm.ask("是否配置 Embedding？（跳过则无法使用语义搜索）", default=True)
    embed_api_key = ""
    embed_base_url = "https://open.bigmodel.cn/api/paas/v4"
    embed_model = "embedding-3"

    if embed_choice:
        console.print("  [dim]推荐: 智谱 Embedding-3 — https://open.bigmodel.cn/usercenter/apikeys[/dim]")
        embed_api_key = Prompt.ask("  Embedding API Key", default=api_key, password=True)
        embed_base_url = Prompt.ask("  Embedding Base URL", default=embed_base_url)
        embed_model = Prompt.ask("  Embedding 模型", default=embed_model)

    # ── 步骤 3: 写入 .env ──
    console.print()
    overwrite = True
    if Path(".env").exists():
        overwrite = Confirm.ask(".env 已存在，是否覆盖？", default=False)

    if overwrite:
        lines = [
            f"# DevAgent v0.5.0 — 由 `dev-agent init` 生成",
            f"",
            f"LLM_CHAT_API_KEY={api_key}",
            f"LLM_CHAT_BASE_URL={base_url}",
            f"LLM_CHAT_MODEL={model}",
            f"LLM_CHAT_TEMPERATURE=0.3",
            f"LLM_CHAT_MAX_TOKENS=8192",
            f"LLM_CHAT_TIMEOUT=120.0",
            f"LLM_CHAT_STREAMING=true",
            f"LLM_CHAT_MAX_TOOL_ROUNDS=20",
            f"",
        ]
        if embed_api_key:
            lines += [
                f"LLM_EMBEDDING_API_KEY={embed_api_key}",
                f"LLM_EMBEDDING_BASE_URL={embed_base_url}",
                f"LLM_EMBEDDING_MODEL={embed_model}",
                f"LLM_EMBEDDING_DIMENSIONS=1024",
                f"",
            ]
        lines += [
            f"MEMORY_SQLITE_PATH=data/memory.db",
            f"DEV_AGENT_WORKSPACE=.",
            f"DEV_AGENT_MAX_CONTEXT_TOKENS=60000",
            f"DEV_AGENT_SUMMARY_TRIGGER_TOKENS=45000",
            f"",
        ]

        Path(".env").write_text("\n".join(lines), encoding="utf-8")
        reset_config()  # 刷新配置缓存

        console.print()
        console.print(Panel(
            f"[bold green]配置完成![/bold green]\n\n"
            f"对话模型: [cyan]{model}[/cyan]\n"
            f"Embedding:  [cyan]{embed_model if embed_api_key else '未配置'}[/cyan]\n\n"
            f"[bold]下一步:[/bold]\n"
            f"  dev-agent chat         开始交互式对话\n"
            f"  dev-agent review file  审查代码\n"
            f"  dev-agent explain file 解释代码\n"
            f"  dev-agent test file    生成测试\n"
            f"  dev-agent commit       自动生成 commit message",
            title="配置保存成功",
            border_style="green",
        ))
    else:
        console.print("[yellow]已取消，配置未修改[/yellow]")


# ══════════════════════════════════════════════════════════════════
# 命令: chat — 交互式对话
# ══════════════════════════════════════════════════════════════════

@app.command()
def chat(
    prompt: Optional[str] = typer.Argument(None, help="直接传入 prompt（非交互模式）"),
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式输出结果"),
):
    """交互式对话 — 流式输出 Agent 的思考和操作

    不传参数进入交互 REPL 模式，传入参数则直接执行后退出。

    示例:
      dev-agent chat
      dev-agent chat "帮我把 utils.py 中的函数加上类型注解"
      dev-agent chat --json "显示项目的主要模块"
    """
    _set_json_flag(json_output)
    config = _check_config_or_exit()
    _check_for_update_async()

    # 非交互模式
    if prompt:
        result = asyncio.run(_run_agent_prompt(prompt))
        if _get_json_flag():
            console.print_json(data={"status": "ok", "response": result})
        else:
            console.print(Markdown(result))
        return

    # 交互模式
    from dev_agent.agent.loop import create_agent

    agent = create_agent(workspace=Path.cwd())

    console.print(Panel(
        "[bold]DevAgent[/bold] — AI 编码智能体\n"
        "输入需求，Agent 自主完成（读取文件、编辑代码、运行命令）\n"
        "[yellow]/help[/yellow] 查看命令 | [yellow]/clear[/yellow] 清空上下文 | [yellow]/exit[/yellow] 退出",
        title="DevAgent",
        border_style="green",
    ))

    while True:
        try:
            console.print()
            user_input = console.input("[bold green]❯[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见![/yellow]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit"):
                console.print("[yellow]再见![/yellow]")
                break
            elif cmd == "/help":
                _show_help()
                continue
            elif cmd == "/clear":
                _clear_context(agent)
                continue
            elif cmd == "/tokens":
                _show_tokens(agent)
                continue
            elif cmd == "/index":
                _run_index()
                continue
            elif cmd == "/stats":
                _show_stats()
                continue
            else:
                console.print(f"[red]未知命令: {user_input}[/red]  (输入 /help 查看可用命令)")
                continue

        asyncio.run(_run_agent_loop(agent, user_input))


# ══════════════════════════════════════════════════════════════════
# 命令: review — 代码审查
# ══════════════════════════════════════════════════════════════════

@app.command()
def review(
    file: Optional[str] = typer.Argument(None, help="要审查的文件路径"),
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式输出结果"),
):
    """代码审查 — 对指定文件或 git diff 做全面的代码审查

    支持管道输入和文件路径两种方式。

    示例:
      dev-agent review src/main.py
      git diff | dev-agent review
      cat utils.py | dev-agent review --json
    """
    _set_json_flag(json_output)
    _check_config_or_exit()

    content, source = _read_pipe_or_args(file)

    # 如果是 git diff 输入（包含 @@ 标记），使用 diff 审查 prompt
    if "@@" in content and ("---" in content or "+++" in content):
        review_prompt = (
            "请对以下 git diff 进行全面的代码审查，输出结构化的审查报告。\n"
            "请关注以下方面:\n"
            "  - 逻辑正确性 (bug、边界条件、空值处理)\n"
            "  - 安全隐患 (注入、敏感信息泄露、权限)\n"
            "  - 性能问题 (不必要的循环、内存占用、N+1 查询)\n"
            "  - 代码风格 (命名、注释、一致性)\n"
            "  - 可维护性 (耦合度、函数长度、测试可行性)\n\n"
            "请按严重程度分类（致命/警告/建议），给出具体文件和行号，并提供改进建议。\n\n"
            f"Git Diff:\n```diff\n{content[:15000]}\n```"
        )
    else:
        review_prompt = (
            "请对以下代码进行全面的代码审查，输出结构化的审查报告。\n"
            "请关注: 逻辑正确性、安全隐患、性能问题、代码风格、可维护性。\n"
            "按严重程度分类（致命/警告/建议），给出具体行号和修复建议。\n\n"
            f"文件: {source}\n```\n{content[:12000]}\n```"
        )

    with console.status("[cyan]正在审查代码...[/cyan]"):
        result = asyncio.run(_run_agent_prompt(review_prompt))

    _output_result(data={"status": "ok", "source": source, "review": result}, text=result)


# ══════════════════════════════════════════════════════════════════
# 命令: explain — 解释代码
# ══════════════════════════════════════════════════════════════════

@app.command()
def explain(
    file: Optional[str] = typer.Argument(None, help="要解释的文件路径"),
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式输出结果"),
):
    """解释代码逻辑 — 用通俗语言解释代码在做什么

    支持管道输入和文件路径两种方式。

    示例:
      dev-agent explain src/complex_algorithm.py
      cat mystery.py | dev-agent explain
      dev-agent explain --json utils.py
    """
    _set_json_flag(json_output)
    _check_config_or_exit()

    content, source = _read_pipe_or_args(file)

    explain_prompt = (
        "请用通俗易懂的语言解释以下代码的功能和逻辑:\n\n"
        "1. 先一句话概括这段代码的用途\n"
        "2. 分段解释核心逻辑和数据流\n"
        "3. 指出关键函数/类的职责\n"
        "4. 如有设计模式或算法，请说明\n\n"
        f"文件: {source}\n```\n{content[:12000]}\n```"
    )

    with console.status("[cyan]正在分析代码...[/cyan]"):
        result = asyncio.run(_run_agent_prompt(explain_prompt))

    _output_result(data={"status": "ok", "source": source, "explanation": result}, text=result)


# ══════════════════════════════════════════════════════════════════
# 命令: fix — 修复代码
# ══════════════════════════════════════════════════════════════════

@app.command()
def fix(
    file: Optional[str] = typer.Argument(None, help="要修复的文件路径"),
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式输出结果"),
):
    """修复代码问题 — 分析并修复 bug、lint 错误、代码异味

    支持管道输入和文件路径两种方式。
    Agent 会直接编辑源文件（通过 edit_file）。

    示例:
      dev-agent fix src/broken.py
      cat buggy.py | dev-agent fix
    """
    _set_json_flag(json_output)
    _check_config_or_exit()

    content, source = _read_pipe_or_args(file)
    is_from_file = file and Path(file).exists()

    if is_from_file:
        fix_prompt = (
            "请分析以下文件中的问题并直接通过 edit_file 修复它们。\n"
            "检查: 语法错误、逻辑 bug、lint 警告、代码异味、安全问题、性能瓶颈。\n\n"
            f"文件: {source}\n```\n{content[:12000]}\n```\n\n"
            "请使用 edit_file 工具逐一修复发现的问题，一次改一个问题。"
        )
    else:
        fix_prompt = (
            "请分析以下代码中的问题并输出修复建议和修复后的代码。\n"
            "检查: 语法错误、逻辑 bug、lint 警告、代码异味、安全问题。\n\n"
            f"来源: {source}\n```\n{content[:12000]}\n```\n\n"
            "请逐一列出问题和对应的修复代码。"
        )

    with console.status("[cyan]正在分析和修复...[/cyan]"):
        result = asyncio.run(_run_agent_prompt(fix_prompt))

    _output_result(data={"status": "ok", "source": source, "fix": result}, text=result)


# ══════════════════════════════════════════════════════════════════
# 命令: test — 生成单元测试
# ══════════════════════════════════════════════════════════════════

@app.command()
def test(
    file: Optional[str] = typer.Argument(None, help="要生成测试的源文件路径"),
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式输出结果"),
):
    """生成单元测试 — 为指定代码生成 pytest 单元测试

    Agent 会分析代码逻辑并自动写入测试文件（{name}_test.py）。

    示例:
      dev-agent test src/utils.py
      cat calculator.py | dev-agent test --json
    """
    _set_json_flag(json_output)
    _check_config_or_exit()

    content, source = _read_pipe_or_args(file)

    test_prompt = (
        "请为以下代码生成完整的 pytest 单元测试。要求:\n\n"
        "1. 覆盖主要功能和边界条件\n"
        "2. 包含正常路径、异常路径、边界值测试\n"
        "3. 使用 pytest 框架（import pytest）\n"
        "4. 测试函数命名清晰（test_<功能>_<场景>）\n"
        "5. 如有外部依赖（数据库、API），使用 mock\n"
        "6. 使用 write_file 将测试写入新文件\n\n"
        f"文件: {source}\n```\n{content[:12000]}\n```"
    )

    with console.status("[cyan]正在生成测试...[/cyan]"):
        result = asyncio.run(_run_agent_prompt(test_prompt))

    _output_result(data={"status": "ok", "source": source, "tests": result}, text=result)


# ══════════════════════════════════════════════════════════════════
# 命令: commit — 自动生成 commit message
# ══════════════════════════════════════════════════════════════════

@app.command()
def commit(
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
    """自动生成 commit message — 分析 git diff 生成规范的提交信息

    遵循 Conventional Commits 规范 (feat/fix/refactor/...)

    示例:
      dev-agent commit
      dev-agent commit --json
    """
    _set_json_flag(json_output)
    _check_config_or_exit()

    # 获取 staged + unstaged diff
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, timeout=10,
        )
        unstaged = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        console.print("[red]未找到 git，请在 git 仓库中运行此命令[/red]")
        raise typer.Exit(code=EXIT_GIT_ERROR)

    stat_text = staged.stdout.strip() or unstaged.stdout.strip()
    if not stat_text:
        console.print("[yellow]没有待提交的变更[/yellow]")
        raise typer.Exit(code=EXIT_OK)

    # 获取详细 diff
    full_diff = ""
    if staged.stdout.strip():
        diff_result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=10,
        )
        full_diff = diff_result.stdout
        scope = "staged"
    else:
        diff_result = subprocess.run(
            ["git", "diff"],
            capture_output=True, text=True, timeout=10,
        )
        full_diff = diff_result.stdout
        scope = "unstaged"

    if not full_diff.strip():
        console.print("[yellow]没有 diff 内容[/yellow]")
        raise typer.Exit(code=EXIT_OK)

    commit_prompt = (
        "请根据以下 git diff 生成一条规范的 commit message。\n\n"
        "要求:\n"
        "1. 遵循 Conventional Commits 规范 (feat/fix/refactor/docs/test/chore/...)\n"
        "2. 标题不超过 72 字符，简洁描述核心变更\n"
        "3. 正文列出关键变更点（每条一行，- 开头）\n"
        "4. 中文输出，一行标题 + 空行 + 正文列表\n\n"
        f"变更统计:\n{stat_text}\n\n"
        f"详细 diff:\n```diff\n{full_diff[:10000]}\n```"
    )

    with console.status("[cyan]正在分析变更...[/cyan]"):
        result = asyncio.run(_run_agent_prompt(commit_prompt))

    # 提取第一行作为 title
    lines = result.strip().split("\n")
    title = lines[0] if lines else ""

    if _get_json_flag():
        console.print_json(data={
            "status": "ok",
            "scope": scope,
            "message": result.strip(),
            "title": title,
        })
    else:
        console.print(Panel(
            result.strip(),
            title=f"建议的 Commit Message ({scope})",
            border_style="cyan",
        ))
        console.print()
        console.print("[dim]复制以上信息，使用 git commit -m \"...\" 提交[/dim]")


# ══════════════════════════════════════════════════════════════════
# 命令: hook — Git Hook 管理
# ══════════════════════════════════════════════════════════════════

@app.command(name="hook")
def hook_install():
    """安装 git pre-commit hook — 提交前自动审查代码变更

    安装后每次 git commit 前自动运行代码审查，发现致命问题将阻止提交。

    示例:
      dev-agent hook install
    """
    git_dir = Path(".git")
    if not git_dir.exists():
        console.print("[red]当前目录不是 git 仓库，请在项目根目录运行[/red]")
        raise typer.Exit(code=EXIT_GIT_ERROR)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit_path = hooks_dir / "pre-commit"
    if pre_commit_path.exists():
        overwrite = Confirm.ask("pre-commit hook 已存在，是否覆盖？", default=False)
        if not overwrite:
            console.print("[yellow]已取消[/yellow]")
            return

    hook_script = '''#!/bin/sh
# DevAgent Pre-commit Hook — 在提交前自动审查代码变更
# 安装: dev-agent hook install
# 卸载: rm .git/hooks/pre-commit

echo "[DevAgent] 正在审查代码变更..."
echo ""

# 检查 .env 是否存在
if [ ! -f .env ]; then
    echo "[DevAgent] WARNING: .env 文件不存在，跳过审查"
    echo "[DevAgent] 请先运行 dev-agent init 完成配置"
    exit 0
fi

# 运行审查
dev-agent review --json < /dev/null > /tmp/devagent_review.json 2>/dev/null

if [ $? -ne 0 ]; then
    echo "[DevAgent] WARNING: 审查命令执行失败，跳过审查"
    exit 0
fi

# 检查 JSON 中是否有致命问题（简化版：检查输出是否包含 "fatal"）
FATAL_COUNT=$(python3 -c "
import json
try:
    with open('/tmp/devagent_review.json') as f:
        data = json.load(f)
    review = data.get('review', '')
    print(review.lower().count('fatal'))
except: print(0)
" 2>/dev/null)

if [ "$FATAL_COUNT" -gt 0 ]; then
    echo "[DevAgent] 发现 ${FATAL_COUNT} 个致命问题！"
    echo "[DevAgent] 请修复后再提交，或使用 git commit --no-verify 跳过"
    exit 1
else
    echo "[DevAgent] 审查通过，允许提交"
fi
'''

    pre_commit_path.write_text(hook_script, encoding="utf-8")
    # Unix 需要可执行权限，Windows 下 git bash 也能识别
    if os.name != "nt":
        os.chmod(pre_commit_path, 0o755)

    console.print(Panel(
        "[bold green]Pre-commit hook 已安装[/bold green]\n\n"
        f"路径: [cyan]{pre_commit_path}[/cyan]\n\n"
        "每次 git commit 前会自动审查代码变更\n"
        "检测到致命问题将阻止提交\n\n"
        "[dim]跳过审查: git commit --no-verify[/dim]\n"
        "[dim]卸载 hook: rm .git/hooks/pre-commit[/dim]",
        title="Git Hook",
        border_style="green",
    ))


# ══════════════════════════════════════════════════════════════════
# 现有命令: version / index / collaborate / serve / stats
# ══════════════════════════════════════════════════════════════════

@app.command()
def version():
    """显示版本信息，并与 PyPI 最新版本对比"""
    from dev_agent import __version__

    # 检查远程版本
    remote_info = ""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get("https://pypi.org/pypi/dev-agent/json")
            if resp.status_code == 200:
                latest = resp.json()["info"]["version"]
                if latest != __version__:
                    remote_info = f"\n[yellow]新版本可用: [bold]{latest}[/bold] （当前 {__version__}）[/yellow]\n[dim]运行 [bold]dev-agent update[/bold] 升级[/dim]"
                else:
                    remote_info = f"\n[dim]已是最新版本 ({__version__})[/dim]"
    except Exception:
        remote_info = "\n[dim]无法检查远程版本[/dim]"

    console.print(f"""
[bold cyan]DevAgent[/bold cyan] v{__version__}
AI 编码智能体 — 多 Agent 协同 + 反思机制 + 弹性工程 (2026 标准)
{remote_info}
[dim]模型: 单模型 + Provider 可切换 (OpenAI 兼容)[/dim]
[dim]工具: read_file / write_file / edit_file / search_code / run_command / git[/dim]
[dim]核心: Agentic Loop + 多 Agent 协同编排 (Supervisor-Worker)[/dim]
[dim]记忆: SQLite + 向量 Embedding + 知识图谱 + 长期经验检索[/dim]
[dim]反思: 工具执行后自动反思，失败自动修正 (ReflectionEngine)[/dim]
[dim]弹性: 指数退避重试 + 断路器保护 + 可观测性监控[/dim]
[dim]协议: MCP 标准化工具协议支持[/dim]
[dim]接口: CLI 交互式 REPL + Web SSE 流式 API[/dim]
    """)


@app.command()
def update():
    """自动升级到最新版本 — 检查 PyPI 并使用 pip 升级

    示例:
      dev-agent update
    """
    from dev_agent import __version__

    console.print(f"[bold cyan]DevAgent v{__version__}[/bold cyan]")

    # 检查远程版本
    with console.status("[cyan]正在检查 PyPI 最新版本...[/cyan]"):
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get("https://pypi.org/pypi/dev-agent/json")
                if resp.status_code != 200:
                    console.print("[red]无法访问 PyPI[/red]")
                    raise typer.Exit(code=EXIT_API_ERROR)
                data = resp.json()
                latest = data["info"]["version"]
        except httpx.HTTPError:
            console.print("[red]网络错误，无法检查更新[/red]")
            raise typer.Exit(code=EXIT_API_ERROR)

    if latest == __version__:
        console.print(f"[green]已是最新版本 ({__version__})[/green]")
        return

    console.print(f"\n[yellow]发现新版本: [bold]{latest}[/bold]（当前 {__version__}）[/yellow]")

    # 显示简要 changelog
    try:
        release = data.get("urls", [])
        if release:
            console.print(f"[dim]发布文件: {release[0].get('filename', 'N/A')} ({release[0].get('size', 0) / 1024:.0f} KB)[/dim]")
    except Exception:
        pass

    confirmed = Confirm.ask(f"\n是否升级到 v{latest}？", default=True)
    if not confirmed:
        console.print("[yellow]已取消[/yellow]")
        return

    console.print()
    with console.status(f"[bold cyan]正在升级到 v{latest}...[/bold cyan]"):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "dev-agent"],
            capture_output=True, text=True,
        )

    if result.returncode == 0:
        console.print(f"[bold green]升级成功![/bold green] DevAgent v{latest}")
        console.print("[dim]重新运行 dev-agent version 验证新版本[/dim]")
    else:
        console.print(f"[red]升级失败:[/red]")
        console.print(result.stderr.strip()[-500:])
        raise typer.Exit(code=EXIT_AGENT_ERROR)


@app.command()
def index(
    force: bool = typer.Option(False, "--force", help="强制重新索引（忽略 hash 跳过）"),
):
    """索引项目代码库（用于 search_code 语义搜索）"""
    _check_config_or_exit()

    from dev_agent.context.index import ProjectIndex

    console.print("[bold cyan]开始索引项目代码库...[/bold cyan] [dim](智谱云端 Embedding-3)[/dim]")
    console.print(f"[dim]工作区: {Path.cwd()}[/dim]")

    try:
        project_index = ProjectIndex(Path.cwd())
        with console.status("[cyan]索引中（调用智谱云端 API）...[/cyan]"):
            stats = project_index.index_project(force=force)

        console.print(Panel(
            f"[bold green]索引完成[/bold green]\n\n"
            f"  索引文件: [cyan]{stats['files']}[/cyan]\n"
            f"  代码块:   [cyan]{stats['chunks']}[/cyan]\n"
            f"  跳过未改: [dim]{stats['skipped']}[/dim]",
            title="索引统计",
            border_style="green",
        ))
    except Exception as e:
        console.print(f"[red]索引失败: {e}[/red]")
        raise typer.Exit(code=EXIT_API_ERROR)


@app.command()
def collaborate():
    """多 Agent 协同模式 — 主管-员工协作"""
    _check_config_or_exit()
    _check_for_update_async()

    from dev_agent.agents.orchestrator import create_orchestrator

    orchestrator = create_orchestrator(workspace=Path.cwd())

    console.print(Panel(
        "[bold]DevAgent — 多 Agent 协同模式[/bold]\n"
        "输入需求，主管 Agent 自动判断是否需要多 Agent 协作\n"
        "[yellow]/help[/yellow] 查看命令 | [yellow]/exit[/yellow] 退出",
        title="Multi-Agent",
        border_style="magenta",
    ))

    while True:
        try:
            console.print()
            user_input = console.input("[bold magenta]❯[/bold magenta] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见![/yellow]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit"):
                console.print("[yellow]再见![/yellow]")
                break
            elif cmd == "/help":
                _show_help()
                continue
            elif cmd == "/clear":
                console.print("[green]多 Agent 模式暂不支持清空上下文[/green]")
                continue
            else:
                console.print(f"[red]未知命令: {user_input}[/red]")
                continue

        asyncio.run(_run_collaboration(orchestrator, user_input))


@app.command()
def stats():
    """查看可观测性统计 — Token 用量、工具调用、错误率"""
    try:
        from dev_agent.core.observability import get_observability

        obs = get_observability()
        global_stats = obs.get_global_stats()
        recent_tools = obs.get_recent_tool_calls(limit=10)

        console.print(Panel(
            f"[bold]可观测性统计[/bold]\n\n"
            f"追踪记录:  [cyan]{global_stats['total_traces']}[/cyan]\n"
            f"工具调用:  [cyan]{global_stats['total_tool_calls']}[/cyan]\n"
            f"工具成功率: [cyan]{global_stats['tool_success_rate']}%[/cyan]\n"
            f"活跃会话:  [cyan]{global_stats['active_sessions']}[/cyan]",
            title="Observability",
            border_style="cyan",
        ))

        if recent_tools:
            console.print("\n[bold]最近工具调用:[/bold]")
            for t in recent_tools[:5]:
                status = "[green]✓[/green]" if t["success"] else "[red]✗[/red]"
                console.print(f"  {status} {t['tool']} ({t['duration_ms']}ms)")

    except Exception as e:
        console.print(f"[red]获取统计失败: {e}[/red]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
):
    """启动 API 服务（不打开浏览器，适合后端部署）

    port=0 时自动分配可用端口，并在 stdout 输出 PORT:<port> 供前端解析。
    """
    import socket
    import uvicorn

    actual_port = port
    if port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            actual_port = s.getsockname()[1]

    # 首行输出机器可读的端口号（Electron 前端依赖此格式）
    print(f"PORT:{actual_port}", flush=True)
    uvicorn.run("dev_agent.api:app", host=host, port=actual_port, reload=True)


@app.command()
def desktop():
    """启动桌面端 — 优先 Electron 原生窗口，回退浏览器

    检测 Electron 打包产物，找到则启动原生窗口（无浏览器外框），
    否则回退到浏览器 + 系统托盘模式。

    示例:
      dev-agent desktop
    """
    from dev_agent.desktop import launch_desktop

    console.print("[bold cyan]启动 DevAgent 桌面端...[/bold cyan]")
    launch_desktop()


# ══════════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════════

def _show_help():
    """显示帮助"""
    console.print(Panel(
        "[bold]可用命令:[/bold]\n\n"
        "[cyan]/help[/cyan]     显示帮助\n"
        "[cyan]/clear[/cyan]    清空当前对话上下文\n"
        "[cyan]/tokens[/cyan]   查看当前 token 使用情况\n"
        "[cyan]/index[/cyan]    索引项目代码库（用于 search_code）\n"
        "[cyan]/stats[/cyan]    查看记忆系统统计\n"
        "[cyan]/exit[/cyan]     退出\n\n"
        "[bold]使用方式:[/bold]\n"
        "直接输入需求，Agent 自主完成开发任务",
        title="帮助",
        border_style="cyan",
    ))


def _check_for_update_async():
    """非阻塞检查新版本，有更新时打印提示

    仅在交互模式启动时调用（chat / collaborate），静默运行不阻塞用户。
    """
    import threading

    from dev_agent import __version__

    def _check():
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get("https://pypi.org/pypi/dev-agent/json")
                if resp.status_code != 200:
                    return
                latest = resp.json()["info"]["version"]
                if latest != __version__:
                    console.print(
                        f"\n[yellow]DevAgent {latest} 可用（当前 {__version__}）— "
                        f"运行 [bold]dev-agent update[/bold] 升级[/yellow]"
                    )
        except Exception:
            pass  # 静默失败，不打扰用户

    t = threading.Thread(target=_check, daemon=True)
    t.start()


def _clear_context(agent):
    """清空对话上下文"""
    from dev_agent.context.manager import ContextManager
    from dev_agent.agent.system_prompt import get_system_prompt

    agent.context = ContextManager(
        workspace=agent.workspace,
        system_prompt=get_system_prompt(),
    )
    console.print("[green]已清空对话上下文[/green]")


def _show_tokens(agent):
    """显示 token 使用"""
    tokens = agent.context.token_count()
    config = get_config()
    max_tokens = config.max_context_tokens
    percentage = (tokens / max_tokens) * 100 if max_tokens > 0 else 0

    color = "green" if percentage < 70 else "yellow" if percentage < 90 else "red"
    console.print(Panel(
        f"当前上下文 token: [cyan]{tokens:,}[/cyan] / {max_tokens:,}\n"
        f"使用率: [{color}]{percentage:.1f}%[/]",
        title="Token 使用",
        border_style="cyan",
    ))


def _run_index():
    """触发项目索引"""
    from dev_agent.context.index import ProjectIndex

    console.print("[bold cyan]开始索引项目代码库...[/bold cyan] [dim](智谱云端 Embedding-3)[/dim]")
    try:
        project_index = ProjectIndex(Path.cwd())
        with console.status("[cyan]索引中（调用智谱云端 API）...[/cyan]"):
            stats = project_index.index_project()

        console.print(Panel(
            f"[bold green]索引完成[/bold green]\n\n"
            f"  索引文件: [cyan]{stats['files']}[/cyan]\n"
            f"  代码块:   [cyan]{stats['chunks']}[/cyan]\n"
            f"  跳过未改: [dim]{stats['skipped']}[/dim]",
            title="索引统计",
            border_style="green",
        ))
    except Exception as e:
        console.print(f"[red]索引失败: {e}[/red]")


def _show_stats():
    """显示记忆系统统计"""
    from dev_agent.memory.store import get_store

    try:
        store = get_store()
        stats = store.stats()

        console.print(Panel(
            f"对话会话:  [cyan]{stats['conversations']}[/cyan]\n"
            f"消息数量:  [cyan]{stats['messages']}[/cyan]\n"
            f"代码块:    [cyan]{stats['file_chunks']}[/cyan]\n"
            f"经验教训:  [cyan]{stats['lessons']}[/cyan]\n"
            f"数据库:    [dim]{stats['db_path']}[/dim]",
            title="记忆系统统计",
            border_style="cyan",
        ))
    except Exception as e:
        console.print(f"[red]获取统计失败: {e}[/red]")


async def _run_agent_loop(agent, user_input: str):
    """运行 Agent 并流式输出"""
    try:
        async for event in agent.run(user_input):
            if event.type == "tool_start":
                console.print(f"[dim cyan]⚙ {event.content}[/dim cyan]")
            elif event.type == "tool_result":
                result_text = event.content
                if len(result_text) > 500:
                    result_text = result_text[:500] + " ..."
                console.print(f"[dim]  ↳ {result_text}[/dim]")
            elif event.type == "text":
                console.print()
                console.print(Markdown(event.content))
            elif event.type == "error":
                console.print(f"[red]错误: {event.content}[/red]")
            elif event.type == "done":
                pass
    except Exception as e:
        console.print(f"[red]执行失败: {e}[/red]")


async def _run_collaboration(orchestrator, user_input: str):
    """运行多 Agent 协同并流式输出"""
    try:
        async for event in orchestrator.collaborate(user_input):
            if event.type == "task_created":
                console.print(f"[dim yellow]📋 {event.content}[/dim yellow]")
            elif event.type == "worker_start":
                console.print(f"[cyan]🤖 [{event.role}] {event.content}[/cyan]")
            elif event.type == "worker_done":
                if event.content:
                    text = event.content[:300] + (" ..." if len(event.content) > 300 else "")
                    console.print(f"[dim green]  ↳ [{event.role}] {text}[/dim green]")
            elif event.type == "reflection":
                console.print(f"[magenta]🔄 {event.content}[/magenta]")
            elif event.type == "text":
                console.print()
                console.print(Markdown(event.content))
            elif event.type == "done":
                console.print("[green]协同完成[/green]")
    except Exception as e:
        console.print(f"[red]协同执行失败: {e}[/red]")


def main():
    app()


if __name__ == "__main__":
    main()
