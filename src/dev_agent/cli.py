"""
CLI 入口 — 基于 Typer + Rich
交互式 REPL + 流式输出 Agent 的思考和工具调用

支持的命令:
  /help       显示帮助
  /clear      清空当前对话上下文
  /tokens     查看当前 token 使用情况
  /index      索引项目代码库
  /stats      查看记忆系统统计
  /exit       退出

多行输入: Shift+Enter 换行，Enter 发送
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from dev_agent.config import get_config

app = typer.Typer(
    name="dev-agent",
    help="DevAgent — AI 编码智能体 (Agent + 工具集)",
)
console = Console()


@app.command()
def chat():
    """
    交互式对话 — 流式输出 Agent 的思考和操作

    输入需求，Agent 自主完成（读取文件、编辑代码、运行命令等）
    输入 /exit 退出 | /help 查看命令 | /clear 清空上下文
    """
    config = get_config()
    missing = config.validate_api_keys()
    if missing:
        console.print(f"[red]错误: 以下 API Key 缺失:[/red]")
        for m in missing:
            console.print(f"  - {m}")
        console.print("\n[yellow]请在 .env 文件中配置 API Key[/yellow]")
        raise typer.Exit(code=1)

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
            # 使用 Prompt 获取输入，支持 / 命令
            console.print()
            user_input = console.input("[bold green]❯[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见![/yellow]")
            break

        if not user_input:
            continue

        # 处理斜杠命令
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

        # 运行 Agent 循环
        asyncio.run(_run_agent(agent, user_input))


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


async def _run_agent(agent, user_input: str):
    """运行 Agent 并流式输出"""
    try:
        async for event in agent.run(user_input):
            if event.type == "tool_start":
                console.print(f"[dim cyan]⚙ {event.content}[/dim cyan]")
            elif event.type == "tool_result":
                # 工具结果以可折叠的暗色文本展示
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
                pass  # 循环正常结束
    except Exception as e:
        console.print(f"[red]执行失败: {e}[/red]")


@app.command()
def index(
    force: bool = typer.Option(False, "--force", help="强制重新索引（忽略 hash 跳过）"),
):
    """
    索引项目代码库（用于 search_code 语义搜索）

    首次使用 search_code 前需运行此命令。
    后续会增量索引，仅处理修改过的文件。

    示例:
      dev-agent index
      dev-agent index --force
    """
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
        console.print(
            "[dim]现在可以在对话中使用 search_code 工具进行语义搜索了[/dim]"
        )
    except Exception as e:
        console.print(f"[red]索引失败: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def version():
    """显示版本信息"""
    console.print("""
[bold cyan]DevAgent[/bold cyan] v0.4.0
AI 编码智能体 — Agent + 工具集范式

[dim]模型: 单模型 + Provider 可切换 (OpenAI 兼容)[/dim]
[dim]工具: read_file / write_file / edit_file / search_code / run_command / git[/dim]
[dim]核心: Agentic Loop — LLM 自主决策[/dim]
[dim]记忆: SQLite 统一存储 + 项目代码库 Embedding 索引[/dim]
[dim]接口: CLI 交互式 REPL + Web SSE 流式 API[/dim]
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
    console.print(f"[dim]API 文档: http://{host}:{port}/docs[/dim]")
    console.print(f"[dim]Web 界面: http://{host}:{port}/[/dim]")
    uvicorn.run("dev_agent.api:app", host=host, port=port, reload=True)


@app.command()
def skills(
    action: str = typer.Argument("list", help="操作: list | install"),
    name: str = typer.Argument("", help="技能名称（install 时需要）"),
):
    """
    技能管理 — 查看或安装技能

    示例:
      dev-agent skills list
      dev-agent skills install self-improving-agent
    """
    from dev_agent.skill_system import SkillLoader, get_skills_dir

    if action == "list":
        loader = SkillLoader()
        skills_dict = loader.list_all()

        if not skills_dict:
            console.print("[dim]skills 目录为空，暂无技能。[/dim]")
            console.print(f"[dim]skills 目录: {get_skills_dir()}[/dim]")
            console.print("[dim]运行 'dev-agent skills install <name>' 安装技能[/dim]")
            return

        console.print(f"[bold]已安装技能[/bold] [dim](目录: {get_skills_dir()})[/dim]\n")
        for dir_name, skill in skills_dict.items():
            console.print(f"[bold cyan]{dir_name}[/bold cyan] — {skill.name} (v{skill.version})")
            console.print(f"  {skill.description}")
            caps = ", ".join(skill.capabilities)
            console.print(f"  [dim]能力: {caps}[/dim]")
            console.print()

    elif action == "install":
        if not name:
            console.print("[red]请提供要安装的技能名称[/red]")
            console.print("示例: dev-agent skills install self-improving-agent")
            raise typer.Exit(code=1)

        console.print(f"[bold cyan]安装技能: {name}...[/bold cyan]")
        console.print(f"[dim]目标目录: {get_skills_dir()}/{name}/[/dim]")

        import subprocess
        skills_dir = str(get_skills_dir())

        try:
            result = subprocess.run(
                ["skillhub", "install", name, "--dir", skills_dir],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                console.print(f"[green]安装成功![/green]\n{result.stdout}")
                # 重新加载并显示
                loader = SkillLoader()
                skill = loader.get_by_dir_name(name)
                if skill:
                    console.print(f"[dim]已加载: {skill.name} v{skill.version}[/dim]")
            else:
                console.print(f"[yellow]skillhub 安装失败: {result.stderr}[/yellow]")
                _show_manual_install(name, skills_dir)
        except FileNotFoundError:
            _show_manual_install(name, skills_dir)
    else:
        console.print(f"[red]未知操作: {action}[/red]  (可选: list | install)")


def _show_manual_install(name: str, skills_dir: str):
    """显示手动安装引导"""
    console.print(f"\n[yellow]手动安装步骤:[/yellow]")
    console.print(f"1. 访问 [cyan]https://skillhub.cn[/cyan] 搜索 '{name}'")
    console.print(f"2. 下载技能包，解压到 [cyan]{skills_dir}\\{name}\\[/cyan]")
    console.print(f"3. 确保目录下有 [cyan]skill.json[/cyan] 文件")
    console.print(f"\n或先安装 skillhub CLI:")
    console.print(f"  curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash")
    console.print(f"  # 然后运行: skillhub install {name} --dir {skills_dir}")


def main():
    app()


if __name__ == "__main__":
    main()
