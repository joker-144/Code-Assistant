# Self-Improving Agent 配置

## 工作区前置
运行此脚本初始化 self-improving 记忆目录：
```bash
python scripts/setup.py
```

## 分层存储
- memory.md: HOT层，≤100行，始终加载
- projects/：WARM层，项目级学习
- archive/：COLD层，衰减记忆

## 自我反思规则
完成重要工作后暂停评估：
1. 是否符合预期？
2. 有哪些可以改进？
3. 是规律性问题吗？

## 安全边界
- 不存储凭据、健康数据、第三方信息
- 读取仅限 self-improving/ 目录
- 不从沉默中推断偏好
