"""
API 入口 — 基于 FastAPI
提供 SSE 流式对话 + 对话管理 + 项目索引 + 记忆统计接口
"""
from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="DevAgent API",
    description="AI 编码智能体 — Agent + 工具集范式",
    version="0.4.0",
)

# CORS — 允许前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 缓存 — 按 conversation_id 复用，实现多轮对话记忆
_MAX_AGENTS = 50
_agents: dict[str, "AgentLoop"] = {}


def _get_or_create_agent(conversation_id: str | None = None):
    """获取或创建 Agent（按 conversation_id 复用，保持多轮对话上下文）"""
    from dev_agent.agent.loop import create_agent

    if conversation_id and conversation_id in _agents:
        return _agents[conversation_id], conversation_id

    agent = create_agent(workspace=Path.cwd(), conversation_id=conversation_id)

    if len(_agents) >= _MAX_AGENTS:
        oldest = next(iter(_agents))
        del _agents[oldest]

    _agents[agent.conversation_id] = agent
    return agent, agent.conversation_id


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息", min_length=1)
    conversation_id: str | None = Field(None, description="对话 ID")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.4.0"


class ConversationCreate(BaseModel):
    title: str = ""


class IndexRequest(BaseModel):
    force: bool = False


# ── 基础接口 ──

@app.get("/")
async def root():
    return {"service": "DevAgent API", "version": "0.4.0", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


# ── 对话接口 ──

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式输出 — 实时返回 Agent 的思考和操作"""
    agent, conv_id = _get_or_create_agent(req.conversation_id)

    async def event_stream():
        HEARTBEAT_INTERVAL = 15  # 心跳间隔（秒），低于前端 30s 超时

        run_gen = agent.run(req.message)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        run_gen.__anext__(),
                        timeout=HEARTBEAT_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    # 15 秒无事件 → 发送心跳注释，保持连接活跃
                    yield ": heartbeat\n\n"
                    continue

                if event.type == "tool_start":
                    yield f"event: tool_start\ndata: {json.dumps({'tool': event.tool_name, 'args': event.tool_args, 'content': event.content}, ensure_ascii=False)}\n\n"
                elif event.type == "tool_result":
                    yield f"event: tool_result\ndata: {json.dumps({'tool': event.tool_name, 'content': event.content}, ensure_ascii=False)}\n\n"
                elif event.type == "text":
                    yield f"event: text\ndata: {json.dumps({'content': event.content}, ensure_ascii=False)}\n\n"
                elif event.type == "error":
                    yield f"event: error\ndata: {json.dumps({'content': event.content}, ensure_ascii=False)}\n\n"
                elif event.type == "done":
                    yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
        except StopAsyncIteration:
            # 正常结束 — 确保发送 done 事件
            yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
            yield ": keepalive\n\n"
            await asyncio.sleep(0.5)
        except Exception as e:
            tb = traceback.format_exc()
            yield f"event: error\ndata: {json.dumps({'content': f'{e}\\n{tb[-500:]}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 对话管理接口 ──

@app.post("/conversations")
async def create_conversation(req: ConversationCreate):
    from dev_agent.memory.store import get_store

    store = get_store()
    conv_id = str(uuid.uuid4())
    store.create_conversation(conv_id, req.title)
    return {"id": conv_id, "title": req.title}


@app.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = 100):
    from dev_agent.memory.store import get_store

    store = get_store()
    messages = store.get_messages(conversation_id, limit=limit)
    return {"conversation_id": conversation_id, "messages": messages}


# ── 项目索引接口 ──

@app.post("/index")
async def index_project(req: IndexRequest):
    from dev_agent.context.index import ProjectIndex

    try:
        project_index = ProjectIndex(Path.cwd())
        stats = await asyncio.to_thread(project_index.index_project, force=req.force)
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 记忆系统接口 ──

@app.get("/memory/stats")
async def memory_stats():
    from dev_agent.memory.store import get_store

    store = get_store()
    return store.stats()


# ── 技能管理接口 ──

class SkillInstallRequest(BaseModel):
    name: str = Field(..., description="技能名称")


@app.get("/skills")
async def list_skills():
    """列出所有已安装的技能"""
    from dev_agent.skill_system import SkillLoader, get_skills_dir

    loader = SkillLoader()
    skills = loader.list_all()
    result = {}
    for dir_name, skill in skills.items():
        result[dir_name] = {
            "name": skill.name,
            "version": skill.version,
            "description": skill.description,
            "capabilities": skill.capabilities,
            "tools": skill.tools,
        }
    return {"skills_dir": str(get_skills_dir()), "skills": result}


@app.get("/skills/{name}")
async def get_skill(name: str):
    """获取指定技能详情"""
    from dev_agent.skill_system import SkillLoader

    loader = SkillLoader()
    skill = loader.get_by_dir_name(name)
    if not skill:
        raise HTTPException(404, f"技能 '{name}' 不存在")
    return {
        "name": skill.name,
        "version": skill.version,
        "description": skill.description,
        "capabilities": skill.capabilities,
        "tools": skill.tools,
    }


@app.post("/skills/install")
async def install_skill(req: SkillInstallRequest):
    """安装技能（从 skillhub）"""
    import subprocess
    from dev_agent.skill_system import get_skills_dir

    skills_dir = str(get_skills_dir())
    try:
        result = await asyncio.to_thread(
            lambda: subprocess.run(
                ["skillhub", "install", req.name, "--dir", skills_dir],
                capture_output=True, text=True, timeout=60,
            )
        )
        if result.returncode == 0:
            return {"success": True, "output": result.stdout, "skills_dir": skills_dir}
        return {"success": False, "error": result.stderr, "skills_dir": skills_dir}
    except FileNotFoundError:
        return {
            "success": False,
            "error": "skillhub CLI 未安装",
            "help": "curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash",
        }
