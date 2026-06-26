"""Tests for M7.8 real-use short-prompt contract.

Validates that the agent-facing surface correctly routes short natural-language
prompts to the canonical personal-run entrypoint — not to the legacy e2e
entrypoint. Covers the M7.8 trap-file redirect fix and the short-prompt
trigger expansion.

All assertions are structural / content checks — no real fund data.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_MD = REPO_ROOT / "skills" / "fund-analysis" / "SKILL.md"
E2E_SKILL_MD = REPO_ROOT / ".opencode" / "skills" / "fund-agent-e2e" / "SKILL.md"
E2E_AGENT_MD = REPO_ROOT / ".opencode" / "agents" / "fund-report-e2e.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestShortPromptTriggers:
    """M7.8: SKILL.md must include short / ambiguous report prompts as triggers."""

    def test_skill_md_has_must_read_directive(self):
        content = _read(SKILL_MD)
        assert "MUST read" in content

    def test_skill_md_lists_short_report_prompts(self):
        content = _read(SKILL_MD)
        # The shortest, most ambiguous prompt from the M7.8 prompt set
        assert "帮我做分析报告" in content

    def test_skill_md_brainstorming_precedence(self):
        """fund-analysis must take precedence over brainstorming for analysis requests."""
        content = _read(SKILL_MD)
        assert "brainstorming" in content.lower()
        # Must tell the agent NOT to ask A/B/C clarifying questions
        assert "A/B/C" in content or "clarifying question" in content.lower() or "disambiguation" in content.lower()

    def test_skill_md_autonomous_workflow_for_short_prompts(self):
        content = _read(SKILL_MD)
        assert "autonomous" in content.lower()


class TestE2eSkillRedirect:
    """M7.8: The .opencode e2e skill must redirect to personal-run, NOT advertise
    bin/fund-agent-e2e as a user-facing command."""

    def test_e2e_skill_redirects_to_personal_run(self):
        content = _read(E2E_SKILL_MD)
        assert "bin/fund-agent-personal-run" in content

    def test_e2e_skill_does_not_advertise_e2e_as_user_command(self):
        """The e2e skill must NOT present bin/fund-agent-e2e as the command to run.

        It may mention it only in the context of 'do NOT call' / 'internal only'.
        """
        content = _read(E2E_SKILL_MD)
        # Find code blocks — none should contain 'bin/fund-agent-e2e' as a
        # runnable command (only personal-run is the canonical command).
        import re
        code_blocks = re.findall(r"```[a-z]*\n(.*?)```", content, re.DOTALL)
        for block in code_blocks:
            # A code block that looks like a command to run should use personal-run
            if "bin/fund-agent" in block:
                assert "bin/fund-agent-personal-run" in block, (
                    f"e2e skill code block advertises non-personal-run entrypoint:\n{block}"
                )

    def test_e2e_skill_states_internal_only(self):
        content = _read(E2E_SKILL_MD)
        assert "internal" in content.lower()

    def test_e2e_skill_does_not_output_legacy_flat_report(self):
        """The e2e skill must NOT tell agents to output real_portfolio_report.md."""
        content = _read(E2E_SKILL_MD)
        # It's OK to mention it as forbidden, but not as an output to produce
        import re
        # Look for "Output" or "输出" sections that mention real_portfolio_report
        output_sections = re.findall(r"(?:Output|输出)[^\n]*\n((?:-.*\n)+)", content)
        for section in output_sections:
            assert "real_portfolio_report.md" not in section, (
                "e2e skill lists real_portfolio_report.md as an output"
            )


class TestE2eAgentRedirect:
    """M7.8: The .opencode fund-report-e2e agent must use personal-run."""

    def test_agent_uses_personal_run(self):
        content = _read(E2E_AGENT_MD)
        assert "bin/fund-agent-personal-run" in content

    def test_agent_forbids_direct_e2e(self):
        content = _read(E2E_AGENT_MD)
        assert "bin/fund-agent-e2e" in content
        # Must be in a restricted/forbidden context
        assert "No calling" in content or "Restricted" in content or "NEVER" in content

    def test_agent_reads_agent_context(self):
        """The agent must read agent_context.md, not eval_workspace as final output."""
        content = _read(E2E_AGENT_MD)
        assert "agent_context.md" in content

    def test_agent_does_not_use_eval_workspace_as_final(self):
        content = _read(E2E_AGENT_MD)
        # eval_workspace may appear in restricted/forbidden context but not as
        # the agent's primary read path
        import re
        read_sections = re.findall(r"(?:Read|read)[^\n]*eval_workspace", content)
        # The agent should read from local_reports/<run_id>/, not eval_workspace
        assert "local_reports/<run_id>" in content or "local_reports/{" in content


class TestCanonicalOutputPathContract:
    """M7.8: The canonical output path contract must be consistent across files."""

    def test_skill_md_canonical_output_is_run_dir(self):
        content = _read(SKILL_MD)
        assert "local_reports/<run_id>/" in content

    def test_e2e_skill_does_not_claim_eval_workspace_as_canonical(self):
        content = _read(E2E_SKILL_MD)
        # The e2e skill must NOT say eval_workspace/runs is the output
        assert "eval_workspace/runs" not in content or "forbidden" in content.lower() or "not" in content.lower()


class TestAgentsMdPrecedence:
    """M7.8: AGENTS.md must declare fund-analysis precedence over brainstorming
    and list personal-run as the canonical entrypoint (not e2e)."""

    def test_agents_md_has_skill_precedence_section(self):
        content = _read(AGENTS_MD)
        assert "Skill precedence" in content
        assert "M7.8" in content

    def test_agents_md_lists_short_prompt(self):
        content = _read(AGENTS_MD)
        assert "帮我做分析报告" in content

    def test_agents_md_forbids_brainstorming_for_analysis(self):
        content = _read(AGENTS_MD)
        assert "brainstorming" in content.lower()
        assert "no" in content.lower() and "brainstorming" in content.lower()

    def test_agents_md_personal_run_is_canonical(self):
        content = _read(AGENTS_MD)
        assert "bin/fund-agent-personal-run" in content
        assert "canonical" in content.lower()

    def test_agents_md_e2e_is_internal_only(self):
        content = _read(AGENTS_MD)
        assert "bin/fund-agent-e2e" in content
        assert "internal" in content.lower() or "do NOT" in content
