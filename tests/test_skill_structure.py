from pathlib import Path

from src.prompts.loader import PROMPT_FILES, load_all_prompts, load_prompt


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "fund-analyst"


def test_fund_analyst_skill_uses_standard_resource_dirs():
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SKILL_DIR / "agents" / "openai.yaml").is_file()
    assert (SKILL_DIR / "prompts").is_dir()
    assert (SKILL_DIR / "references").is_dir()

    root_markdown = sorted(path.name for path in SKILL_DIR.glob("*.md"))
    assert root_markdown == ["SKILL.md"]


def test_prompt_loader_reads_all_agent_prompts():
    prompts = load_all_prompts(root=ROOT)

    assert set(prompts) == set(PROMPT_FILES)
    for key, spec in prompts.items():
        assert spec.key == key
        assert spec.path.is_file()
        assert "Prompt" in spec.text
        assert "AGENT_FILL" not in spec.text


def test_prompt_loader_rejects_unknown_key():
    try:
        load_prompt("unknown", root=ROOT)
    except KeyError as exc:
        assert "未知 Prompt" in str(exc)
    else:
        raise AssertionError("unknown prompt key should fail")
