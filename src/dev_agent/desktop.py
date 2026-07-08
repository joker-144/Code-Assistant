"""
桌面端启动器 — 启动 API 后端 + 打开浏览器 + 系统托盘管理

支持两种运行方式:
  - 源码: python -m dev_agent.desktop
  - CLI:  dev-agent desktop
  - 打包: dev-agent.exe desktop
"""
from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
import socket
from pathlib import Path


def find_free_port(start: int = 8000) -> int:
    """从 start 开始查找第一个可用端口，最多尝试 100 个"""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def _try_gui(proc: subprocess.Popen, port: int) -> bool:
    """尝试启动 tkinter 窗口，失败返回 False"""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.title("DevAgent 桌面端")
        root.protocol("WM_DELETE_WINDOW", lambda: _shutdown(root, proc))

        label = tk.Label(
            root,
            text=f"DevAgent 正在运行\n\n浏览器访问: http://localhost:{port}\n\n关闭此窗口将停止服务",
            font=("Microsoft YaHei", 11),
            padx=30,
            pady=20,
        )
        label.pack()

        btn = tk.Button(
            root,
            text="停止并退出",
            command=lambda: _shutdown(root, proc),
            font=("Microsoft YaHei", 10),
            bg="#e74c3c",
            fg="white",
            padx=20,
            pady=6,
        )
        btn.pack(pady=(0, 20))

        root.update_idletasks()
        w, h = 420, 200
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

        root.deiconify()
        root.mainloop()
        return True
    except Exception:
        return False


def _shutdown(root, proc: subprocess.Popen):
    """安全关闭"""
    try:
        root.destroy()
    except Exception:
        pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    except Exception:
        pass


def main():
    """桌面端入口"""
    port = find_free_port()
    url = f"http://localhost:{port}"

    # 构建启动命令
    if getattr(sys, "frozen", False):
        # 打包后的 exe 模式
        cmd = [sys.executable, "serve", "--port", str(port), "--host", "127.0.0.1"]
    else:
        # 源码模式
        cmd = [
            sys.executable,
            "-m", "dev_agent.cli",
            "serve",
            "--port", str(port),
            "--host", "127.0.0.1",
        ]

    # 启动 API 后端子进程（Windows 下隐藏控制台窗口）
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    # 等待 API 启动
    started = False
    for _ in range(30):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                started = True
                break

    if not started:
        print(f"[DevAgent] API 启动超时，请检查端口 {port} 是否被占用")
        try:
            proc.terminate()
        except Exception:
            pass
        sys.exit(1)

    # 打开浏览器
    webbrowser.open(url)

    # 尝试 GUI 窗口，失败则回退到终端等待
    if not _try_gui(proc, port):
        print(f"\nDevAgent 桌面端已启动")
        print(f"浏览器访问: {url}")
        print("按 Ctrl+C 退出...\n")
        try:
            proc.wait()
        except KeyboardInterrupt:
            print("\n正在停止...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print("已退出")


if __name__ == "__main__":
    main()
