"""
技能系统 — 统一管理所有 Agent 技能

skills/
├── planner/    ← 规划Agent 技能
├── coder/      ← 编码Agent 技能
├── reviewer/   ← 审查Agent 技能
└── (下载的新技能也放在这里)

每个技能目录包含:
  - skill.json  技能元数据（名称、版本、能力、工具列表）
  - SKILL.md    技能详细说明（可选）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# skills 目录路径 — 项目根目录下的 skills/
_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


def get_skills_dir() -> Path:
    """获取 skills 目录路径（供 CLI/skillhub 使用）"""
    return _SKILLS_DIR


class SkillInfo:
    """技能元数据"""

    def __init__(self, name: str, version: str, description: str,
                 capabilities: list[str], tools: list[str]):
        self.name = name
        self.version = version
        self.description = description
        self.capabilities = capabilities
        self.tools = tools

    @classmethod
    def from_json(cls, path: Path) -> "SkillInfo":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", path.parent.name),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            tools=data.get("tools", []),
        )


class SkillLoader:
    """加载 skills 目录中所有技能"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or _SKILLS_DIR

    def list_all(self) -> dict[str, SkillInfo]:
        """扫描 skills 目录，返回 {agent_name: SkillInfo}"""
        result = {}
        if not self.skills_dir.exists():
            return result

        for d in sorted(self.skills_dir.iterdir()):
            if not d.is_dir():
                continue
            skill_json = d / "skill.json"
            if skill_json.exists():
                try:
                    skill = SkillInfo.from_json(skill_json)
                    result[d.name] = skill
                except Exception:
                    pass
        return result

    def get_skill(self, agent_name: str) -> Optional[SkillInfo]:
        return self.list_all().get(agent_name)

    def get_by_dir_name(self, dir_name: str) -> Optional[SkillInfo]:
        """按目录名获取技能（供下载后直接使用）"""
        skill_json = self.skills_dir / dir_name / "skill.json"
        if skill_json.exists():
            try:
                return SkillInfo.from_json(skill_json)
            except Exception:
                pass
        return None

    def format_for_prompt(self) -> str:
        """生成供 Agent system prompt 使用的技能描述"""
        skills = self.list_all()
        if not skills:
            return ""

        lines = ["\n## 可用技能\n"]
        for agent_name, skill in skills.items():
            caps = ", ".join(skill.capabilities[:3])
            tools = ", ".join(skill.tools[:3])
            lines.append(
                f"- **{agent_name}**: {skill.description}\n"
                f"  能力: {caps}\n"
                f"  工具: {tools}"
            )
        return "\n".join(lines) + "\n"
