#!/usr/bin/env python3
"""将审查结果 JSON 转换为 Markdown 报告"""
import argparse
import json
from pathlib import Path
from datetime import datetime


def generate_report(review_json: str, output_dir: str) -> str:
    """生成 Markdown 审查报告"""
    data = json.loads(Path(review_json).read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    issues = data.get("issues", [])

    critical = [i for i in issues if i.get("severity") == "严重"]
    warnings = [i for i in issues if i.get("severity") == "一般"]
    infos = [i for i in issues if i.get("severity") == "优化"]

    lines = [
        "# 代码审查报告",
        f"\n> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n## 概览统计",
        f"\n| 指标 | 数值 |",
        f"|------|------|",
        f"| 扫描文件数 | {summary.get('files_scanned', 0)} |",
        f"| 问题总数 | {summary.get('total_issues', 0)} |",
        f"| 严重问题 | {summary.get('critical', 0)} |",
        f"| 一般问题 | {summary.get('warning', 0)} |",
        f"| 优化建议 | {summary.get('info', 0)} |",
    ]

    if critical:
        lines.append(f"\n## 严重问题（需立即修复）\n")
        for i, issue in enumerate(critical, 1):
            lines.append(f"### {i}. [{issue.get('category', '')}] {issue.get('message', '')}")
            lines.append(f"- **文件**: `{issue.get('file', '')}` 第 {issue.get('line', '')} 行")
            if issue.get("snippet"):
                lines.append(f"- **代码**: `{issue['snippet']}`")
            lines.append("")

    if warnings:
        lines.append(f"\n## 一般问题（建议修复）\n")
        for i, issue in enumerate(warnings, 1):
            lines.append(f"### {i}. [{issue.get('category', '')}] {issue.get('message', '')}")
            lines.append(f"- **文件**: `{issue.get('file', '')}` 第 {issue.get('line', '')} 行")
            if issue.get("snippet"):
                lines.append(f"- **代码**: `{issue['snippet']}`")
            lines.append("")

    if infos:
        lines.append(f"\n## 优化建议\n")
        for i, issue in enumerate(infos, 1):
            lines.append(f"- [{issue.get('category', '')}] {issue.get('message', '')} "
                         f"— `{issue.get('file', '')}:{issue.get('line', '')}`")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="审查报告生成器")
    parser.add_argument("--review-json", default="./review_results.json", help="审查结果 JSON")
    parser.add_argument("--output-dir", default=".", help="报告输出目录")
    args = parser.parse_args()

    report = generate_report(args.review_json, args.output_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "code_review_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"报告已生成: {out_path}")


if __name__ == "__main__":
    main()
