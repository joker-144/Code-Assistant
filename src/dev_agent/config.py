"""
DevAgent 配置系统
基于 pydantic-settings，从 .env 和环境变量加载配置
单模型运行时，Provider 可切换（OpenAI 兼容协议）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """DevAgent 全局配置 — 统一从 .env 加载

    所有字段直接从 .env / 环境变量读取，避免嵌套模型的加载问题。
    LLM_* 前缀对应 LLM 配置，MEMORY_* 前缀对应记忆配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM 配置（env_prefix 无，直接用字段名匹配 LLM_API_KEY 等）──
    # pydantic-settings 会自动将字段名大写后匹配环境变量
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.deepseek.com", validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-chat", validation_alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.3, validation_alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=8192, validation_alias="LLM_MAX_TOKENS")
    llm_timeout: float = Field(default=120.0, validation_alias="LLM_TIMEOUT")
    llm_streaming: bool = Field(default=True, validation_alias="LLM_STREAMING")
    llm_max_tool_rounds: int = Field(default=20, validation_alias="LLM_MAX_TOOL_ROUNDS")

    # ── 记忆系统配置 ──
    memory_sqlite_path: str = Field(default="data/memory.db", validation_alias="MEMORY_SQLITE_PATH")
    memory_embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5", validation_alias="MEMORY_EMBEDDING_MODEL"
    )

    # ── Agent 配置 ──
    workspace: Path = Field(default=Path("."), validation_alias="DEV_AGENT_WORKSPACE")
    verbose: bool = Field(default=True, validation_alias="DEV_AGENT_VERBOSE")
    max_context_tokens: int = Field(default=60000, validation_alias="DEV_AGENT_MAX_CONTEXT_TOKENS")
    summary_trigger_tokens: int = Field(
        default=45000, validation_alias="DEV_AGENT_SUMMARY_TRIGGER_TOKENS"
    )

    def validate_api_keys(self) -> list[str]:
        """检查哪些 API Key 缺失"""
        missing = []
        if not self.llm_api_key or "your-" in self.llm_api_key:
            missing.append("LLM (LLM_API_KEY)")
        return missing


_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config


def reset_config():
    """重置配置单例（用于测试）"""
    global _config
    _config = None
