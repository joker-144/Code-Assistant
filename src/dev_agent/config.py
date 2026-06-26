"""
DevAgent 配置系统
基于 pydantic-settings，从 .env 和环境变量加载所有配置
支持数据库后端可替换（SQLite / PostgreSQL / Milvus / ChromaDB）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeepSeekConfig(BaseSettings):
    """DeepSeek-V4-Pro 配置 — 大脑规划 + 代码生成 + 仲裁"""
    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_")
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"


class QwenConfig(BaseSettings):
    """Qwen-Plus 配置 — 代码审查（便宜、JSON 输出稳定）"""
    model_config = SettingsConfigDict(env_prefix="QWEN_")
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-plus"


class MemoryConfig(BaseSettings):
    """记忆系统配置 — 支持 SQLite/PostgreSQL + Milvus/ChromaDB 可替换"""
    model_config = SettingsConfigDict(env_prefix="MEMORY_")

    # 结构化记忆 — SQLite（默认）或 PostgreSQL
    sqlite_path: str = "data/memory.db"
    postgres_dsn: str = ""  # 非空时优先使用 PostgreSQL

    # 向量记忆 — Milvus（默认）或 ChromaDB
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "dev_agent_memory"
    # ChromaDB 备用
    chroma_persist_dir: str = "data/chroma"

    embedding_dim: int = 1536


class AgentConfig(BaseSettings):
    """DevAgent 全局配置"""
    model_config = SettingsConfigDict(
        env_prefix="DEV_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek: DeepSeekConfig = DeepSeekConfig()
    qwen: QwenConfig = QwenConfig()
    memory: MemoryConfig = MemoryConfig()

    workspace: Path = Path("workspace")
    max_retries: int = 3
    verbose: bool = True
    max_context_tokens: int = 60000
    summary_trigger_tokens: int = 45000

    def validate_api_keys(self) -> list[str]:
        """检查哪些 API Key 缺失"""
        missing = []
        if not self.deepseek.api_key or "your-" in self.deepseek.api_key:
            missing.append("DeepSeek-V4-Pro (DEEPSEEK_API_KEY)")
        if not self.qwen.api_key or "your-" in self.qwen.api_key:
            missing.append("Qwen-Plus (QWEN_API_KEY)")
        return missing


_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config