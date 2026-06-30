# Self-Improving Agent

来源: SkillHub (原作者: pskoett) | 68.1万次下载 | v3.0.21

## 概述

捕获经验教训、错误和纠正，以实现持续改进。适用场景：
- 命令或操作意外失败
- 用户纠正了某行为
- 发现更好的处理方式
- 知识已过时

## 快速参考

| 情况 | 行动 |
|------|------|
| 命令/操作失败 | 记录到 `.learnings/ERRORS.md` |
| 用户纠正你 | 记录到 `.learnings/LEARNINGS.md`，类别 `correction` |
| 用户想要缺失功能 | 记录到 `.learnings/FEATURE_REQUESTS.md` |
| API/外部工具失败 | 记录到 `.learnings/ERRORS.md`，附带集成细节 |
| 知识已过时 | 记录到 `.learnings/LEARNINGS.md`，类别 `knowledge_gap` |
| 发现更好方法 | 记录到 `.learnings/LEARNINGS.md`，类别 `best_practice` |
| 广泛适用的学习 | 提升到 `AGENTS.md` 或 `CLAUDE.md` |

## 记录格式

### 学习条目

追加到 `.learnings/LEARNINGS.md`：

```
## [LRN-YYYYMMDD-NNN] 简短标题
**类别**：correction | knowledge_gap | best_practice
**上下文**：发生了什么
**学到什么**：具体的改进点
**来源**：用户反馈 | 代码审查 | 错误分析
**优先级**：high | medium | low
```

### 错误条目

追加到 `.learnings/ERRORS.md`：

```
## [ERR-YYYYMMDD-NNN] 错误描述
**命令**：执行了什么命令
**错误信息**：完整的错误输出
**根因**：为什么失败
**修复**：如何解决
**预防**：如何避免再次发生
```

## 工作流

1. 当错误或纠正发生时，立即记录
2. 定期审查学习记录，将广泛适用的条目提升到项目记忆
3. 在开始新任务前，回顾相关学习记录