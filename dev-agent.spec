# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 将 dev-agent 打包为单个 .exe 文件
用法: pyinstaller dev-agent.spec
"""

import sys
from pathlib import Path

# 项目根目录
ROOT = Path.cwd()
SRC = ROOT / "src"

# ── 数据文件收集 ──
# web/dist 静态前端文件 -> web/dist
datas = []
web_dist = ROOT / "web" / "dist"
if web_dist.exists():
    for f in web_dist.rglob("*"):
        if f.is_file():
            target_dir = Path("web") / "dist" / f.relative_to(web_dist).parent
            datas.append((str(f), str(target_dir)))

# .env.example
env_example = ROOT / ".env.example"
if env_example.exists():
    datas.append((str(env_example), "_internal"))

# ── 隐藏导入（动态 import 的模块） ──
hidden_imports = [
    # dev-agent 内部动态导入
    "dev_agent.agent.loop",
    "dev_agent.memory.store",
    "dev_agent.context.index",
    # FastAPI 相关
    "fastapi",
    "uvicorn",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # 编码 / 加密
    "tiktoken",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    # Git
    "git",
    "gitdb",
    # pydantic
    "pydantic",
    "pydantic.deprecated",
    # typer/rich
    "typer",
    "rich",
    # httpx
    "httpx",
    "httpcore",
    # 标准库（importlib.metadata 依赖 email）
    "importlib.metadata",
    "email",
    "email.mime",
    "email.mime.text",
    # 通用
    "dotenv",
    "yaml",
    "json",
    "asyncio",
    "uuid",
]

# 排除不需要的模块（减小体积）
excluded_modules = [
    "test",
    "unittest",
    "pytest",
    "setuptools",
    "pip",
    "wheel",
    "distutils",
    "xmlrpc",
    "pdb",
    "doctest",
]

a = Analysis(
    [str(SRC / "dev_agent" / "cli.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="dev-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
