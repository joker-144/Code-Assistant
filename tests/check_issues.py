"""临时诊断脚本：检查删除、工具、技能 API"""
import httpx
c = httpx.Client()

print("=== 健康检查 ===")
r = c.get('http://localhost:8000/health')
print(f"  {r.json()}")

print("\n=== 对话列表 ===")
r = c.get('http://localhost:8000/conversations?limit=5')
data = r.json()
convs = data.get('conversations', [])
print(f"  共 {len(convs)} 条")
if convs:
    cid = convs[0]['id']
    dr = c.delete(f'http://localhost:8000/conversations/{cid}')
    print(f"  删除 {cid[:8]}... 状态: {dr.status_code} body: {dr.text[:100]}")
else:
    print("  无对话可删除")

print("\n=== 工具列表 ===")
r = c.get('http://localhost:8000/api/tools')
data = r.json()
print(f"  状态码: {r.status_code}, count: {data.get('count')}")
if data.get('tools'):
    for t in data['tools'][:5]:
        print(f"    - {t['name']}: {t['description'][:60]}")
else:
    print("  错误:", data.get('error', '未知'))

print("\n=== 技能列表 ===")
r = c.get('http://localhost:8000/api/skills')
data = r.json()
print(f"  状态码: {r.status_code}, count: {data.get('count')}")
if data.get('skills'):
    for s in data['skills']:
        print(f"    - {s['name']}")
else:
    print("  数据:", data)
