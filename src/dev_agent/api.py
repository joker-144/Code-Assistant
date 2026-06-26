"""
API 入口 — 基于 FastAPI
提供 REST API 和 WebSocket 接口
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel, Field

from dev_agent.orchestrator import get_orchestrator

app = FastAPI(
    title="DevAgent API",
    description="多模型协作开发智能体 — DeepSeek-V4-Pro + Qwen-Plus",
    version="0.1.0",
)


# ── 请求/响应模型 ──

class ExecuteRequest(BaseModel):
    request: str = Field(..., description="开发需求描述", min_length=1)
    request_type: str = Field(default="code_gen", description="任务类型: code_gen | code_fix")


class ReviewRequest(BaseModel):
    code: str = Field(..., description="要审查的代码")
    task_description: str = Field(default="", description="原始需求描述")


class GenerateDocsRequest(BaseModel):
    code: str = Field(..., description="要生成文档的代码")


class ExecuteResponse(BaseModel):
    task_id: str
    overall_approach: str
    sub_tasks: list[dict]
    duration_seconds: float
    status: str = "completed"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


# ── API 路由 ──

@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse()


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """
    执行开发任务

    输入自然语言需求，返回执行计划 + 结果
    """
    try:
        orchestrator = get_orchestrator()
        result = orchestrator.execute(req.request, req.request_type)
        return ExecuteResponse(
            task_id=result["task_id"],
            overall_approach=result["overall_approach"],
            sub_tasks=result.get("sub_tasks", []),
            duration_seconds=result["duration_seconds"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/review")
async def review_code(req: ReviewRequest):
    """
    审查代码质量

    返回结构化审查报告（5 维度评分 + 问题清单）
    """
    try:
        orchestrator = get_orchestrator()
        return orchestrator.review_code(req.code, req.task_description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-docs")
async def generate_docs(req: GenerateDocsRequest):
    """
    为代码生成文档
    """
    try:
        orchestrator = get_orchestrator()
        docs = orchestrator.generate_docs(req.code)
        return {"documentation": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats")
async def memory_stats():
    """获取记忆系统统计"""
    try:
        orchestrator = get_orchestrator()
        return orchestrator.memory_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 流式输出"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            orchestrator = get_orchestrator()

            await websocket.send_json({"type": "status", "message": "开始分析需求..."})

            result = orchestrator.execute(data)

            await websocket.send_json({
                "type": "result",
                "data": result,
            })
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()