"""
技能管理工具 — list_skills、load_skill、install_skill

Agent 可通过这些工具检索、加载、安装技能。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from dev_agent.skill_system import SkillLoader, get_skills_dir
from dev_agent.tools.types import ToolResult


class SkillOps:
    """技能管理操作"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.loader = SkillLoader()

    async def list_skills(self) -> ToolResult:
        """列出当前所有技能"""
        skills = self.loader.list_all()
        if not skills:
            return ToolResult(success=True, data="skills 目录为空，暂无技能。")
        lines = ["## 当前已安装技能\n"]
        for name, skill in skills.items():
            caps = ", ".join(skill.capabilities)
            lines.append(f"- **{name}** ({skill.version}): {skill.description}")
            lines.append(f"  能力: {caps}")
        return ToolResult(success=True, data="\n".join(lines))

    async def load_skill(self, name: str = "") -> ToolResult:
        """加载指定技能的详细信息"""
        if name:
            skill = self.loader.get_by_dir_name(name)
            if not skill:
                return ToolResult(success=False, error=f"技能 '{name}' 不存在。可用的: {list(self.loader.list_all().keys())}")
            caps = "\n".join(f"- {c}" for c in skill.capabilities)
            tools = "\n".join(f"- {t}" for t in skill.tools)
            return ToolResult(success=True, data=(
                f"## {skill.name} (v{skill.version})\n\n"
                f"{skill.description}\n\n"
                f"### 核心能力\n{caps}\n\n"
                f"### 关联工具\n{tools}"
            ))
        else:
            return await self.list_skills()

    async def install_skill(self, name: str = "") -> ToolResult:
        """从 skillhub 安装技能

        Args:
            name: 技能名称（如 self-improving-agent、code-reviewer）
        """
        if not name:
            return ToolResult(success=False, error="请提供要安装的技能名称")

        skills_dir = str(get_skills_dir())

        try:
            # 尝试用 skillhub CLI 安装
            result = subprocess.run(
                ["skillhub", "install", name, "--dir", skills_dir],
                capture_output=True, text=True, timeout=30, cwd=str(self.workspace),
            )
            if result.returncode == 0:
                # 重新加载
                self.loader = SkillLoader()
                return ToolResult(success=True, data=f"技能 '{name}' 安装成功。\n{result.stdout}")
            else:
                # skillhub 不可用时，引导手动下载
                return ToolResult(
                    success=False,
                    error=(
                        f"skillhub CLI 未安装或安装失败。\n"
                        f"手动安装步骤:\n"
                        f"1. 从 https://skillhub.cn 搜索 '{name}'\n"
                        f"2. 下载后放入 '{skills_dir}/{name}/' 目录\n"
                        f"3. 确保目录下有 skill.json 文件"
                    ),
                )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=(
                    f"skillhub CLI 未安装。请先安装:\n"
                    f"  curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash\n\n"
                    f"或手动下载技能放入: {skills_dir}/<技能名>/"
                ),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="安装超时，请检查网络连接后重试")
