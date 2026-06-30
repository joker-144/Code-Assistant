"""
技能系统 — 加载和管理 Agent 技能
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class Skill:
    """技能定义"""
    def __init__(self, name: str, version: str, agent: str, description: str,
                 capabilities: list[str], tools: list[str]):
        self.name = name
        self.version = version
        self.agent = agent
        self.description = description
        self.capabilities = capabilities
        self.tools = tools

    @classmethod
    def from_file(cls, path: Path) -> "Skill":
        """从 skill.json 文件加载"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            name=data["name"],
            version=data["version"],
            agent=data["agent"],
            description=data["description"],
            capabilities=data.get("capabilities", []),
            tools=data.get("tools", []),
        )


class SkillLoader:
    """技能加载器"""

    def __init__(self, skills_dir: Optional[Path] = None):
        if skills_dir is None:
            # 默认使用项目根目录的 skills 文件夹
            # __file__ = src/dev_agent/skill_system.py -> parent(3) = 项目根目录
            self.skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
        else:
            self.skills_dir = Path(skills_dir).resolve()

    def load_all_skills(self) -> dict[str, Skill]:
        """加载所有技能"""
        skills = {}
        if not self.skills_dir.exists():
            return skills

        for agent_dir in self.skills_dir.iterdir():
            if agent_dir.is_dir():
                skill_file = agent_dir / "skill.json"
                if skill_file.exists():
                    try:
                        skill = Skill.from_file(skill_file)
                        skills[skill.agent] = skill
                    except Exception:
                        pass

        return skills

    def get_skill(self, agent: str) -> Optional[Skill]:
        """获取指定 Agent 的技能"""
        skills = self.load_all_skills()
        return skills.get(agent)

    def get_skills_for_agent(self, agent: str) -> Skill:
        """获取 Agent 技能（包含工具描述）"""
        skill = self.get_skill(agent)
        if not skill:
            return Skill(
                name=f"{agent}_default",
                version="1.0.0",
                agent=agent,
                description="默认技能",
                capabilities=["代码编写", "问题解决"],
                tools=["file", "shell", "git", "web"],
            )
        return skill

    def get_skill_prompt(self, agent: str) -> str:
        """获取 Agent 的技能 prompt"""
        skill = self.get_skills_for_agent(agent)

        tools_desc = {
            "web_search": "网络搜索 - 搜索最新技术文档和在线资料",
            "web_fetch": "网页获取 - 获取指定 URL 的页面内容并提取正文",
            "file_read": "文件读取 - 读取项目文件内容",
            "file_write": "文件写入 - 创建或修改项目文件",
            "shell": "Shell命令 - 执行系统命令进行构建、测试等操作",
            "git": "Git操作 - 执行 Git 版本控制命令",
        }

        capabilities = "\n".join(f"- {c}" for c in skill.capabilities)
        tools = "\n".join(f"- {t}: {tools_desc.get(t, t)}" for t in skill.tools)

        return f"""你是一个专业的 {skill.name}，版本 {skill.version}
角色: {skill.description}

## 核心能力
{capabilities}

## 可用工具
{tools}

请根据用户需求，运用上述能力和工具完成任务。"""

    @property
    def skills_dir_path(self) -> Path:
        """返回可被 skillhub 使用的 skills 目录路径"""
        return self.skills_dir
