"""
诊断测试：复现前端请求 /chat/stream 卡住的问题

用法:
  # 先启动后端
  uvicorn dev_agent.api:app --host 0.0.0.0 --port 8000

  # 用 .env 中的 Key 测试
  python tests/diagnose_chat_stream.py

  # 用指定 Key 测试（模拟前端 settings）
  python tests/diagnose_chat_stream.py --api-key sk-your-key --base-url https://api.deepseek.com
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

from openai import AsyncOpenAI


API_BASE = "http://localhost:8000"
# 不同类型的请求用于复现问题
TEST_CASES = [
    {
        "name": "简单问候（应该秒回）",
        "message": "你好，请用一句话介绍你自己。",
    },
    {
        "name": "中等长度（可能触发工具调用）",
        "message": "请列出当前目录下的文件，并总结项目结构。",
    },
    {
        "name": "复杂推理（可能 30s+）",
        "message": "请用 Python 写一个快速排序算法，并解释时间复杂度。",
    },
]


async def test_direct_llm(args: argparse.Namespace):
    """直接测试 LLM 客户端连接（不经过后端）"""
    print(f"\n{'='*60}")
    print("[DIAG] 直接测试 DeepSeek API 连接")
    print(f"{'='*60}")

    api_key = args.api_key
    base_url = args.base_url

    # 如果没有传 key，从 .env 读
    if not api_key:
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("LLM_CHAT_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        print("[ERROR] 未找到 API Key（请传 --api-key 或在 .env 中设置）")
        return False

    base_url = base_url or "https://api.deepseek.com"

    # 脱敏显示
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else api_key[:4] + "..."
    print(f"[INFO] API Key: {masked_key}  (len={len(api_key)})")
    print(f"[INFO] Base URL: {base_url}/chat/completions")

    try:
        start = time.time()
        client = AsyncOpenAI(api_key=api_key, base_url=base_url,
                             timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0))
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "请只用 OK 回答"}],
            max_tokens=10,
        )
        elapsed = time.time() - start
        content = response.choices[0].message.content or ""
        print(f"[OK]  DeepSeek API 连接成功 ({elapsed:.2f}s)")
        print(f"[OK]  响应: {content[:100]}")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"[FAIL] DeepSeek API 连接失败 ({elapsed:.2f}s)")
        print(f"[FAIL] 错误: {e}")
        # 判断错误类型
        err_str = str(e)
        if "401" in err_str or "authentication" in err_str.lower() or "invalid" in err_str.lower():
            print(f"[FAIL] 原因: API Key 无效，请检查 KEY 是否正确、是否过期")
        elif "429" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower():
            print(f"[FAIL] 原因: 触发速率限制或配额已耗尽")
        elif "timeout" in err_str.lower():
            print(f"[FAIL] 原因: 连接超时（网络或 DeepSeek 服务问题）")
        else:
            print(f"[FAIL] 原因: 请查看上方错误详情")
        return False


async def test_single_case(client: httpx.AsyncClient, case: dict, index: int,
                           settings_payload: dict | None = None) -> dict:
    """测试单个 case，记录每个阶段耗时和事件"""
    print(f"\n{'='*60}")
    print(f"[Test {index}] {case['name']}")
    print(f"[Test {index}] 消息: {case['message']}")
    if settings_payload:
        print(f"[Test {index}] 使用 settings: api_key={settings_payload.get('api_key','')[:8]}...")
    print(f"{'='*60}")

    result = {
        "name": case["name"],
        "success": False,
        "events": [],
        "ttfb": None,
        "total_duration": None,
        "first_event_type": None,
        "last_event_type": None,
        "event_count": 0,
        "text_chars": 0,
        "text_preview": "",
        "error": None,
    }

    # 构建请求体
    payload = {"message": case["message"]}
    if settings_payload:
        payload["settings"] = settings_payload

    start = time.time()
    try:
        async with client.stream(
            "POST",
            f"{API_BASE}/chat/stream",
            json=payload,
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
        ) as response:
            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}"
                print(f"[Test {index}] FAIL HTTP {response.status_code}")
                return result

            print(f"[Test {index}] OK 连接已建立 (HTTP {response.status_code})")
            current_event_type = None
            current_event_data: list[str] = []

            async for chunk in response.aiter_text():
                if not chunk:
                    continue

                if result["ttfb"] is None:
                    result["ttfb"] = time.time() - start
                    print(f"[Test {index}] 首字节 (TTFB): {result['ttfb']:.2f}s")

                for line in chunk.split("\n"):
                    if line.startswith("event: "):
                        current_event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        result["events"].append({
                            "type": current_event_type or "text",
                            "elapsed": time.time() - start,
                            "data_preview": str(data)[:200],
                        })
                        result["event_count"] += 1
                        if result["first_event_type"] is None:
                            result["first_event_type"] = current_event_type or "text"
                        result["last_event_type"] = current_event_type or "text"

                        if current_event_type == "text":
                            result["text_chars"] += len(data.get("content", ""))
                            result["text_preview"] += data.get("content", "")
                        elif current_event_type == "done":
                            print(f"[Test {index}] OK 收到 done 事件 (elapsed={time.time()-start:.2f}s)")
                        elif current_event_type == "error":
                            print(f"[Test {index}] ERROR 收到 error 事件: {data.get('content', '')[:200]}")
                            result["error"] = data.get("content", "")

            result["success"] = result["last_event_type"] == "done"

            # 打印收到的文本内容摘要
            if result["text_preview"]:
                print(f"[Test {index}] 文本响应 ({result['text_chars']}字):")
                print(f"  {result['text_preview'][:300]}")

    except httpx.TimeoutException as e:
        result["error"] = f"TimeoutException: {e}"
        print(f"[Test {index}] TIMEOUT 超时: {e}")
    except httpx.ReadError as e:
        result["error"] = f"ReadError: {e}"
        print(f"[Test {index}] READERR 读取错误: {e}")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        print(f"[Test {index}] EXCEPTION 异常: {e}")
    finally:
        result["total_duration"] = time.time() - start

    print(f"\n[Test {index}] 汇总:")
    print(f"  - 总耗时:       {result['total_duration']:.2f}s")
    print(f"  - 首字节延迟:   {result['ttfb']:.2f}s" if result["ttfb"] else "  - 首字节延迟:   N/A")
    print(f"  - 事件总数:     {result['event_count']}")
    print(f"  - 文本字符数:   {result['text_chars']}")
    print(f"  - 首事件类型:   {result['first_event_type']}")
    print(f"  - 末事件类型:   {result['last_event_type']}")
    print(f"  - 成功:         {'PASS' if result['success'] else 'FAIL'}")

    if result["events"]:
        print(f"  - 事件时间线 (前10):")
        for ev in result["events"][:10]:
            print(f"      [{ev['elapsed']:6.2f}s] {ev['type']:12s} {ev['data_preview'][:80]}")
        if len(result["events"]) > 10:
            print(f"      ... 还有 {len(result['events'])-10} 个事件")

    return result


async def main():
    parser = argparse.ArgumentParser(description="诊断 /chat/stream SSE 接口")
    parser.add_argument("--api-key", help="DeepSeek API Key（模拟前端 settings）")
    parser.add_argument("--base-url", default="https://api.deepseek.com", help="DeepSeek Base URL")
    parser.add_argument("--no-direct-test", action="store_true", help="跳过直连测试")
    args = parser.parse_args()

    # 设置 stdout 编码为 UTF-8
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(f"[DIAG] 诊断 /chat/stream 接口")
    print(f"   API: {API_BASE}")

    # 1. 检查后端是否可达
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{API_BASE}/health")
            if r.status_code != 200:
                print(f"[ERROR] /health 失败: {r.status_code}")
                return
            print(f"[OK] 后端健康检查通过: {r.json()}")
    except Exception as e:
        print(f"[ERROR] 无法连接后端: {e}")
        print(f"   请先启动: uvicorn dev_agent.api:app --host 0.0.0.0 --port 8000")
        return

    # 2. 直连测试 DeepSeek API Key
    key_valid = False
    if not args.no_direct_test:
        key_valid = await test_direct_llm(args)

    # 3. 构建 settings payload（如果有传 key 或 key 有效）
    settings_payload = None
    if args.api_key:
        settings_payload = {"api_key": args.api_key, "base_url": args.base_url}

    # 如果直连失败但没传 --api-key，提示用户
    if not key_valid and not args.api_key and not args.no_direct_test:
        print(f"\n[WARN] .env 中的 API Key 无效。")
        print(f"[WARN] 请传入有效 Key 重试：")
        print(f"    python tests/diagnose_chat_stream.py --api-key sk-your-key")
        print(f"[WARN] 仅测试后端通信（将返回 error 事件）...")

    # 4. 逐个执行 SSE 测试
    results = []
    async with httpx.AsyncClient() as client:
        for i, case in enumerate(TEST_CASES, 1):
            result = await test_single_case(client, case, i, settings_payload)
            results.append(result)
            if i < len(TEST_CASES):
                await asyncio.sleep(2)

    # 5. 总结
    print(f"\n{'='*60}")
    print(f"测试总结")
    print(f"{'='*60}")
    for i, r in enumerate(results, 1):
        status = "PASS" if r["success"] else "FAIL"
        ttfb_str = f"TTFB={r['ttfb']:.2f}s | " if r["ttfb"] else "TTFB=N/A   | "
        print(f"{status} | {r['name']:30s} | "
              f"{ttfb_str}"
              f"Total={r['total_duration']:.2f}s | "
              f"Events={r['event_count']} | "
              f"Chars={r['text_chars']}")
        if r["error"]:
            print(f"         Error: {r['error'][:200]}")

    # 6. 给出诊断结论
    print(f"\n{'='*60}")
    print(f"诊断结论")
    print(f"{'='*60}")
    all_pass = all(r["success"] for r in results)
    if all_pass:
        print("SSE 流式接口工作正常！修复后已无卡住问题。")
    else:
        print("SSE 流式接口仍有问题:")
        for r in results:
            if not r["success"]:
                err = r.get("error", "未知错误")
                if "timeout" in err.lower():
                    print(f"  - 超时错误: {err[:100]}")
                elif "401" in err:
                    print(f"  - API Key 无效: {err[:100]}")
                elif "429" in err or "rate" in err.lower():
                    print(f"  - 速率限制: {err[:100]}")
                else:
                    print(f"  - 其他错误: {err[:100]}")

    if not key_valid and not args.no_direct_test:
        print("\n重要: .env 中的 API Key 后端检测无效，请确保:")
        print("  1. Key 未过期")
        print("  2. Key 未被 revoke")
        print("  3. 账户有余额")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WARN] 用户中断")
        sys.exit(0)
