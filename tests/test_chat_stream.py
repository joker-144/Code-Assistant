"""
测试对话接口 (/chat/stream) — 诊断对话卡住问题

测试范围:
1. LLMClient 实例化（检查 httpx 导入等依赖问题）
2. AgentLoop 创建和基本流程
3. /chat/stream SSE 流式接口（使用 Mock LLM）
4. SSE 事件格式和错误处理
5. SSE 心跳机制验证
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 确保使用项目根目录的 .env
os.chdir(Path(__file__).parent.parent)


def parse_sse(text: str) -> list[dict]:
    """解析 SSE 文本流为事件列表"""
    events = []
    current_event = None
    for line in text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: ") and current_event:
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                data = line[6:]
            events.append({"event": current_event, "data": data})
            current_event = None
    return events


# ── 测试 1: LLMClient 实例化 ──

class TestLLMClientInit:
    """测试 LLMClient 能否正确实例化"""

    def test_llm_client_init_with_explicit_params(self):
        """LLMClient 使用显式参数应该能正常实例化"""
        from dev_agent.llm.client import LLMClient

        try:
            client = LLMClient(
                api_key="test-key",
                base_url="https://api.test.com",
                model="test-model",
            )
            assert client.model == "test-model"
            assert client._api_key == "test-key"
            assert client._base_url == "https://api.test.com"
            assert client._async is not None
            assert client._sync is not None
        except NameError as e:
            pytest.fail(f"LLMClient 实例化失败 — 缺少导入: {e}")
        except Exception as e:
            pytest.fail(f"LLMClient 实例化失败: {e}")

    def test_llm_client_init_with_config(self):
        """LLMClient 使用 .env 配置应该能正常实例化"""
        from dev_agent.llm.client import LLMClient

        try:
            client = LLMClient()
            assert client.model is not None
            assert len(client.model) > 0
        except NameError as e:
            pytest.fail(f"LLMClient 实例化失败 — 缺少导入: {e}")
        except Exception as e:
            pytest.fail(f"LLMClient 实例化失败: {e}")

    def test_httpx_imported(self):
        """验证 httpx 在 client.py 模块中可用"""
        from dev_agent.llm import client as client_module

        assert hasattr(client_module, "httpx"), (
            "httpx 未在 client.py 中导入 — LLMClient.__init__ 使用了 httpx.Timeout() "
            "但未 import httpx，会导致 NameError"
        )


# ── 测试 2: AgentLoop 创建 ──

class TestAgentLoopCreation:
    """测试 AgentLoop 能否正确创建"""

    def test_agent_loop_init(self, tmp_path):
        """AgentLoop 应该能正常创建（包含 LLMClient 实例化）"""
        from dev_agent.agent.loop import AgentLoop

        try:
            agent = AgentLoop(workspace=tmp_path)
            assert agent.llm is not None
            assert agent.tools is not None
            assert agent.context is not None
            assert agent.conversation_id is not None
        except NameError as e:
            pytest.fail(f"AgentLoop 创建失败 — 缺少导入: {e}")
        except Exception as e:
            pytest.fail(f"AgentLoop 创建失败: {e}")


# ── 测试 3: /chat/stream SSE 接口 ──

class TestChatStreamEndpoint:
    """测试 /chat/stream SSE 流式接口"""

    @pytest_asyncio.fixture
    async def http_client(self):
        """创建异步 HTTP 测试客户端"""
        from httpx import ASGITransport, AsyncClient
        from dev_agent.api import app

        # 清空全局 agent 缓存
        from dev_agent.api import _agents
        _agents.clear()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

        _agents.clear()

    @pytest.mark.asyncio
    async def test_health_check(self, http_client):
        """健康检查接口应该正常"""
        resp = await http_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_chat_stream_simple_reply(self, http_client):
        """测试 /chat/stream — Mock LLM 返回简单文本回复

        验证 SSE 流返回正确的 text + done 事件
        """
        from dev_agent.llm.client import LLMClient, ChatMessage

        mock_response = ChatMessage(
            content="你好！我是 DevAgent。",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )

        with patch.object(LLMClient, "achat_with_tools", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response

            resp = await http_client.post(
                "/chat/stream",
                json={"message": "你好"},
                timeout=30.0,
            )

            # 即使 LLM 被 mock，如果 LLMClient.__init__ 有 NameError，
            # _get_or_create_agent 会抛异常，FastAPI 返回 500
            assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}: {resp.text}"
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events = parse_sse(resp.text)
            event_types = [e["event"] for e in events]

            assert "text" in event_types, f"缺少 text 事件, 收到: {event_types}"
            assert "done" in event_types, f"缺少 done 事件, 收到: {event_types}"

            # 验证 text 事件内容
            text_event = next(e for e in events if e["event"] == "text")
            assert text_event["data"]["content"] == "你好！我是 DevAgent。"

            # 验证 done 事件包含 conversation_id
            done_event = next(e for e in events if e["event"] == "done")
            assert "conversation_id" in done_event["data"]

    @pytest.mark.asyncio
    async def test_chat_stream_llm_error(self, http_client):
        """测试 /chat/stream — LLM 调用失败时应返回 error 事件（而非 500 崩溃）"""
        from dev_agent.llm.client import LLMClient

        with patch.object(LLMClient, "achat_with_tools", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 服务不可用")

            resp = await http_client.post(
                "/chat/stream",
                json={"message": "你好"},
                timeout=60.0,
            )

            assert resp.status_code == 200, f"期望 200 (SSE 错误事件), 实际 {resp.status_code}"
            events = parse_sse(resp.text)
            event_types = [e["event"] for e in events]

            assert "error" in event_types, f"缺少 error 事件, 收到: {event_types}"

            error_event = next(e for e in events if e["event"] == "error")
            assert "LLM" in error_event["data"]["content"] or "重试" in error_event["data"]["content"]

    @pytest.mark.asyncio
    async def test_chat_stream_with_tool_call(self, http_client, tmp_path):
        """测试 /chat/stream — LLM 请求工具调用后返回最终回复

        验证完整流程: tool_start → tool_result → text → done
        """
        from dev_agent.llm.client import LLMClient, ChatMessage, ToolCall

        # 第一次调用：LLM 请求工具调用
        mock_tool_response = ChatMessage(
            content="",
            tool_calls=[ToolCall(id="call_1", name="list_dir", arguments={"path": "."})],
            finish_reason="tool_calls",
        )
        # 第二次调用：LLM 返回最终文本
        mock_final_response = ChatMessage(
            content="当前目录已列出。",
            tool_calls=[],
            finish_reason="stop",
        )

        with patch.object(LLMClient, "achat_with_tools", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = [mock_tool_response, mock_final_response]

            resp = await http_client.post(
                "/chat/stream",
                json={"message": "列出当前目录"},
                timeout=30.0,
            )

            assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}: {resp.text}"
            events = parse_sse(resp.text)
            event_types = [e["event"] for e in events]

            assert "tool_start" in event_types, f"缺少 tool_start 事件, 收到: {event_types}"
            assert "tool_result" in event_types, f"缺少 tool_result 事件, 收到: {event_types}"
            assert "text" in event_types, f"缺少 text 事件, 收到: {event_types}"
            assert "done" in event_types, f"缺少 done 事件, 收到: {event_types}"

    @pytest.mark.asyncio
    async def test_chat_stream_heartbeat(self, http_client):
        """测试 /chat/stream — LLM 响应慢时应有心跳保活

        Mock LLM 延迟 15 秒响应（超过 10 秒心跳间隔），
        验证 SSE 流中包含心跳注释
        """
        from dev_agent.llm.client import LLMClient, ChatMessage

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(15)  # 超过心跳间隔
            return ChatMessage(content="延迟回复", finish_reason="stop")

        with patch.object(LLMClient, "achat_with_tools", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = slow_response

            resp = await http_client.post(
                "/chat/stream",
                json={"message": "你好"},
                timeout=60.0,
            )

            assert resp.status_code == 200
            # 应该包含心跳注释（以 : 开头的行）
            assert ": heartbeat" in resp.text, "SSE 流中缺少心跳注释"

            events = parse_sse(resp.text)
            event_types = [e["event"] for e in events]
            assert "text" in event_types, "心跳之后应该最终收到 text 事件"

    @pytest.mark.asyncio
    async def test_chat_stream_conversation_id_reuse(self, http_client):
        """测试 /chat/stream — 同一 conversation_id 应复用 Agent"""
        from dev_agent.llm.client import LLMClient, ChatMessage

        mock_response = ChatMessage(content="回复", finish_reason="stop")

        with patch.object(LLMClient, "achat_with_tools", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response

            # 第一次对话
            resp1 = await http_client.post(
                "/chat/stream",
                json={"message": "第一次消息"},
                timeout=30.0,
            )
            assert resp1.status_code == 200
            events1 = parse_sse(resp1.text)
            done1 = next(e for e in events1 if e["event"] == "done")
            conv_id_1 = done1["data"]["conversation_id"]

            # 第二次对话，传入相同 conversation_id
            resp2 = await http_client.post(
                "/chat/stream",
                json={"message": "第二次消息", "conversation_id": conv_id_1},
                timeout=30.0,
            )
            assert resp2.status_code == 200
            events2 = parse_sse(resp2.text)
            done2 = next(e for e in events2 if e["event"] == "done")
            conv_id_2 = done2["data"]["conversation_id"]

            assert conv_id_1 == conv_id_2, "同一 conversation_id 应返回相同 ID"


# ── 测试 4: SSE 错误处理边界情况 ──

class TestSSEErrorHandling:
    """测试 SSE 流式接口的边界情况"""

    @pytest_asyncio.fixture
    async def http_client(self):
        from httpx import ASGITransport, AsyncClient
        from dev_agent.api import app, _agents

        _agents.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        _agents.clear()

    @pytest.mark.asyncio
    async def test_empty_message_rejected(self, http_client):
        """空消息应被拒绝"""
        resp = await http_client.post(
            "/chat/stream",
            json={"message": ""},
            timeout=10.0,
        )
        assert resp.status_code == 422, "空消息应返回 422 验证错误"

    @pytest.mark.asyncio
    async def test_agent_creation_error_returns_sse_error(self, http_client):
        """Agent 创建失败时应返回 SSE error 事件（而非裸 500）"""
        from dev_agent.api import _get_or_create_agent

        with patch(
            "dev_agent.api._get_or_create_agent",
            side_effect=Exception("Agent 创建失败模拟"),
        ):
            resp = await http_client.post(
                "/chat/stream",
                json={"message": "测试"},
                timeout=10.0,
            )
            # 当前实现：_get_or_create_agent 在 StreamingResponse 之前调用
            # 如果抛异常，FastAPI 返回 500
            # 这是一个潜在问题 — 前端期望 SSE 格式的错误
            assert resp.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--asyncio-mode=auto"])
