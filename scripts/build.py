#!/usr/bin/env python3
"""
DevAgent 构建与发布脚本

用法:
  python scripts/build.py build        构建 wheel + sdist
  python scripts/build.py test-install 本地安装测试
  python scripts/build.py publish      发布到 PyPI
  python scripts/build.py clean        清理构建产物
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(cmd: list[str], **kwargs) -> int:
    """运行命令并实时输出"""
    print(f"\033[36m$ {' '.join(cmd)}\033[0m")
    result = subprocess.run(cmd, cwd=str(ROOT), **kwargs)
    if result.returncode != 0:
        print(f"\033[31m命令失败，退出码: {result.returncode}\033[0m")
        sys.exit(result.returncode)
    return result.returncode


def clean() -> None:
    """清理构建产物"""
    for name in ["dist", "build", "*.egg-info"]:
        for path in ROOT.glob(name):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  已删除: {path}")
            elif path.is_file():
                path.unlink()
                print(f"  已删除: {path}")
    # 清理 __pycache__
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    print("\033[32m清理完成\033[0m")


def build() -> None:
    """构建 wheel + sdist"""
    run([sys.executable, "-m", "build", "--wheel", "--sdist"])
    print()
    print("\033[32m构建完成!\033[0m")
    for f in sorted(ROOT.glob("dist/*")):
        size = f.stat().st_size
        print(f"  {f.name}  ({size / 1024:.1f} KB)")


def test_install() -> None:
    """本地安装测试（先卸载再安装 whl）"""
    whl_files = sorted(ROOT.glob("dist/*.whl"))
    if not whl_files:
        print("\033[33m未找到 .whl 文件，请先运行 build\033[0m")
        sys.exit(1)

    whl = whl_files[-1]
    print(f"安装: {whl.name}")
    run([sys.executable, "-m", "pip", "uninstall", "-y", "dev-agent"])
    run([sys.executable, "-m", "pip", "install", str(whl)])

    # 验证
    result = subprocess.run(
        [sys.executable, "-c", "from dev_agent import __version__; print(f'DevAgent v{__version__}')"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    print(f"\033[32m{result.stdout.strip()}\033[0m")

    # 验证 CLI
    result = subprocess.run(
        ["dev-agent", "--help"], capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("\033[32mCLI 命令验证通过\033[0m")
    else:
        print(f"\033[31mCLI 命令验证失败: {result.stderr}\033[0m")


def publish() -> None:
    """发布到 PyPI（需要配置 TWINE_USERNAME/TWINE_PASSWORD 或 .pypirc）"""
    whl_files = sorted(ROOT.glob("dist/*.whl"))
    if not whl_files:
        print("\033[33m未找到发布文件，请先运行 build\033[0m")
        sys.exit(1)

    # 检查 twine
    try:
        subprocess.run([sys.executable, "-m", "twine", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\033[33mtwine 未安装，正在安装...\033[0m")
        run([sys.executable, "-m", "pip", "install", "twine"])

    # 发布
    repository = "--repository" + "pypi"
    run([sys.executable, "-m", "twine", "upload", repository, "--non-interactive", "dist/*"])

    print("\033[32m发布完成! 升级: pip install --upgrade dev-agent\033[0m")


def main() -> None:
    commands = {
        "clean": clean,
        "build": build,
        "test-install": test_install,
        "publish": publish,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("用法: python scripts/build.py <command>")
        print(f"可用命令: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
