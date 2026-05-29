from pathlib import Path

from legacy.analysis.scoring.types import MarketRegime
from legacy.prompts.loader import PROMPT_FILES, load_all_prompts, load_prompt


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


def test_skill_contract_docs_match_current_agent_evidence_extensions():
    evidence_contract = (SKILL_DIR / "references" / "evidence-contract.md").read_text(
        encoding="utf-8"
    )

    for field in ("kg_snapshot", "news_evidence", "score_evidence", "strategy_evidence"):
        assert f"`{field}`" in evidence_contract
    assert "`event_extraction`" not in evidence_contract
    assert "`kg_analysis`" not in evidence_contract


def test_scoring_agent_prompt_uses_runtime_regime_weights():
    prompt = (SKILL_DIR / "prompts" / "scoring-agent.md").read_text(
        encoding="utf-8"
    )
    labels = {
        MarketRegime.NORMAL: "NORMAL",
        MarketRegime.HIGH_VOLATILITY: "HIGH_VOLATILITY",
        MarketRegime.TRENDING: "TRENDING",
        MarketRegime.CRISIS: "CRISIS",
    }

    for regime, label in labels.items():
        weights = regime.weights()
        rows = [line for line in prompt.splitlines() if f"| {label}" in line]
        assert rows
        row = rows[0]
        for expected_cell in [
            f"{int(weights['quant'] * 100)}%",
            f"{int(weights['fundamental'] * 100)}%",
            f"{int(weights['event'] * 100)}%",
            f"{int(weights['position'] * 100)}%",
            f"{int(weights['timing'] * 100)}%",
        ]:
            assert expected_cell in row
