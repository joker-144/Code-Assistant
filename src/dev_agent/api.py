"""
API 入口 — 基于 FastAPI
提供 SSE 流式对话 + 对话管理 + 项目索引 + 记忆统计接口

同时托管 web/dist/ 静态界面（Vue 构建），访问根路径 / 即可使用。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(
    title="DevAgent API",
    description="AI 编码智能体 — Agent + 工具集范式",
    version="0.4.0",
)

# 静态 Web 界面托管（Vue 构建产物）
WEB_DIR = Path(__file__).parent.parent.parent / "web" / "dist"

# 全局 Agent 缓存 — 按 conversation_id 复用，实现多轮对话记忆
# key: conversation_id, value: AgentLoop 实例
_MAX_AGENTS = 50  # 缓存上限，防止内存无限增长
_agents: dict[str, "AgentLoop"] = {}


def _get_or_create_agent(conversation_id: str | None = None):
    """获取或创建 Agent（按 conversation_id 复用，保持多轮对话上下文）"""
    from dev_agent.agent.loop import create_agent

    if conversation_id and conversation_id in _agents:
        return _agents[conversation_id], conversation_id

    agent = create_agent(workspace=Path.cwd(), conversation_id=conversation_id)

    # 超过上限时淘汰最早的 Agent
    if len(_agents) >= _MAX_AGENTS:
        oldest = next(iter(_agents))
        del _agents[oldest]

    _agents[agent.conversation_id] = agent
    return agent, agent.conversation_id


# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息", min_length=1)
    conversation_id: str | None = Field(None, description="对话 ID（首次对话不传，后续传入以保持上下文）")


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


# ── 对话接口 ──

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式输出 — 实时返回 Agent 的思考和操作

    事件类型:
      - event: tool_start   工具调用开始
      - event: tool_result  工具执行结果
      - event: text         Agent 文本回复
      - event: error        错误
      - event: done         完成（data 中含 conversation_id）

    通过传入 conversation_id 实现多轮对话上下文保持。
    """
    agent, conv_id = _get_or_create_agent(req.conversation_id)

    async def event_stream():
        try:
            async for event in agent.run(req.message):
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
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'content': str(e)}, ensure_ascii=False)}\n\n"

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


# ── 项目索引接口 ──

@app.post("/index")
async def index_project(req: IndexRequest):
    """索引项目代码库（用于 search_code 语义搜索）

    通过 asyncio.to_thread 在后台线程执行，避免阻塞事件循环。
    """
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
    """获取记忆系统统计"""
    from dev_agent.memory.store import get_store

    store = get_store()
    return store.stats()
