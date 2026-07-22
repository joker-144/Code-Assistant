# Code Review - 代码审查工具

对指定文件夹内的代码进行全面的质量审查和问题检测。

## 任务目标
- 能力：代码规范性检查、潜在Bug检测、性能优化建议、代码可读性评估、生成结构化审查报告
- 触发条件：用户需要审查代码质量、发现潜在Bug、优化代码性能或生成代码审查报告时

## 标准流程

### 1. 执行代码审查
```bash
python scripts/code_reviewer.py --input-dir <path>
```
输出：`review_results.json`

### 2. 生成审查报告
```bash
python scripts/report_generator.py --review-json ./review_results.json --output-dir ./reports
```
输出：`reports/code_review_report.md`

### 3. 查看审查报告

报告包含：
- 概览统计（文件数量、问题总数、各严重性问题分布）
- 严重问题列表（需立即修复）
- 一般问题列表（建议修复）
- 优化建议列表（性能和可读性提升）
- 文件级别的详细分析

## 严重性分级

| 级别 | 说明 | 处理 |
|------|------|------|
| **严重** | 可能导致Bug或安全漏洞 | 立即修复 |
| **一般** | 代码质量问题 | 重构时处理 |
| **优化** | 提升建议 | 按项目进度安排 |

## 可选参数
- `--file-ext .py`：只审查特定类型文件
- `--exclude-dirs tests,node_modules`：排除目录

## 注意事项
- 审查工具使用静态分析方法，可能无法检测运行时问题
- 建议结合单元测试和集成测试进行全面质量保障
- 不同编程语言的检查规则有所差异，详见 `references/review-guidelines.md`
