"""
DevAgent 智能体功能综合测试

测试范围：
  1. 健康检查 / 基础接口
  2. 对话管理（创建/列表/消息）
  3. SSE 流式对话（简单问答）
  4. SSE 流式对话（工具调用：文件读写）
  5. SSE 流式对话（工具调用：Shell 命令）
  6. SSE 流式对话（代码搜索）
  7. 多轮对话上下文保持
  8. 记忆系统
  9. 用户配置管理
 10. 错误处理（空消息/无效对话ID）

用法:
  python tests/test_agent_features.py
  python tests/test_agent_features.py --api-key sk-xxx
  python tests/test_agent_features.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# 修复 Windows 终端编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 测试结果数据结构 ──

@dataclass
class TestResult:
    name: str
    passed: bool
    score: float  # 0-10
    duration: float = 0.0
    details: str = ""
    suggestions: list[str] = field(default_factory=list)


@dataclass
class SSEEvent:
    type: str  # tool_start / tool_result / text / error / done
    data: dict


# ── SSE 客户端 ──

def parse_sse_stream(response: httpx.Response) -> list[SSEEvent]:
    """解析 SSE 流，返回事件列表"""
    events: list[SSEEvent] = []
    current_event: str | None = None
    buffer = ""

    for chunk in response.iter_text():
        buffer += chunk
        lines = buffer.split("\n")
        buffer = lines.pop() or ""

        for line in lines:
            line = line.strip()
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: ") and current_event:
                try:
                    data = json.loads(line[6:])
                    events.append(SSEEvent(type=current_event, data=data))
                except json.JSONDecodeError:
                    pass
                current_event = None
            elif line.startswith(": heartbeat"):
                pass  # 忽略心跳

    return events


# ── 测试类 ──

class AgentTester:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=120.0)
        self.conversation_id: str | None = None
        self.results: list[TestResult] = []

    def run_all(self):
        """运行所有测试"""
        print("=" * 70)
        print("  DevAgent 智能体功能综合测试")
        print(f"  API: {self.base_url}")
        print("=" * 70)

        # 先配置 API Key
        if self.api_key:
            self._configure_api_key()

        tests = [
            ("1. 健康检查与基础接口", self.test_health),
            ("2. 对话管理（创建/列表）", self.test_conversation_management),
            ("3. SSE 流式对话 — 简单问答", self.test_simple_chat),
            ("4. SSE 流式对话 — 文件读取工具", self.test_file_read_tool),
            ("5. SSE 流式对话 — Shell 命令工具", self.test_shell_tool),
            ("6. SSE 流式对话 — 代码搜索", self.test_code_search),
            ("7. 多轮对话上下文保持", self.test_multi_turn_context),
            ("8. 记忆系统统计", self.test_memory_stats),
            ("9. 用户配置管理", self.test_user_settings),
            ("10. 错误处理", self.test_error_handling),
        ]

        for name, func in tests:
            print(f"\n{'─' * 70}")
            print(f"[{name}]")
            print(f"{'─' * 70}")
            try:
                func()
            except Exception as e:
                self._record(name, passed=False, score=0, details=f"异常: {e}", suggestions=[
                    "检查后端服务是否正常运行",
                    f"异常类型: {type(e).__name__}",
                ])
                traceback.print_exc()

        self._print_summary()

    def _configure_api_key(self):
        """通过 /api/user-settings 写入 API Key"""
        print(f"  配置 API Key: {self.api_key[:8]}...{self.api_key[-4:]}")
        settings = {
            "provider": "deepseek",
            "apiKeys": {"deepseek": self.api_key},
            "baseUrl": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "temperature": 0.3,
            "maxTokens": 8192,
        }
        r = self.client.post(f"{self.base_url}/api/user-settings", json=settings)
        if r.status_code == 200:
            print("  ✅ API Key 配置成功")
        else:
            print(f"  ⚠️ API Key 配置失败: HTTP {r.status_code}")

    def _send_chat(self, message: str, conv_id: str | None = None) -> tuple[list[SSEEvent], float, float]:
        """发送聊天消息，返回 (事件列表, TTFB, 总耗时)"""
        body = {"message": message}
        if conv_id:
            body["conversation_id"] = conv_id

        t0 = time.time()
        ttfb = 0.0

        with self.client.stream("POST", f"{self.base_url}/chat/stream", json=body) as r:
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.read().text[:200]}")

            events = []
            current_event = None
            buffer = ""

            for chunk in r.iter_text():
                if ttfb == 0.0:
                    ttfb = time.time() - t0

                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop() or ""

                for line in lines:
                    line = line.strip()
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: ") and current_event:
                        try:
                            data = json.loads(line[6:])
                            events.append(SSEEvent(type=current_event, data=data))
                            if current_event == "done":
                                current_event = None
                        except json.JSONDecodeError:
                            pass
                        current_event = None

        total = time.time() - t0
        return events, ttfb, total

    def _extract_text(self, events: list[SSEEvent]) -> str:
        """从事件列表中提取所有文本回复"""
        return "".join(e.data.get("content", "") for e in events if e.type == "text")

    def _extract_tools(self, events: list[SSEEvent]) -> list[dict]:
        """从事件列表中提取工具调用记录"""
        tools = []
        current_tool = None
        for e in events:
            if e.type == "tool_start":
                current_tool = {"name": e.data.get("tool", ""), "args": e.data.get("args", {}), "result": ""}
                tools.append(current_tool)
            elif e.type == "tool_result":
                if current_tool:
                    current_tool["result"] = e.data.get("content", "")[:200]
        return tools

    def _has_error(self, events: list[SSEEvent]) -> str | None:
        """检查是否有错误事件"""
        for e in events:
            if e.type == "error":
                return e.data.get("content", "")
        return None

    def _get_conv_id(self, events: list[SSEEvent]) -> str | None:
        """从 done 事件提取 conversation_id"""
        for e in events:
            if e.type == "done":
                return e.data.get("conversation_id")
        return None

    def _record(self, name: str, passed: bool, score: float, duration: float = 0,
                details: str = "", suggestions: list[str] | None = None):
        r = TestResult(name=name, passed=passed, score=score, duration=duration,
                       details=details, suggestions=suggestions or [])
        self.results.append(r)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  结果: {status} | 评分: {score:.1f}/10 | 耗时: {duration:.1f}s")
        if details:
            print(f"  详情: {details}")
        if r.suggestions:
            print("  建议:")
            for s in r.suggestions:
                print(f"    - {s}")

    # ── 测试用例 ──

    def test_health(self):
        """测试 1: 健康检查"""
        t0 = time.time()
        r = self.client.get(f"{self.base_url}/health")
        dt = time.time() - t0

        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "ok":
                self._record("健康检查", True, 10, dt, f"version={data.get('version', '?')}")
            else:
                self._record("健康检查", False, 5, dt, f"status={data.get('status')}")
        else:
            self._record("健康检查", False, 0, dt, f"HTTP {r.status_code}")

    def test_conversation_management(self):
        """测试 2: 对话管理"""
        t0 = time.time()

        # 创建对话
        r = self.client.post(f"{self.base_url}/conversations", json={"title": "测试对话"})
        if r.status_code != 200:
            self._record("对话管理", False, 0, time.time() - t0, f"创建失败: HTTP {r.status_code}")
            return

        conv = r.json()
        conv_id = conv.get("id", "")

        # 列表查询
        r2 = self.client.get(f"{self.base_url}/conversations?limit=20")
        if r2.status_code != 200:
            self._record("对话管理", False, 3, time.time() - t0, "列表查询失败")
            return

        convs = r2.json().get("conversations", [])
        found = any(c.get("id") == conv_id for c in convs)

        # 查询消息
        r3 = self.client.get(f"{self.base_url}/conversations/{conv_id}/messages")
        if r3.status_code == 200 and found:
            self._record("对话管理", True, 9, time.time() - t0,
                         f"创建+列表+消息查询均正常, conv_id={conv_id[:8]}...")
        else:
            self._record("对话管理", False, 5, time.time() - t0,
                         f"消息查询失败: HTTP {r3.status_code}, 列表包含={found}")

    def test_simple_chat(self):
        """测试 3: 简单问答"""
        events, ttfb, total = self._send_chat("你好，请用一句话介绍你自己。")
        text = self._extract_text(events)
        err = self._has_error(events)
        self.conversation_id = self._get_conv_id(events)

        if err:
            self._record("简单问答", False, 0, total, f"错误: {err}", ["检查 API Key 是否有效"])
        elif len(text) > 10:
            score = 10 if ttfb < 5 else 8
            self._record("简单问答", True, score, total,
                         f"TTFB={ttfb:.1f}s, 回复={len(text)}字, 事件数={len(events)}")
        else:
            self._record("简单问答", False, 3, total,
                         f"回复过短: '{text}'", ["检查 LLM 是否正常响应"])

    def test_file_read_tool(self):
        """测试 4: 文件读取工具调用"""
        events, ttfb, total = self._send_chat(
            "请读取 .env 文件，告诉我里面配置了什么模型。",
            conv_id=self.conversation_id
        )
        text = self._extract_text(events)
        tools = self._extract_tools(events)
        err = self._has_error(events)

        if err:
            self._record("文件读取工具", False, 0, total, f"错误: {err}")
            return

        has_read_tool = any("read" in t["name"].lower() or "file" in t["name"].lower() for t in tools)
        if has_read_tool and len(text) > 20:
            score = 10 if len(tools) <= 4 else 7
            self._record("文件读取工具", True, score, total,
                         f"工具调用={len(tools)}次, 回复={len(text)}字, TTFB={ttfb:.1f}s",
                         [] if score >= 9 else ["减少不必要的工具调用轮次"])
        else:
            self._record("文件读取工具", False, 4, total,
                         f"未检测到文件读取工具, 工具数={len(tools)}, 回复长度={len(text)}",
                         ["检查 read_file 工具是否注册"])

    def test_shell_tool(self):
        """测试 5: Shell 命令工具调用"""
        events, ttfb, total = self._send_chat(
            "请执行 echo 'hello from test' 命令，告诉我输出结果。",
            conv_id=self.conversation_id
        )
        text = self._extract_text(events)
        tools = self._extract_tools(events)
        err = self._has_error(events)

        if err:
            self._record("Shell 命令工具", False, 0, total, f"错误: {err}")
            return

        has_shell = any(
            t["name"] == "run_command" or
            "shell" in t["name"].lower() or
            "exec" in t["name"].lower() or
            "bash" in t["name"].lower() or
            "command" in t["name"].lower()
            for t in tools
        )
        if has_shell and "hello" in text.lower():
            self._record("Shell 命令工具", True, 10, total,
                         f"工具={len(tools)}次, 回复包含正确结果, TTFB={ttfb:.1f}s")
        elif has_shell:
            self._record("Shell 命令工具", True, 7, total,
                         f"工具已调用但回复未包含预期结果, 回复={text[:100]}",
                         ["检查 Shell 工具输出解析"])
        else:
            self._record("Shell 命令工具", False, 3, total,
                         f"未检测到 Shell 工具调用, 工具数={len(tools)}",
                         ["检查 run_command 工具是否注册"])

    def test_code_search(self):
        """测试 6: 代码搜索"""
        events, ttfb, total = self._send_chat(
            "在项目中搜索包含 'FastAPI' 的文件，列出文件路径。",
            conv_id=self.conversation_id
        )
        text = self._extract_text(events)
        tools = self._extract_tools(events)
        err = self._has_error(events)

        if err:
            self._record("代码搜索", False, 0, total, f"错误: {err}")
            return

        has_search = any(
            "search" in t["name"].lower() or
            "grep" in t["name"].lower() or
            "glob" in t["name"].lower() or
            "list_dir" in t["name"].lower()
            for t in tools
        )
        if has_search and len(text) > 10:
            self._record("代码搜索", True, 9, total,
                         f"搜索工具={len(tools)}次, 回复={len(text)}字")
        else:
            # 可能 LLM 用 run_command 替代了搜索
            has_cmd = any(
                t["name"] == "run_command" or
                "command" in t["name"].lower() or
                "shell" in t["name"].lower()
                for t in tools
            )
            if has_cmd and len(text) > 10:
                self._record("代码搜索", True, 6, total,
                             f"使用 run_command 替代专用搜索工具, 工具={len(tools)}次",
                             ["建议优先使用 search_code 工具而非 run_command"])
            else:
                self._record("代码搜索", False, 3, total,
                             f"未检测到搜索行为, 工具数={len(tools)}",
                             ["检查搜索工具是否可用", "可能需要先运行项目索引: POST /index"])

    def test_multi_turn_context(self):
        """测试 7: 多轮对话上下文"""
        # 第一轮
        events1, _, total1 = self._send_chat(
            "记住我的名字叫'测试用户'，不要做别的，确认收到即可。",
            conv_id=self.conversation_id
        )
        text1 = self._extract_text(events1)
        err1 = self._has_error(events1)
        self.conversation_id = self._get_conv_id(events1) or self.conversation_id

        if err1 or not self.conversation_id:
            self._record("多轮对话上下文", False, 0, total1, f"第一轮失败: {err1}")
            return

        # 第二轮：验证上下文
        events2, _, total2 = self._send_chat(
            "我刚才告诉你我叫什么名字？",
            conv_id=self.conversation_id
        )
        text2 = self._extract_text(events2)
        total = total1 + total2

        if "测试用户" in text2:
            self._record("多轮对话上下文", True, 10, total,
                         f"第二轮正确回忆了上下文, 回复={text2[:80]}")
        else:
            self._record("多轮对话上下文", False, 4, total,
                         f"第二轮未能回忆上下文, 回复={text2[:100]}",
                         ["检查 Agent 上下文窗口是否正确传递历史消息",
                          "检查 conversation_id 复用逻辑"])

    def test_memory_stats(self):
        """测试 8: 记忆系统"""
        t0 = time.time()
        r = self.client.get(f"{self.base_url}/memory/stats")
        dt = time.time() - t0

        if r.status_code == 200:
            data = r.json()
            # 检查返回结构
            has_fields = any(k in data for k in ("conversations", "messages", "embeddings", "total"))
            if has_fields:
                self._record("记忆系统", True, 9, dt, f"stats={json.dumps(data, ensure_ascii=False)[:150]}")
            else:
                self._record("记忆系统", True, 6, dt, f"返回结构不完整: {data}",
                             ["建议统一 stats 返回字段"])
        else:
            self._record("记忆系统", False, 0, dt, f"HTTP {r.status_code}")

    def test_user_settings(self):
        """测试 9: 用户配置管理"""
        t0 = time.time()
        # 读取配置
        r = self.client.get(f"{self.base_url}/api/user-settings")
        dt = time.time() - t0

        if r.status_code == 200:
            data = r.json()
            has_provider = "provider" in data
            has_api_keys = "apiKeys" in data
            if has_provider or has_api_keys:
                self._record("用户配置管理", True, 9, dt,
                             f"配置读取正常, provider={data.get('provider', '?')}",
                             [] if has_provider and has_api_keys else ["建议返回完整字段"])
            else:
                self._record("用户配置管理", True, 5, dt, f"返回字段不完整: {list(data.keys())}")
        else:
            self._record("用户配置管理", False, 0, dt, f"HTTP {r.status_code}")

    def test_error_handling(self):
        """测试 10: 错误处理"""
        t0 = time.time()
        # 空消息应该被 pydantic 拒绝
        r = self.client.post(f"{self.base_url}/chat/stream", json={"message": ""})
        dt = time.time() - t0

        if r.status_code == 422:
            self._record("错误处理", True, 10, dt, "空消息正确返回 422 验证错误")
        else:
            self._record("错误处理", False, 4, dt,
                         f"空消息应返回 422, 实际返回 {r.status_code}",
                         ["添加 min_length=1 校验"])

    # ── 汇总报告 ──

    def _print_summary(self):
        print("\n" + "=" * 70)
        print("  测试汇总报告")
        print("=" * 70)

        total_score = 0
        max_score = 0
        passed_count = 0

        print(f"\n{'测试项':<30} {'状态':<8} {'评分':<10} {'耗时':<10} {'说明'}")
        print("─" * 100)

        for r in self.results:
            total_score += r.score
            max_score += 10
            if r.passed:
                passed_count += 1
            status = "✅" if r.passed else "❌"
            print(f"{r.name:<30} {status:<8} {r.score:.1f}/10    {r.duration:.1f}s      {r.details[:40]}")

        print("─" * 100)
        avg = total_score / max_score * 10 if max_score > 0 else 0
        print(f"\n  通过: {passed_count}/{len(self.results)} | 总分: {total_score:.1f}/{max_score} | 平均分: {avg:.1f}/10")

        # 评级
        if avg >= 9:
            grade = "A (优秀)"
        elif avg >= 7:
            grade = "B (良好)"
        elif avg >= 5:
            grade = "C (合格)"
        else:
            grade = "D (不合格)"
        print(f"  评级: {grade}")

        # 修改建议汇总
        all_suggestions = []
        for r in self.results:
            if not r.passed or r.suggestions:
                for s in r.suggestions:
                    all_suggestions.append(f"[{r.name}] {s}")

        if all_suggestions:
            print(f"\n{'─' * 70}")
            print("  修改建议汇总:")
            print("─" * 70)
            for s in all_suggestions:
                print(f"  • {s}")

        print(f"\n{'=' * 70}")
        print("  测试完成")
        print(f"{'=' * 70}")


# ── 入口 ──

def main():
    parser = argparse.ArgumentParser(description="DevAgent 智能体功能综合测试")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")
    parser.add_argument("--api-key", default="", help="DeepSeek API Key（会自动写入 .env）")
    args = parser.parse_args()

    tester = AgentTester(base_url=args.base_url, api_key=args.api_key)
    tester.run_all()


if __name__ == "__main__":
    main()
