"""
API 入口 — 基于 FastAPI
提供 SSE 流式对话 + 对话管理 + 项目索引 + 记忆统计接口

同时托管 web/dist/ 静态界面（Vue 构建），访问根路径 / 即可使用。
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dev_agent import __version__
from dev_agent.config import get_config, reset_config

app = FastAPI(
    title="DevAgent API",
    description="AI 编码智能体 — Agent + 工具集范式",
    version=__version__,
)

# CORS 允许前端直连后端（绕过 Vite 代理的 SSE 缓冲问题）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态 Web 界面托管（Vue 构建产物）
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：多个可能的路径尝试
    _base = Path(sys._MEIPASS)
    for _p in [_base / "web" / "dist", _base / "_internal" / "web" / "dist"]:
        if _p.exists() and (_p / "index.html").exists():
            WEB_DIR = _p
            break
    else:
        WEB_DIR = _base / "web" / "dist"  # 默认路径
else:
    WEB_DIR = Path(__file__).parent.parent.parent / "web" / "dist"

# 全局 Agent 缓存 — 按 conversation_id 复用，实现多轮对话记忆
# key: conversation_id, value: AgentLoop 实例
_MAX_AGENTS = 50  # 缓存上限，防止内存无限增长
_agents: dict[str, "AgentLoop"] = {}


def _get_or_create_agent(conversation_id: str | None = None):
    """获取或创建 Agent（按 conversation_id 复用，保持多轮对话上下文）

    所有 LLM 配置从 .env 读取，前端设置通过 _save_user_settings 写入 .env。
    如果传入已有 conversation_id，会从 SQLite 恢复历史消息到 Agent 上下文。
    """
    from dev_agent.agent.loop import create_agent

    if conversation_id and conversation_id in _agents:
        return _agents[conversation_id], conversation_id

    agent = create_agent(workspace=Path.cwd(), conversation_id=conversation_id)

    # 如果是已有对话（非新对话），从 DB 恢复历史消息到上下文
    if conversation_id:
        _restore_agent_context(agent, conversation_id)

    # 超过上限时淘汰最早的 Agent
    if len(_agents) >= _MAX_AGENTS:
        oldest = next(iter(_agents))
        del _agents[oldest]

    _agents[agent.conversation_id] = agent
    return agent, agent.conversation_id


def _restore_agent_context(agent, conversation_id: str):
    """从 SQLite 恢复历史消息到 Agent 的 ContextManager 中

    这样 Agent 在回答前就知道之前对话的全部内容，避免 AI 失忆。
    """
    import json as _json
    try:
        from dev_agent.memory.store import get_store
        store = get_store()
        msgs = store.get_messages(conversation_id, limit=500)
        if not msgs:
            return

        for msg in msgs:
            role = msg.get("role")
            content = msg.get("content") or ""
            tool_name = msg.get("tool_name")
            tool_args_raw = msg.get("tool_args")
            tool_call_id = msg.get("tool_call_id")

            if role == "user":
                agent.context.add_user_message(content)
            elif role == "assistant":
                tool_calls = []
                if tool_args_raw:
                    try:
                        tool_calls = _json.loads(tool_args_raw)
                    except Exception:
                        pass
                agent.context.add_assistant_message(content, tool_calls if tool_calls else None)
            elif role == "tool":
                agent.context.add_tool_result(
                    tool_call_id=tool_call_id or "",
                    tool_name=tool_name or "",
                    result=content,
                )
    except Exception:
        # 恢复失败不影响核心功能
        pass


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息", min_length=1)
    conversation_id: str | None = Field(None, description="对话 ID（首次对话不传，后续传入以保持上下文）")
    settings: dict | None = Field(None, description="前端设置覆盖（已弃用，配置从 .env 读取）")
    mode: str = Field("single", description="运行模式: single=单Agent, collaborate=多Agent协作")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = __version__


class ConversationCreate(BaseModel):
    title: str = ""


class IndexRequest(BaseModel):
    force: bool = False


# ── 基础接口 ──

@app.get("/")
async def root():
    """Web 界面"""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(404, "Web 界面未找到，请先运行 cd web && npm install && npm run build")


# 挂载静态资源（JS/CSS/图片等）
if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse()


@app.get("/debug/webfiles")
async def debug_web_files():
    """调试接口：列出 WEB_DIR 路径和文件"""
    web_path = str(WEB_DIR)
    exists = WEB_DIR.exists()
    index_exists = (WEB_DIR / "index.html").exists()
    assets_exists = (WEB_DIR / "assets").exists()
    files = []
    if exists:
        for f in sorted(WEB_DIR.rglob("*")):
            if f.is_file():
                files.append(str(f.relative_to(WEB_DIR)))
    return {
        "web_dir": web_path,
        "exists": exists,
        "index_html": index_exists,
        "assets_dir": assets_exists,
        "pyinstaller_frozen": getattr(sys, 'frozen', False),
        "meipass": getattr(sys, '_MEIPASS', None),
        "file_count": len(files),
        "files": files[:50],
    }


# ── 对话接口 ──

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式输出 — 实时返回 Agent 的思考和操作

    事件类型:
      - event: tool_start   工具调用开始
      - event: tool_result  工具执行结果
      - event: text         Agent 文本回复
      - event: collaborate  多智能体协作事件（mode=collaborate 时）
      - event: error        错误
      - event: done         完成（data 中含 conversation_id）

    通过传入 conversation_id 实现多轮对话上下文保持。
    mode=collaborate 时启动多智能体协作流程。
    """
    # 协作模式走多 Agent 流程
    if req.mode == "collaborate":
        return StreamingResponse(
            _collaborate_stream(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    agent, conv_id = _get_or_create_agent(req.conversation_id)

    async def event_stream():
        event_queue: asyncio.Queue = asyncio.Queue()

        async def agent_producer():
            """后台任务：运行 Agent，将事件放入队列"""
            try:
                async for event in agent.run(req.message):
                    await event_queue.put(("event", event))
            except Exception as e:
                await event_queue.put(("error", str(e)))

        producer_task = asyncio.create_task(agent_producer())
        heartbeat_interval = 10  # 秒（低于前端 30s 超时）

        try:
            while True:
                try:
                    item_type, item_data = await asyncio.wait_for(
                        event_queue.get(),
                        timeout=heartbeat_interval,
                    )
                except asyncio.TimeoutError:
                    # 10 秒无事件 — 发送心跳，保持连接活跃
                    if producer_task.done():
                        break
                    yield ": heartbeat\n\n"
                    continue

                if item_type == "event":
                    event = item_data
                    if event.type == "tool_start":
                        # 智能体调用识别：只有 load_skill(name="xxx") 且指定了技能名时才标记
                        is_agent = bool(event.skill_name) and event.tool_name == "load_skill"
                        yield f"event: tool_start\ndata: {json.dumps({'tool': event.tool_name, 'args': event.tool_args, 'content': event.content, 'tokens': event.tokens or {}, 'is_agent': is_agent, 'agent_name': event.skill_name or ''}, ensure_ascii=False)}\n\n"
                    elif event.type == "tool_result":
                        yield f"event: tool_result\ndata: {json.dumps({'tool': event.tool_name, 'content': event.content}, ensure_ascii=False)}\n\n"
                    elif event.type == "text":
                        yield f"event: text\ndata: {json.dumps({'content': event.content}, ensure_ascii=False)}\n\n"
                    elif event.type == "error":
                        yield f"event: error\ndata: {json.dumps({'content': event.content, 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
                    elif event.type == "done":
                        yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
                elif item_type == "done":
                    yield f"event: done\ndata: {json.dumps({'conversation_id': item_data}, ensure_ascii=False)}\n\n"
                    break
                elif item_type == "error":
                    yield f"event: error\ndata: {json.dumps({'content': item_data, 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
                    break
        finally:
            if not producer_task.done():
                producer_task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _collaborate_stream(req: ChatRequest):
    """多智能体协作 SSE 流"""
    from dev_agent.agents.orchestrator import create_orchestrator

    orchestrator = create_orchestrator()
    conv_id = req.conversation_id or str(uuid.uuid4())

    try:
        async for event in orchestrator.collaborate(req.message):
            if event.type == "task_created":
                yield f"event: collaborate\ndata: {json.dumps({'phase': 'plan', 'role': event.role, 'content': event.content}, ensure_ascii=False)}\n\n"
            elif event.type == "worker_start":
                yield f"event: collaborate\ndata: {json.dumps({'phase': 'start', 'role': event.role, 'content': event.content}, ensure_ascii=False)}\n\n"
            elif event.type == "worker_done":
                yield f"event: collaborate\ndata: {json.dumps({'phase': 'done', 'role': event.role, 'content': event.content}, ensure_ascii=False)}\n\n"
            elif event.type == "reflection":
                yield f"event: collaborate\ndata: {json.dumps({'phase': 'reflection', 'role': event.role, 'content': event.content}, ensure_ascii=False)}\n\n"
            elif event.type == "text":
                yield f"event: text\ndata: {json.dumps({'content': event.content, 'role': event.role}, ensure_ascii=False)}\n\n"
            elif event.type == "done":
                yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'content': str(e), 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id}, ensure_ascii=False)}\n\n"


# ── 对话管理接口 ──

@app.get("/conversations")
async def list_conversations(limit: int = 50):
    """获取对话列表（按更新时间倒序）"""
    from dev_agent.memory.store import get_store

    store = get_store()
    conversations = store.list_conversations(limit=limit)
    return {"conversations": conversations}


@app.post("/conversations")
async def create_conversation(req: ConversationCreate):
    """创建新对话"""
    from dev_agent.memory.store import get_store

    store = get_store()
    conv_id = str(uuid.uuid4())
    store.create_conversation(conv_id, req.title)
    return {"id": conv_id, "title": req.title}


@app.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = 100):
    """获取对话消息列表"""
    from dev_agent.memory.store import get_store

    store = get_store()
    messages = store.get_messages(conversation_id, limit=limit)
    return {"conversation_id": conversation_id, "messages": messages}


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话及其所有消息"""
    from dev_agent.memory.store import get_store

    store = get_store()
    store.delete_conversation(conversation_id)
    # 清理 Agent 缓存
    if conversation_id in _agents:
        del _agents[conversation_id]
    return {"success": True, "id": conversation_id}


# ── 项目索引接口 ──

@app.post("/index")
async def index_project(req: IndexRequest):
    """索引项目代码库（用于 search_code 语义搜索）

    通过 asyncio.to_thread 在后台线程执行，避免阻塞事件循环。
    """
    from dev_agent.context.index import ProjectIndex

    try:
        project_index = ProjectIndex(_current_workspace())
        stats = await asyncio.to_thread(project_index.index_project, force=req.force)
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 记忆系统接口 ──

@app.get("/memory/stats")
async def memory_stats():
    """获取三层记忆系统统计"""
    from dev_agent.memory.memory_orch import create_memory_orchestrator

    orch = create_memory_orchestrator()
    data = orch.stats()
    data["active_agents"] = len(_agents)
    return data


@app.get("/api/token-stats")
async def token_stats():
    """获取 Token 用量统计（供仪表盘展示）"""
    try:
        from dev_agent.memory.store import get_store
        store = get_store()
        return store.get_token_stats()
    except Exception as e:
        return {
            "total_prompt": 0, "total_completion": 0,
            "total_tokens": 0, "total_calls": 0,
            "today_prompt": 0, "today_completion": 0,
            "today_tokens": 0, "today_calls": 0,
            "error": str(e),
        }


@app.get("/memory/summaries")
async def list_memory_summaries(limit: int = 10):
    """获取跨会话记忆摘要列表"""
    from dev_agent.memory.memory_orch import create_memory_orchestrator

    orch = create_memory_orchestrator()
    summaries = orch.long_term.get_recent_summaries(limit=limit)
    return {"summaries": summaries, "count": len(summaries)}


@app.get("/memory/memories")
async def list_memories(limit: int = 20):
    """获取所有语义记忆（按重要性排序）"""
    from dev_agent.memory.memory_orch import create_memory_orchestrator

    orch = create_memory_orchestrator()
    memories = orch.long_term.recall_important_memories(limit=limit)
    return {"memories": memories, "count": len(memories)}


@app.post("/memory/search")
async def search_memories(query: str = "", top_k: int = 5):
    """语义搜索记忆"""
    if not query:
        return {"results": [], "count": 0}
    from dev_agent.memory.memory_orch import create_memory_orchestrator

    orch = create_memory_orchestrator()
    if orch.semantic:
        results = orch.semantic.search(query, top_k=top_k)
        return {"results": results, "count": len(results)}
    return {"results": [], "count": 0, "note": "语义记忆未启用"}


# ── 版本检查与更新接口 ──

@app.get("/api/agent/info")
async def get_agent_info():
    """获取当前 Agent 的基本信息"""
    return {
        "name": "编码智能体",
        "version": __version__,
        "description": "DevAgent 核心编码智能体 — 基于 LLM 自主决策，通过工具调用完成代码开发任务。具备代码读取、编写、编辑、搜索、命令执行、Git 版本控制等完整能力。",
        "capabilities": [
            "代码读写与编辑",
            "项目文件浏览与搜索",
            "命令行操作与构建运行",
            "Git 版本控制（状态/差异/日志/提交/分支）",
            "多轮对话上下文保持",
            "工具执行反思与自动修正",
            "代码库语义搜索",
            "技能（Skill）扩展系统",
        ],
        "tools_endpoint": "/api/tools",
        "skills_endpoint": "/api/skills",
    }


@app.get("/api/agents")
async def list_agents():
    """获取所有已定义的 Agent 角色列表（含专属技能信息）"""
    from dev_agent.agents.loader import get_agent_loader

    loader = get_agent_loader()
    agents = loader.get_all_role_info()
    return {"agents": agents, "count": len(agents)}


# ── 工作区管理 API ──


def _current_workspace() -> Path:
    """获取当前工作区路径"""
    from dev_agent.config import get_config
    cfg = get_config()
    ws = cfg.workspace
    if ws is None or str(ws) == ".":
        ws = Path.cwd()
    return ws.resolve()


@app.get("/api/workspace")
async def get_workspace():
    """获取当前工作区路径和顶层文件列表"""
    ws = _current_workspace()
    return {
        "path": str(ws),
        "name": ws.name,
    }


@app.get("/api/workspace/tree")
async def get_workspace_tree(path: str = ""):
    """浏览目录树 — 返回指定目录下的一级内容

    Args:
        path: 要浏览的目录路径（绝对路径或相对当前工作区）。
              不传则返回当前工作区的内容。
              传 "roots" 返回磁盘根目录列表（Windows）。
    """
    import os

    if path == "roots" or not path:
        if not path:
            ws = _current_workspace()
            target = ws
        else:
            # Windows 磁盘根目录
            roots = []
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    roots.append({"name": f"{letter}:", "path": drive, "type": "dir"})
            return {"path": "roots", "entries": roots}
    else:
        p = Path(path)
        if not p.is_absolute():
            p = _current_workspace() / p
        target = p.resolve()

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在: {target}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"不是目录: {target}")

    entries = []
    try:
        for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            # 跳过隐藏文件和常见忽略目录
            if item.name.startswith(".") and item.name not in (".env", ".gitignore"):
                continue
            if item.name in {"node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".git"}:
                continue
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "dir" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else 0,
                    "ext": item.suffix.lower() if item.is_file() else "",
                })
            except (PermissionError, OSError):
                continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"无权限访问: {target}")

    return {"path": str(target), "entries": entries}


class WorkspaceSwitchRequest(BaseModel):
    path: str = Field(..., description="新的工作区路径")


@app.post("/api/workspace")
async def switch_workspace(req: WorkspaceSwitchRequest):
    """切换工作区到指定路径

    切换后会清除所有缓存的 Agent 实例，下次对话将使用新工作区。
    """
    from dev_agent.config import get_config, reset_config
    import os

    target = Path(req.path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在: {target}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"不是目录: {target}")

    # 更新配置中的 workspace
    cfg = get_config()
    cfg.workspace = target

    # 清除所有缓存的 Agent 实例（它们绑定的是旧 workspace）
    cleared = len(_agents)
    _agents.clear()

    return {
        "success": True,
        "path": str(target),
        "name": target.name,
        "cleared_agents": cleared,
    }


@app.get("/api/tools")
async def list_tools():
    """获取所有已注册工具的名称和描述"""
    from dev_agent.tools.engine import ToolEngine
    from dev_agent.config import get_config
    cfg = get_config()
    engine = ToolEngine(workspace=cfg.workspace)
    schemas = engine.get_schemas()
    tools = []
    for s in schemas:
        tools.append({
            "name": s.get("function", {}).get("name", ""),
            "description": s.get("function", {}).get("description", ""),
            "parameters": s.get("function", {}).get("parameters", {}),
        })
    return {"tools": tools, "count": len(tools)}


@app.get("/api/skills")
async def list_skills():
    """获取所有已安装技能的信息（含调用时机等丰富信息）"""
    try:
        from dev_agent.skill_system import SkillLoader
        loader = SkillLoader()
        manifest = loader.generate_manifest()
        return manifest
    except Exception as e:
        return {"skills": [], "count": 0, "error": str(e)}


@app.get("/api/skills/remote-search")
async def search_remote_skills(q: str = "", limit: int = 10):
    """搜索远程技能库（内置 HTTP 客户端，不依赖 skillhub CLI）"""
    try:
        from dev_agent.skill_hub_client import SkillHubClient
        client = SkillHubClient()
        results = await client.search(query=q, limit=limit)
        return {
            "query": q,
            "count": len(results),
            "skills": [r.to_dict() for r in results],
        }
    except Exception as e:
        return {"query": q, "count": 0, "skills": [], "error": str(e)}


@app.post("/api/skills/install")
async def install_skill_api(req: dict):
    """通过 API 安装技能到 .agent/skills/ 目录

    Body: {"name": "skill-slug", "force": false}
    """
    from dev_agent.skill_hub_client import SkillHubClient
    from dev_agent.skill_system import SkillLoader

    name = req.get("name", "").strip()
    force = bool(req.get("force", False))
    if not name:
        return {"success": False, "error": "缺少技能名称"}

    try:
        from dev_agent.skill_system import get_skills_dir
        skills_dir = get_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)

        client = SkillHubClient()
        result = await client.download_and_install(
            slug=name,
            target_dir=skills_dir,
            force=force,
        )

        if not result.get("success"):
            return {"success": False, "error": result.get("error", "未知错误")}

        # 重新加载技能清单
        SkillLoader.reload()

        return {
            "success": True,
            "name": name,
            "path": result.get("path"),
            "skill_json": result.get("skill_json"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/skills/manifest")
async def get_skills_manifest():
    """直接返回 manifest.json 文件内容（快速加载，无需重新扫描）"""
    from dev_agent.skill_system import get_skills_dir
    manifest_path = get_skills_dir() / "manifest.json"
    if manifest_path.exists():
        try:
            import json
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # fallback: 重新扫描
    from dev_agent.skill_system import SkillLoader
    return SkillLoader().generate_manifest()


@app.get("/api/models")
async def list_models(
    provider: str = "",
    api_key: str = "",
    base_url: str = "",
):
    """获取供应商的真实模型列表

    直接调用供应商的 GET {base_url}/models 接口拉取真实模型清单。
    不提供内置回退——需要用户提供有效的 API Key 和 Base URL。
    """
    import httpx

    result = {
        "models": [],
        "source": "none",
        "error": None,
    }

    if not base_url:
        result["error"] = "请先配置 Base URL"
        return result

    if not api_key:
        result["error"] = "请先配置 API Key"
        return result

    try:
        models_url = base_url.rstrip("/") + "/models"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", data.get("models", []))
                if isinstance(raw_models, list) and raw_models:
                    result["models"] = [
                        {"id": m.get("id", m) if isinstance(m, dict) else str(m),
                         "name": m.get("id", m) if isinstance(m, dict) else str(m)}
                        for m in raw_models
                    ]
                    result["source"] = "api"
                else:
                    result["error"] = "API 返回的模型列表为空"
            else:
                result["error"] = f"API 请求失败 (HTTP {resp.status_code})"
    except Exception as e:
        result["error"] = f"连接失败: {str(e)}"

    return result


# ── 用户配置持久化接口 ──

_USER_SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "settings.json"


def _load_user_settings() -> dict:
    """从磁盘加载用户配置"""
    try:
        if _USER_SETTINGS_FILE.exists():
            return json.loads(_USER_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


_DOTENV_KEY_MAP = {
    "LLM_CHAT_API_KEY": ("apiKeys", "provider"),
    "LLM_CHAT_BASE_URL": ("baseUrl",),
    "LLM_CHAT_MODEL": ("model",),
    "LLM_CHAT_TEMPERATURE": ("temperature",),
    "LLM_CHAT_MAX_TOKENS": ("maxTokens",),
}


def _save_to_dotenv(data: dict) -> None:
    """将前端用户配置写入 .env 文件，确保后端始终使用前端配置"""
    dotenv_path = Path(".env").resolve()
    if not dotenv_path.exists():
        print(f"[WARN] .env 文件不存在: {dotenv_path}")
        return

    # 从 data 中提取值，映射为 .env 变量
    env_values: dict[str, str] = {}
    for env_key, keys in _DOTENV_KEY_MAP.items():
        if env_key == "LLM_CHAT_API_KEY":
            # apiKeys 是 { provider: key } 字典，需要知道当前 provider
            api_keys = data.get("apiKeys") or {}
            provider = data.get("provider", "deepseek")
            value = api_keys.get(provider, "")
        else:
            # 其他字段直接取
            value = data.get(keys[0])
        if value is not None and value != "":
            env_values[env_key] = str(value)

    if not env_values:
        return

    # 读取当前 .env，逐行替换
    lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []
    updated_keys = set()
    for line in lines:
        stripped = line.strip()
        # 跳过注释，但保留
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in env_values:
            new_lines.append(f"{key}={env_values[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    # 追加尚未在 .env 中的新变量
    for key, value in env_values.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    dotenv_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"[INFO] .env 已更新: {', '.join(f'{k}={v}' for k, v in env_values.items())}")


def _save_user_settings(data: dict) -> None:
    """将用户配置写入磁盘，同时写入 .env 并重载配置"""
    # 1) 写入 data/settings.json（保持向前兼容）
    try:
        _USER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _USER_SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] 保存 settings.json 失败: {e}")

    # 2) 写入 .env 并重载配置
    _save_to_dotenv(data)
    reset_config()
    # 触发一次 get_config() 让新配置生效并打印
    cfg = get_config()
    masked_key = cfg.llm_chat_api_key[:8] + "..." + cfg.llm_chat_api_key[-4:] if len(cfg.llm_chat_api_key) > 12 else "***"
    print(f"[INFO] 配置已重载: model={cfg.llm_chat_model}, base_url={cfg.llm_chat_base_url}, api_key={masked_key}")


@app.get("/api/user-settings")
async def get_user_settings():
    """获取持久化的用户配置（provider / apiKeys / model / baseUrl / temperature / maxTokens）"""
    return _load_user_settings()


class UserSettingsPayload(BaseModel):
    provider: str | None = None
    apiKeys: dict | None = None
    model: str | None = None
    baseUrl: str | None = None
    temperature: float | None = None
    maxTokens: int | None = None


@app.post("/api/user-settings")
async def save_user_settings(payload: UserSettingsPayload):
    """保存用户配置到磁盘，与 localStorage 双写保证多端一致"""
    current = _load_user_settings()
    # 仅更新传入的非 None 字段
    update = payload.model_dump(exclude_none=True)
    current.update(update)
    _save_user_settings(current)
    return {"success": True}


@app.get("/api/version/check")
async def version_check():
    """检查最新版本（多源回退：GitHub → 镜像代理 → PyPI）"""
    import httpx

    current = __version__
    result = {
        "current": current,
        "latest": current,
        "changelog": "",
        "has_update": False,
        "release_url": "",
        "download_url": "",
        "source": "none",
    }

    # GitHub API 源列表（直连 + 镜像代理，按优先级排列）
    gh_api_sources = [
        "https://api.github.com/repos/joker-144/Code-Assistant/releases/latest",
        "https://gh-proxy.com/api.github.com/repos/joker-144/Code-Assistant/releases/latest",
        "https://ghproxy.net/api.github.com/repos/joker-144/Code-Assistant/releases/latest",
    ]

    gh_headers = {
        "User-Agent": "DevAgent-Updater",
        "Accept": "application/vnd.github.v3+json",
    }

    # 依次尝试每个源
    for api_url in gh_api_sources:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(api_url, headers=gh_headers)
                resp.raise_for_status()
                data = resp.json()

            tag = data.get("tag_name", "").lstrip("v")
            changelog_body = data.get("body", "") or ""
            html_url = data.get("html_url", "")

            # 查找 Windows 安装包资源
            download_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".exe") and ("Setup" in name or "setup" in name or "install" in name or "Installer" in name):
                    download_url = asset.get("browser_download_url", "")
                    break
            if not download_url:
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        download_url = asset.get("browser_download_url", "")
                        break

            if tag:
                result["latest"] = tag
                result["changelog"] = changelog_body[:4096]
                result["release_url"] = html_url
                result["download_url"] = download_url
                result["has_update"] = _compare_versions(tag, current) > 0
                result["source"] = "github"
                return result
        except Exception:
            continue

    # 所有 GitHub 源均失败，回退 PyPI
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            py_resp = client.get(
                "https://pypi.org/pypi/dev-agent/json",
                headers={"User-Agent": "DevAgent-Updater"},
            )
            py_resp.raise_for_status()
            data = py_resp.json()
            latest = data.get("info", {}).get("version", current)
            release_url = data.get("info", {}).get("release_url", "")

            result["latest"] = latest
            result["release_url"] = release_url
            result["has_update"] = _compare_versions(latest, current) > 0
            result["source"] = "pypi"

            if result["has_update"]:
                result["changelog"] = f"PyPI 新版本 {latest} 已发布，请使用 pip install --upgrade dev-agent 更新。"
    except Exception as e:
        result["error"] = f"检查更新失败: {str(e)}"

    return result


@app.post("/api/version/download")
async def version_download():
    """下载最新版本的安装包（多源回退 + 断点续传 + SSE 进度流）

    下载源优先级：GitHub 直连 → 镜像代理 → 逐源尝试
    所有镜像代理对同一个 download_url 做前缀拼接。
    """
    import asyncio
    import httpx
    import time

    # GitHub 下载镜像代理前缀列表（对 release asset 下载 URL 做前缀拼接）
    MIRROR_PREFIXES = [
        "",  # 直连
        "https://gh-proxy.com/",
        "https://ghproxy.net/",
        "https://github.moeyy.xyz/",
    ]

    async def download_stream():
        release_url = ""
        gh_data = None

        # Step 1: 获取 Release 信息（多源尝试）
        gh_api_sources = [
            "https://api.github.com/repos/joker-144/Code-Assistant/releases/latest",
            "https://gh-proxy.com/api.github.com/repos/joker-144/Code-Assistant/releases/latest",
            "https://ghproxy.net/api.github.com/repos/joker-144/Code-Assistant/releases/latest",
        ]
        gh_headers = {
            "User-Agent": "DevAgent-Updater",
            "Accept": "application/vnd.github.v3+json",
        }

        for api_url in gh_api_sources:
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.get(api_url, headers=gh_headers)
                    resp.raise_for_status()
                    gh_data = resp.json()
                    break
            except Exception:
                continue

        if gh_data is None:
            yield f"data: {json.dumps({'status': 'error', 'message': '无法连接到更新服务器，请检查网络或稍后重试'}, ensure_ascii=False)}\n\n"
            return

        tag = gh_data.get("tag_name", "").lstrip("v")
        release_url = gh_data.get("html_url", "")

        download_url = ""
        file_name = ""
        for asset in gh_data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe"):
                download_url = asset.get("browser_download_url", "")
                file_name = name
                break

        if not download_url:
            msg = "未找到可用安装包"
            if release_url:
                msg += f"，请手动下载: {release_url}"
            yield f"data: {json.dumps({'status': 'error', 'message': msg, 'release_url': release_url}, ensure_ascii=False)}\n\n"
            return

        download_dir = Path.home() / "Downloads"
        download_dir.mkdir(exist_ok=True)
        dest = download_dir / file_name

        # 构建候选下载 URL 列表（直连 + 各镜像代理）
        candidate_urls = []
        for prefix in MIRROR_PREFIXES:
            candidate_urls.append(f"{prefix}{download_url}")

        # 先获取文件大小
        total_size = 0
        for try_url in candidate_urls:
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    head_resp = await client.head(try_url, headers={"User-Agent": "DevAgent-Updater"})
                    if head_resp.status_code == 200:
                        total_size = int(head_resp.headers.get("Content-Length", 0))
                        if total_size > 0:
                            break
            except Exception:
                continue

        existing_size = dest.stat().st_size if dest.exists() else 0
        if existing_size > 0 and total_size > 0 and existing_size >= total_size:
            yield f"data: {json.dumps({'status': 'done', 'message': '文件已存在，跳过下载', 'file_path': str(dest), 'percent': 100}, ensure_ascii=False)}\n\n"
            return

        if existing_size > 0 and total_size > 0:
            pct = int(existing_size * 100 / total_size)
            yield f"data: {json.dumps({'status': 'progress', 'message': f'续传下载中', 'percent': pct, 'downloaded_mb': round(existing_size/1048576, 1), 'total_mb': round(total_size/1048576, 1), 'speed_mb_s': 0}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'status': 'info', 'message': f'找到版本 {tag}，开始下载 {file_name}…', 'total_mb': round(total_size/1048576, 1) if total_size else 0}, ensure_ascii=False)}\n\n"

        # 逐源尝试下载
        download_succeeded = False
        last_report = 0.0
        last_downloaded = existing_size
        speed_start_time = 0.0

        for source_idx, try_url in enumerate(candidate_urls):
            if download_succeeded:
                break

            source_name = "直连" if source_idx == 0 else f"镜像{source_idx}"

            try:
                headers = {"User-Agent": "DevAgent-Updater"}
                resume_from = dest.stat().st_size if dest.exists() else 0
                if resume_from > 0:
                    headers["Range"] = f"bytes={resume_from}-"

                download_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(600.0, connect=15.0),
                    follow_redirects=True,
                    headers={"User-Agent": "DevAgent-Updater"},
                )

                total_downloaded = resume_from
                speed_start_time = time.time()
                last_downloaded = total_downloaded

                async with download_client.stream("GET", try_url, headers=headers) as resp:
                    if resp.status_code not in (200, 206):
                        resp.raise_for_status()

                    if resp.status_code == 206:
                        cr = resp.headers.get("Content-Range", "")
                        if cr:
                            total_size = int(cr.split("/")[-1])

                    open_mode = "ab" if (resp.status_code == 206 and resume_from > 0) else "wb"
                    if open_mode == "wb":
                        total_downloaded = 0
                        last_downloaded = 0

                    with open(dest, open_mode) as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            total_downloaded += len(chunk)
                            now = time.time()
                            if total_size and (now - last_report > 0.3 or total_downloaded >= total_size):
                                last_report = now
                                pct = int(total_downloaded * 100 / total_size)
                                # 计算速度
                                elapsed = now - speed_start_time
                                speed = (total_downloaded - last_downloaded) / elapsed / 1048576 if elapsed > 0 else 0
                                yield f"data: {json.dumps({'status': 'progress', 'message': '下载中', 'percent': pct, 'downloaded_mb': round(total_downloaded/1048576, 1), 'total_mb': round(total_size/1048576, 1), 'speed_mb_s': round(speed, 2)}, ensure_ascii=False)}\n\n"
                                last_downloaded = total_downloaded
                                speed_start_time = now

                await download_client.aclose()
                download_succeeded = True

            except Exception as e:
                if source_idx < len(candidate_urls) - 1:
                    yield f"data: {json.dumps({'status': 'info', 'message': f'{source_name}下载失败，切换到下一个源…'}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)
                else:
                    err_msg = f"所有下载源均失败: {str(e)}"
                    if release_url:
                        err_msg += f" | 请手动下载: {release_url}"
                    yield f"data: {json.dumps({'status': 'error', 'message': err_msg, 'release_url': release_url}, ensure_ascii=False)}\n\n"
                    return

        if download_succeeded:
            yield f"data: {json.dumps({'status': 'done', 'message': '下载完成', 'file_path': str(dest), 'percent': 100, 'downloaded_mb': round(total_size/1048576, 1) if total_size else 0, 'total_mb': round(total_size/1048576, 1) if total_size else 0}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        download_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/version/install")
async def version_install(request: Request):
    """启动安装程序（UAC 提权 + 独立进程），安装完成后由安装程序处理重启。

    Inno Setup 安装包本身支持升级覆盖安装，不需要先卸载旧版本。
    """
    import subprocess

    body = await request.json()
    file_path = body.get("file_path", "")

    if not file_path or not Path(file_path).exists():
        return {"success": False, "error": f"安装包不存在: {file_path}"}

    try:
        # 使用 PowerShell Start-Process -Verb RunAs 触发 UAC 提权
        # 这样安装程序会以管理员权限运行，能写入 Program Files
        # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS 确保安装程序独立于 API 进程
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200

        proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"Start-Process -FilePath '{file_path}' -Verb RunAs",
            ],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        return {
            "success": True,
            "message": "安装程序已启动（需要管理员权限确认），请在 UAC 弹窗中点击[是]以继续安装。",
            "pid": proc.pid,
        }
    except Exception as e:
        return {"success": False, "error": f"安装启动失败: {str(e)}"}


def _compare_versions(v1: str, v2: str) -> int:
    """比较两个 semver 版本号，返回 1(v1>v2) / 0(相等) / -1(v1<v2)"""
    try:
        from packaging.version import parse as parse_version
    except ImportError:
        def parse_version(v: str):
            parts = []
            for x in v.replace("-", ".").split("."):
                try:
                    parts.append(int(x))
                except ValueError:
                    parts.append(0)
            return tuple(parts)

    p1 = parse_version(v1)
    p2 = parse_version(v2)
    if p1 > p2:
        return 1
    elif p1 < p2:
        return -1
    return 0
