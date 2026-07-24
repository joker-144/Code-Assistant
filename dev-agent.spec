# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\dev_agent\\cli.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('VERSION', '.'),
        ('web/dist', 'web/dist'),
        ('src/dev_agent/agents', 'dev_agent/agents'),
    ],
    hiddenimports=[
        'httpx', 'fastapi', 'uvicorn', 'packaging',
        'starlette', 'starlette.middleware.cors', 'starlette.routing',
        'websockets', 'watchfiles', 'python-dotenv', 'uvloop',
        'chromadb', 'chromadb.utils.embedding_functions',
        'sentence_transformers', 'tiktoken', 'tiktoken_ext.openai_public', 'tiktoken_ext',
        'dev_agent', 'dev_agent.api', 'dev_agent.config',
        'dev_agent.agent', 'dev_agent.agent.loop', 'dev_agent.agent.system_prompt',
        'dev_agent.core', 'dev_agent.core.observability',
        'dev_agent.memory', 'dev_agent.memory.store',
        'dev_agent.context', 'dev_agent.context.index',
        'dev_agent.desktop',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='dev-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
