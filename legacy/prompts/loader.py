"""Load modular prompts bundled with the fund-analyst skill."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_SKILL_NAME = "fund-analyst"
PROMPT_FILES = {
    "router": "router.md",
    "news": "news-agent.md",
    "scoring": "scoring-agent.md",
    "portfolio": "portfolio-agent.md",
    "summary": "summary-agent.md",
}


@dataclass(frozen=True)
class PromptSpec:
    key: str
    path: Path
    text: str


def repo_root(start: Path | None = None) -> Path:
    """Return the project root by walking up to the nearest `skills/` folder."""
    current = (start or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "skills" / DEFAULT_SKILL_NAME / "SKILL.md").exists():
            return candidate
    raise FileNotFoundError("无法定位 fund-agent 项目根目录")


def skill_prompt_dir(skill_name: str = DEFAULT_SKILL_NAME, root: Path | None = None) -> Path:
    base = root or repo_root()
    prompt_dir = base / "skills" / skill_name / "prompts"
    if not prompt_dir.is_dir():
        raise FileNotFoundError(f"Prompt 目录不存在: {prompt_dir}")
    return prompt_dir


def load_prompt(key: str, skill_name: str = DEFAULT_SKILL_NAME, root: Path | None = None) -> PromptSpec:
    """Load one named prompt from `skills/<skill>/prompts`."""
    filename = PROMPT_FILES.get(key)
    if filename is None:
        known = ", ".join(sorted(PROMPT_FILES))
        raise KeyError(f"未知 Prompt: {key}; 可用: {known}")
    path = skill_prompt_dir(skill_name, root) / filename
    if not path.is_file():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return PromptSpec(key=key, path=path, text=path.read_text(encoding="utf-8"))


def load_all_prompts(skill_name: str = DEFAULT_SKILL_NAME, root: Path | None = None) -> dict[str, PromptSpec]:
    return {
        key: load_prompt(key, skill_name=skill_name, root=root)
        for key in PROMPT_FILES
    }
