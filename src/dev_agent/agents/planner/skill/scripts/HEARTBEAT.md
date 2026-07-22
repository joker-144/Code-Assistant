# Self-Improving — HEARTBEAT.md（工作区集成用）

将此文件复制到工作区的 AGENTS.md 或 .github/AGENTS.md 中以启用 heartbeat 检查。

```
# DevAgent — Self-Improving Heartbeat

## 触发器
- 每次 Agent 启动/唤醒时
- 每次任务完成后

## 检查项
1. 是否存在 `~/self-improving/memory.md`？
2. 是否存在 `~/self-improving/corrections.md`？
3. 最近一次心跳时间？

## 自动操作
- 加载 HOT 记忆 (memory.md)
- 检查最近 feedback (corrections.md 最后10条)
- 更新 heartbeat-state.md
```
