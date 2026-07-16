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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dev_agent import __version__

app = FastAPI(
    title="DevAgent API",
    description="AI 编码智能体 — Agent + 工具集范式",
    version=__version__,
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


def _get_or_create_agent(conversation_id: str | None = None, settings: dict | None = None):
    """获取或创建 Agent（按 conversation_id 复用，保持多轮对话上下文）

    若传入 settings 覆盖，则始终新建 Agent（避免配置变更后复用旧 Agent）。
    """
    from dev_agent.agent.loop import create_agent

    # 有配置覆盖时，不复用，创建新 Agent
    if settings:
        agent = create_agent(workspace=Path.cwd(), conversation_id=conversation_id, llm_overrides=settings)
        _agents[agent.conversation_id] = agent
        return agent, agent.conversation_id

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
    settings: dict | None = Field(None, description="前端设置覆盖（api_key, base_url, model, temperature, max_tokens）")


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
      - event: error        错误
      - event: done         完成（data 中含 conversation_id）

    通过传入 conversation_id 实现多轮对话上下文保持。
    """
    agent, conv_id = _get_or_create_agent(req.conversation_id, req.settings)

    async def event_stream():
        agent_gen = agent.run(req.message)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        agent_gen.__anext__(),
                        timeout=5.0,
                    )
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
                except asyncio.TimeoutError:
                    # 每 5 秒发送心跳注释，防止 TCP 空闲断开
                    yield ": keepalive\n\n"
        except StopAsyncIteration:
            pass
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


# ── 版本检查与更新接口 ──

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

_USER_SETTINGS_FILE = Path.home() / ".devagent" / "settings.json"


def _load_user_settings() -> dict:
    """从磁盘加载用户配置"""
    try:
        if _USER_SETTINGS_FILE.exists():
            return json.loads(_USER_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_user_settings(data: dict) -> None:
    """将用户配置写入磁盘"""
    _USER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USER_SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    """检查最新版本（优先 GitHub Releases，回退 PyPI）"""
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

    # 优先尝试 GitHub Releases
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            gh_resp = client.get(
                "https://api.github.com/repos/joker-144/Code-Assistant/releases/latest",
                headers={
                    "User-Agent": "DevAgent-Updater",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            gh_resp.raise_for_status()
            gh_data = gh_resp.json()
            tag = gh_data.get("tag_name", "").lstrip("v")
            changelog_body = gh_data.get("body", "") or ""
            html_url = gh_data.get("html_url", "")

            # 查找 Windows 安装包资源
            download_url = ""
            for asset in gh_data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".exe") and ("Setup" in name or "setup" in name or "install" in name or "Installer" in name):
                    download_url = asset.get("browser_download_url", "")
                    break
            if not download_url:
                for asset in gh_data.get("assets", []):
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
    except Exception:
        # GitHub 失败，回退 PyPI
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
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
    """下载最新版本的安装包到下载目录，返回本地文件路径（SSE 流式进度）"""
    import asyncio
    import httpx

    async def download_stream():
        import time
        release_url = ""

        try:
            # 获取最新 Release 信息
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                gh_resp = await client.get(
                    "https://api.github.com/repos/joker-144/Code-Assistant/releases/latest",
                    headers={
                        "User-Agent": "DevAgent-Updater",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                gh_resp.raise_for_status()
                gh_data = gh_resp.json()
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

            total_size = 0
            # 先获取文件大小并检查已下载多少
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                head_resp = await client.head(download_url, headers={"User-Agent": "DevAgent-Updater"})
                if head_resp.status_code == 200:
                    total_size = int(head_resp.headers.get("Content-Length", 0))

            existing_size = dest.stat().st_size if dest.exists() else 0
            if existing_size > 0 and total_size > 0 and existing_size >= total_size:
                # 文件已完整下载
                yield f"data: {json.dumps({'status': 'done', 'message': '文件已存在，跳过下载', 'file_path': str(dest)}, ensure_ascii=False)}\n\n"
                return
            elif existing_size > 0 and total_size > 0:
                yield f"data: {json.dumps({'status': 'info', 'message': f'发现未完成的下载，从 {existing_size/1024/1024:.1f}MB 处续传…'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'info', 'message': f'找到版本 {tag}，开始下载 {file_name}…'}, ensure_ascii=False)}\n\n"

            # 进度报告间隔控制
            last_report = 0.0

            download_client = httpx.AsyncClient(
                timeout=httpx.Timeout(600.0, connect=15.0),
                follow_redirects=True,
                headers={"User-Agent": "DevAgent-Updater"},
            )

            max_retries = 3
            total_downloaded = existing_size

            for attempt in range(max_retries + 1):
                try:
                    headers = {"User-Agent": "DevAgent-Updater"}
                    resume_from = dest.stat().st_size if dest.exists() else 0
                    if resume_from > 0:
                        headers["Range"] = f"bytes={resume_from}-"

                    async with download_client.stream("GET", download_url, headers=headers) as resp:
                        if resp.status_code not in (200, 206):
                            resp.raise_for_status()

                        # 206 = 断点续传
                        if resp.status_code == 206:
                            cr = resp.headers.get("Content-Range", "")
                            if cr:
                                total_size = int(cr.split("/")[-1])

                        open_mode = "ab" if (resp.status_code == 206 and resume_from > 0) else "wb"
                        with open(dest, open_mode) as f:
                            async for chunk in resp.aiter_bytes(chunk_size=65536):
                                f.write(chunk)
                                total_downloaded += len(chunk)
                                now = time.time()
                                if total_size and (now - last_report > 0.5 or total_downloaded >= total_size):
                                    last_report = now
                                    pct = int(total_downloaded * 100 / total_size)
                                    yield f"data: {json.dumps({'status': 'progress', 'message': f'下载中 {total_downloaded//1024//1024}MB / {total_size//1024//1024}MB ({pct}%)', 'percent': pct}, ensure_ascii=False)}\n\n"

                    # 下载成功，跳出重试循环
                    break

                except Exception:
                    if attempt < max_retries:
                        delay = 2 ** attempt
                        yield f"data: {json.dumps({'status': 'info', 'message': f'连接中断，{delay}秒后重试 (第{attempt+1}次)…'}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(delay)
                    else:
                        raise

            await download_client.aclose()
            yield f"data: {json.dumps({'status': 'done', 'message': '下载完成', 'file_path': str(dest)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            err_msg = f"下载失败: {str(e)}"
            if release_url:
                err_msg += f" | 请手动下载: {release_url}"
            yield f"data: {json.dumps({'status': 'error', 'message': err_msg, 'release_url': release_url}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        download_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/version/install")
async def version_install(request: Request):
    """先卸载旧版本（如已安装），再安装新版本。返回 JSON 状态。"""
    import os
    import subprocess
    import winreg

    body = await request.json()
    file_path = body.get("file_path", "")

    if not file_path or not Path(file_path).exists():
        return {"success": False, "error": f"安装包不存在: {file_path}"}

    try:
        uninstalled = False
        uninstall_result = ""

        # 查找已安装的 DevAgent（Inno Setup 注册表项）
        base_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        uninstaller_path = ""
        for hkey_root, subkey_path in base_keys:
            try:
                with winreg.OpenKey(hkey_root, subkey_path) as uninstall_key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(uninstall_key, i)
                            with winreg.OpenKey(uninstall_key, subkey_name) as app_key:
                                try:
                                    display_name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                                    if "DevAgent" in display_name or "dev-agent" in display_name.lower():
                                        try:
                                            uninstaller_path = winreg.QueryValueEx(app_key, "UninstallString")[0]
                                            # UninstallString 通常带引号: "C:\...\unins000.exe"
                                            uninstaller_path = uninstaller_path.strip('"')
                                        except FileNotFoundError:
                                            pass
                                        break
                                except FileNotFoundError:
                                    pass
                            i += 1
                        except OSError:
                            break
                if uninstaller_path:
                    break
            except OSError:
                continue

        # 如果注册表没找到，尝试常见路径
        if not uninstaller_path:
            common_paths = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "DevAgent" / "unins000.exe",
                Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "DevAgent" / "unins000.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "DevAgent" / "unins000.exe",
            ]
            for p in common_paths:
                if p.exists():
                    uninstaller_path = str(p)
                    break

        # 执行卸载
        if uninstaller_path and Path(uninstaller_path).exists():
            proc = subprocess.run(
                [uninstaller_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                capture_output=True, text=True, timeout=120,
            )
            uninstalled = True
            uninstall_result = f"旧版本已卸载 (返回码 {proc.returncode})"

        # 安装新版本
        proc = subprocess.Popen(
            [file_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        msg_parts = []
        if uninstalled:
            msg_parts.append(uninstall_result)
        msg_parts.append("安装程序已启动，应用即将关闭以完成更新。")

        return {
            "success": True,
            "message": " ".join(msg_parts),
            "pid": proc.pid,
            "uninstalled": uninstalled,
        }
    except Exception as e:
        return {"success": False, "error": f"安装失败: {str(e)}"}


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
