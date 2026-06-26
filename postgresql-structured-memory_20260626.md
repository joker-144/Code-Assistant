# 结构化记忆 + 向量库协作 — 完成

**时间**：2026-06-26 10:40

## 决策

用户指出记忆功能应该是"结构化记忆 + 向量库"协作而非各自独立。已将 MemorySystem 升级为**双写 + 混合检索**架构。

## 核心改动（`structured.py`）

### 从独立查询 → 混合检索

**改前**：
- PostgreSQL 和 ChromaDB 各自独立查询，需要调用方手动组合
- `find_similar_tasks()` 用 ILIKE 文本匹配（不准）
- `recall()` 纯语义搜索（没有结构化过滤，可能返回无关类型）

**改后 — 三个核心能力**：

**1. 双写（remember_task / remember_code）**
```
一次调用 → 同时落地 PostgreSQL（结构化字段）和 ChromaDB（embedding）
关联键：task.id = "task:{task_id}" 横跨两层
```

**2. 混合检索（hybrid_search）— 三步流水线**
```
Step 1: PostgreSQL 结构化过滤
  SELECT * FROM tasks WHERE request_type='code_gen' AND verdict='passed'
  → 精确按类型/状态/模型/时间过滤 → 候选集（如 200 条）

Step 2: ChromaDB 语义重排
  对候选集的 task.id 从向量库取 embedding
  和 query embedding 计算 cosine 相似度
  取 top_k 最相关的

Step 3: 拼回 PostgreSQL 结构化字段
  返回: [{request, type, verdict, score, cost, ..., _semantic_score: 0.94}, ...]
```

**3. 降级策略**
```
PostgreSQL + ChromaDB 都可用 → 混合检索
只有 PostgreSQL → ILIKE 文本匹配
只有 ChromaDB → 纯语义搜索
都挂了 → 空列表（不 crash）
```

### MemorySystem 对外 API

| 方法 | 走哪层 | 场景 |
|------|--------|------|
| `remember_task(task)` | 双写 PG+Chroma | 每次任务结束记录 |
| `remember_code(file, code)` | 双写 PG+Chroma | 项目扫描时索引代码 |
| `remember_lesson(text, tags)` | ChromaDB | 记录经验教训 |
| `hybrid_search(q, filter_*, days, top_k)` | PG过滤+Chroma排序 | 🔥 主要查询方式 |
| `recall(q, top_k)` | ChromaDB | 纯语义搜索 |
| `recall_code(q, top_k)` | ChromaDB | 代码片段搜索 |
| `get_best_worker(type, days)` | PostgreSQL | 智能路由 |
| `get_daily_report()` | PostgreSQL | 性能仪表盘 |
| `get_failed_tasks(hours)` | PostgreSQL | 失败追踪 |
| `add_message(role, content)` | 内存 | 对话上下文 |
| `summary()` | 全部 | 记忆系统状态 |
