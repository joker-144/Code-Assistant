"""
CLI 入口 — 基于 Typer + Rich
提供 run / chat / review / serve / version 命令
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from dev_agent.config import get_config

app = typer.Typer(
    name="dev-agent",
    help="DevAgent — 多模型协作开发智能体 (DeepSeek-V4-Pro + Qwen-Plus)",
)
console = Console()


def _get_orchestrator():
    """延迟导入编排器"""
    from dev_agent.orchestrator import get_orchestrator
    return get_orchestrator()


@app.command()
def run(
    request: str = typer.Argument(..., help="开发需求描述"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出结果到文件"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="静默模式"),
):
    """
    执行一次开发任务

    示例:
      dev-agent run "用 Python 写一个函数，返回列表的最大值和最小值之差"
      dev-agent run "创建一个 FastAPI 应用，包含 /health 端点"
    """
    # 检查 API Key
    config = get_config()
    missing = config.validate_api_keys()
    if missing:
        console.print(f"[red]错误: 以下 API Key 缺失:[/red]")
        for m in missing:
            console.print(f"  - {m}")
        console.print("\n[yellow]请在 .env 文件中配置 API Key[/yellow]")
        raise typer.Exit(code=1)

    if not quiet:
        config.verbose = True

    orchestrator = _get_orchestrator()

    with console.status("[bold green]执行中...[/bold green]"):
        result = orchestrator.execute(request)

    if json_output:
        console.print(json.dumps(result, ensure_ascii=False, indent=2))
    elif output:
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]结果已写入: {output}[/green]")
    else:
        _print_result(result)


def _print_result(result: dict) -> None:
    """格式化输出执行结果"""
    # 方案概览
    console.print(Panel(
        f"[bold cyan]{result.get('overall_approach', 'N/A')}[/bold cyan]",
        title="执行方案",
        border_style="cyan",
    ))

    # 架构说明
    arch = result.get("architecture_notes", "")
    if arch:
        console.print(Panel(arch, title="架构说明", border_style="blue"))

    # 子任务表
    table = Table(title="子任务执行情况")
    table.add_column("ID", style="dim")
    table.add_column("描述")
    table.add_column("执行者")
    table.add_column("状态")

    for task in result.get("sub_tasks", []):
        status_style = {
            "done": "green",
            "failed": "red",
            "running": "yellow",
            "pending": "dim",
        }.get(task.get("status", ""), "white")

        table.add_row(
            task.get("id", "-"),
            task.get("description", "-")[:60],
            task.get("worker", "-"),
            f"[{status_style}]{task.get('status', '-')}[/{status_style}]",
        )

    console.print(table)

    # 耗时
    console.print(f"\n[dim]耗时: {result.get('duration_seconds', '?')}s[/dim]")


@app.command()
def chat():
    """
    交互式对话模式

    输入开发需求，我来规划并执行
    输入 'exit' 退出 | 'status' 查看状态 | 'help' 帮助
    """
    config = get_config()
    missing = config.validate_api_keys()
    if missing:
        console.print(f"[red]错误: 以下 API Key 缺失:[/red]")
        for m in missing:
            console.print(f"  - {m}")
        console.print("\n[yellow]请在 .env 文件中配置 API Key[/yellow]")
        raise typer.Exit(code=1)

    orchestrator = _get_orchestrator()

    console.print(Panel(
        "[bold]DevAgent 交互模式[/bold]\n"
        "输入开发需求，我来规划并执行\n"
        "输入 [yellow]exit[/yellow] 退出 | [yellow]status[/yellow] 查看状态 | [yellow]help[/yellow] 帮助",
        title="🧠 DevAgent",
        border_style="green",
    ))

    while True:
        try:
            user_input = console.input("\n[bold green]需求> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见![/yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() == "exit":
            console.print("[yellow]再见![/yellow]")
            break
        elif user_input.lower() == "status":
            stats = orchestrator.memory_stats()
            console.print(json.dumps(stats, ensure_ascii=False, indent=2))
            continue
        elif user_input.lower() == "help":
            console.print("""
[bold]可用命令:[/bold]
  [cyan]任意需求[/cyan] — 执行开发任务
  [cyan]exit[/cyan]      — 退出
  [cyan]status[/cyan]    — 查看记忆系统状态
  [cyan]help[/cyan]      — 显示帮助
            """)
            continue

        result = orchestrator.execute(user_input)
        _print_result(result)


@app.command()
def review(
    path: str = typer.Argument(..., help="要审查的文件或目录路径"),
    focus: str = typer.Option("all", "--focus", "-f", help="审查重点: all|security|performance"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON 格式输出"),
):
    """
    审查代码质量

    示例:
      dev-agent review src/services/
      dev-agent review src/main.py --focus security
    """
    orchestrator = _get_orchestrator()

    target = Path(path)
    if target.is_file():
        code = target.read_text(encoding="utf-8")
    elif target.is_dir():
        code_parts = []
        for py_file in target.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                code_parts.append(f"// FILE: {py_file}\n{py_file.read_text(encoding='utf-8')}")
        code = "\n\n".join(code_parts)
    else:
        console.print(f"[red]路径不存在: {path}[/red]")
        raise typer.Exit(code=1)

    with console.status("[bold green]审查中...[/bold green]"):
        result = orchestrator.review_code(code, f"审查 {path} (重点: {focus})")

    if json_output:
        console.print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_review_result(result)


def _print_review_result(result: dict) -> None:
    """格式化输出审查结果"""
    score = result.get("overall_score", "?")
    color = "green" if isinstance(score, int) and score >= 7 else "yellow" if isinstance(score, int) and score >= 5 else "red"
    console.print(f"\n[bold]总评分: [{color}]{score}/10[/{color}][/bold]")

    # 各维度评分
    dims = result.get("dimensions", {})
    if dims:
        table = Table(title="各维度评分")
        table.add_column("维度")
        table.add_column("评分")
        table.add_column("评价")
        for name, detail in dims.items():
            dim_score = detail.get("score", "?") if isinstance(detail, dict) else "?"
            dim_comment = detail.get("comment", "") if isinstance(detail, dict) else ""
            table.add_row(name, str(dim_score), dim_comment[:60])
        console.print(table)

    # 问题列表
    issues = result.get("issues", [])
    if issues:
        console.print("\n[bold]发现的问题:[/bold]")
        for issue in issues:
            severity = issue.get("severity", "info")
            icon = {"error": "🔴", "warning": "🟡", "suggestion": "🔵"}.get(severity, "⚪")
            console.print(f"  {icon} [{severity}] {issue.get('location', '?')}: {issue.get('message', '')}")

    console.print(f"\n[dim]{result.get('summary', '')}[/dim]")


@app.command()
def version():
    """显示版本信息"""
    console.print("""
[bold cyan]DevAgent[/bold cyan] v0.1.0
多模型协作开发智能体

[dim]大脑: DeepSeek-V4-Pro (规划 + 仲裁)[/dim]
[dim]编码: DeepSeek-V4-Pro (代码生成)[/dim]
[dim]审查: Qwen-Plus (代码审查)[/dim]
[dim]记忆: SQLite + Milvus[/dim]
    """)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
):
    """
    启动 API 服务

    示例:
      dev-agent serve
      dev-agent serve --port 9000
    """
    import uvicorn

    console.print(f"[bold green]启动 API 服务: http://{host}:{port}[/bold green]")
    console.print("[dim]API 文档: http://{host}:{port}/docs[/dim]")
    uvicorn.run("dev_agent.api:app", host=host, port=port, reload=True)


def main():
    app()


if __name__ == "__main__":
    main()