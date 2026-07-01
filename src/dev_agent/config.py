"""
DevAgent 配置系统
基于 pydantic-settings，从 .env 和环境变量加载配置
单模型运行时，Provider 可切换（OpenAI 兼容协议）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM 配置 — 单模型，Provider 可切换

    通过 OpenAI 兼容协议，一行配置即可切换 DeepSeek / Qwen / OpenAI / Claude
    """
    model_config = SettingsConfigDict(env_prefix="LLM_")

    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout: float = 120.0

    # 流式输出
    streaming: bool = True

    # Function Calling 最大轮数（AgentLoop 中限制工具调用循环次数）
    max_tool_rounds: int = 20


class MemoryConfig(BaseSettings):
    """记忆系统配置 — SQLite 统一本地存储"""
    model_config = SettingsConfigDict(env_prefix="MEMORY_")

    sqlite_path: str = "data/memory.db"
    # 本地 Embedding 模型（sentence-transformers）
    embedding_model: str = "BAAI/bge-small-zh-v1.5"


class AgentConfig(BaseSettings):
    """DevAgent 全局配置"""
    model_config = SettingsConfigDict(
        env_prefix="DEV_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = LLMConfig()
    memory: MemoryConfig = MemoryConfig()

    workspace: Path = Path(".")
    verbose: bool = True
    max_context_tokens: int = 60000
    summary_trigger_tokens: int = 45000

    def validate_api_keys(self) -> list[str]:
        """检查哪些 API Key 缺失"""
        missing = []
        if not self.llm.api_key or "your-" in self.llm.api_key:
            missing.append("LLM (LLM_API_KEY)")
        return missing


_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config
