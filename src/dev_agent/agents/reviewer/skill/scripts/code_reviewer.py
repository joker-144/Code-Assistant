#!/usr/bin/env python3
"""代码审查工具 — 静态分析代码质量、Bug检测、性能优化建议"""
import argparse
import json
import os
import re
from pathlib import Path

SEVERITY_CRITICAL = "严重"
SEVERITY_WARNING = "一般"
SEVERITY_INFO = "优化"

ISSUE_CHECKS = [
    # (pattern, message, severity, category)
    (r"console\.(log|warn|error)", "使用 console.log 而非统一日志库", SEVERITY_WARNING, "代码质量"),
    (r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']+[\"']", "硬编码敏感信息", SEVERITY_CRITICAL, "安全"),
    (r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']+[\"']", "硬编码敏感信息", SEVERITY_CRITICAL, "安全"),
    (r"except\s*:", "裸露的 except 语句，缺少异常类型", SEVERITY_WARNING, "错误处理"),
    (r"(sql|execute)\s*\(?\s*[\"'].*%\s", "可能存在 SQL 注入风险", SEVERITY_CRITICAL, "安全"),
    (r"#\s*TODO", "未完成的 TODO 注释", SEVERITY_INFO, "代码质量"),
    (r"import\s+\*\s+from", "使用 import * 导入，污染命名空间", SEVERITY_WARNING, "导入规范"),
    (r"\.innerHTML\s*=", "使用 innerHTML 可能存在 XSS 风险", SEVERITY_CRITICAL, "安全"),
    (r"os\.system\(", "使用 os.system()，建议用 subprocess", SEVERITY_WARNING, "安全"),
    (r"eval\(", "使用 eval()，存在安全风险", SEVERITY_CRITICAL, "安全"),
    (r"pass\s*$", "空语句块，可能未完成实现", SEVERITY_INFO, "代码完整性"),
    (r"return\s+None\s*$", "return None 可省略为 return", SEVERITY_INFO, "代码风格"),
]


def analyze_file(filepath: Path) -> list[dict]:
    """分析单个文件"""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")
    except Exception:
        return [{"file": str(filepath), "line": 0, "error": "无法读取文件"}]

    for i, line in enumerate(lines, 1):
        for pattern, message, severity, category in ISSUE_CHECKS:
            if re.search(pattern, line, re.IGNORECASE):
                # 去重：同一行同类型问题只报一次
                if not any(iss["line"] == i and iss["message"] == message for iss in issues):
                    issues.append({
                        "file": str(filepath), "line": i, "severity": severity,
                        "category": category, "message": message,
                        "snippet": line.strip()[:120],
                    })
    return issues


def scan_directory(input_dir: str, file_ext: str = None, exclude_dirs: str = None) -> dict:
    """扫描目录"""
    root = Path(input_dir)
    if not root.exists():
        return {"error": f"目录不存在: {input_dir}"}

    exclusions = set(d.strip() for d in (exclude_dirs or "").split(",") if d.strip())
    exclusions.update({"node_modules", ".git", "__pycache__", ".venv", "dist", "build"})

    all_issues = []
    files_scanned = 0

    for filepath in root.rglob("*"):
        if filepath.is_dir() and filepath.name in exclusions:
            continue
        if filepath.is_file():
            ext = filepath.suffix
            if file_ext and ext != file_ext:
                continue
            if ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rs", ".rb"):
                issues = analyze_file(filepath)
                if issues:
                    all_issues.extend(issues)
                files_scanned += 1

    critical = sum(1 for i in all_issues if i.get("severity") == SEVERITY_CRITICAL)
    warnings = sum(1 for i in all_issues if i.get("severity") == SEVERITY_WARNING)
    infos = sum(1 for i in all_issues if i.get("severity") == SEVERITY_INFO)

    return {
        "summary": {
            "files_scanned": files_scanned,
            "total_issues": len(all_issues),
            "critical": critical,
            "warning": warnings,
            "info": infos,
        },
        "issues": all_issues,
    }


def main():
    parser = argparse.ArgumentParser(description="代码审查工具")
    parser.add_argument("--input-dir", required=True, help="要审查的文件夹路径")
    parser.add_argument("--file-ext", default=None, help="只审查指定扩展名（如 .py）")
    parser.add_argument("--exclude-dirs", default=None, help="排除目录（逗号分隔）")
    parser.add_argument("--output", default="review_results.json", help="输出文件路径")
    args = parser.parse_args()

    results = scan_directory(args.input_dir, args.file_ext, args.exclude_dirs)

    out_path = Path(args.output)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = results["summary"]
    print(f"审查完成: {summary['files_scanned']} 个文件, "
          f"{summary['total_issues']} 个问题 (严重:{summary['critical']}, "
          f"一般:{summary['warning']}, 优化:{summary['info']})")
    print(f"结果保存到: {out_path}")


if __name__ == "__main__":
    main()
