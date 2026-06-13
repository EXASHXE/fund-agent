"""Tests for deterministic markdown report renderer — no LLM, no network."""

from __future__ import annotations

import pytest

from src.skills_runtime.workflow.markdown_report import (
    REQUIRED_ZH_CN_SECTIONS,
    render_advisory_report_markdown,
)


def _minimal_report(**overrides):
    base = {
        "report_sections": [],
        "analysis_mode": "report_only",
        "quality_gate": {"status": "PASS"},
    }
    base.update(overrides)
    return base


def _realistic_report_sections():
    return [
        {
            "id": "direct_answer",
            "title": "直接回答",
            "status": "PARTIAL",
            "bullets": [
                "组合价值100,000，持仓3只基金",
                "数据完整度D级，关键数据缺失",
            ],
        },
        {
            "id": "evidence_status",
            "title": "证据状态",
            "status": "PARTIAL",
            "bullets": [
                "decision_support_ready: False",
                "证据不足：missing_nav_history, missing_recent_news",
            ],
        },
        {
            "id": "action_boundary",
            "title": "操作边界",
            "status": "OK",
            "bullets": [],
        },
        {
            "id": "data_gaps",
            "title": "数据缺口",
            "status": "PARTIAL",
            "bullets": [
                "NAV历史数据缺失",
                "近期新闻缺失",
                "成本基础未知（003003）",
            ],
        },
    ]


class TestMarkdownReportSections:
    def test_required_zh_cn_headings_present(self):
        md = render_advisory_report_markdown(_minimal_report())
        for section_id, section_title in REQUIRED_ZH_CN_SECTIONS:
            assert section_title in md, f"missing section: {section_title}"

    def test_report_only_no_formal_decision(self):
        md = render_advisory_report_markdown(_minimal_report(analysis_mode="report_only"))
        assert "未调用决策支持" in md or "报告模式" in md
        assert "正式交易决策" not in md or "不包含" in md

    def test_blocked_decision_shows_blockers(self):
        md = render_advisory_report_markdown(
            _minimal_report(analysis_mode="formal_trade_decision", decision=None)
        )
        assert "正式决策未生成" in md or "证据不足" in md

    def test_formal_decision_includes_action(self):
        decision = {
            "action": "HOLD",
            "fund_code": "000001",
            "execution_amount": 0,
            "evidence_anchors": ["anchor_1"],
        }
        md = render_advisory_report_markdown(
            _minimal_report(analysis_mode="formal_trade_decision", decision=decision)
        )
        assert "HOLD" in md
        assert "000001" in md

    def test_no_broker_execution_instruction(self):
        md = render_advisory_report_markdown(_minimal_report())
        assert "不包含经纪执行" in md or "不执行" in md

    def test_missing_data_disclosed(self):
        sections = [{"id": "data_gaps", "status": "MISSING", "bullets": ["NAV数据缺失"]}]
        md = render_advisory_report_markdown(_minimal_report(report_sections=sections))
        assert "NAV数据缺失" in md

    def test_deterministic_output(self):
        r1 = render_advisory_report_markdown(_minimal_report())
        r2 = render_advisory_report_markdown(_minimal_report())
        assert r1 == r2

    def test_invalid_input(self):
        md = render_advisory_report_markdown("not a dict")
        assert "Error" in md

    def test_zh_cn_section_numbers(self):
        md = render_advisory_report_markdown(_minimal_report())
        assert "## 1." in md
        assert "## 10." in md

    def test_risk_disclaimer_present(self):
        md = render_advisory_report_markdown(_minimal_report())
        assert "风险提示" in md
        assert "不构成投资建议" in md


class TestMarkdownReportSoftAdvice:
    def test_soft_advice_no_formal_decision(self):
        md = render_advisory_report_markdown(_minimal_report(analysis_mode="soft_action_advice"))
        assert "操作建议" in md or "soft_action_advice" in md.lower() or "未生成正式交易决策" in md


class TestMarkdownReportQualityGate:
    def test_quality_gate_included(self):
        md = render_advisory_report_markdown(
            _minimal_report(quality_gate={"status": "PARTIAL", "issues": ["missing NAV"]})
        )
        assert "质量门控" in md
        assert "PARTIAL" in md


class TestMarkdownReportRealisticFinalReport:
    def test_realistic_sections_render(self):
        sections = _realistic_report_sections()
        md = render_advisory_report_markdown(
            _minimal_report(report_sections=sections, analysis_mode="report_only")
        )
        assert "组合价值100,000" in md
        assert "证据不足" in md
        assert "NAV历史数据缺失" in md
        assert "成本基础未知" in md

    def test_blocked_formal_decision_with_reason_codes(self):
        sections = [
            {
                "id": "evidence_status",
                "title": "证据状态",
                "status": "PARTIAL",
                "bullets": [
                    "decision_support_ready: False",
                    "Blockers: missing_nav_history, missing_recent_news",
                ],
            },
        ]
        md = render_advisory_report_markdown(
            _minimal_report(
                report_sections=sections,
                analysis_mode="formal_trade_decision",
                decision=None,
            )
        )
        assert "正式决策未生成" in md or "证据不足" in md
        assert "不包含经纪执行" in md or "不执行" in md

    def test_formal_decision_with_evidence_anchors(self):
        decision = {
            "action": "REDUCE",
            "fund_code": "000001",
            "execution_amount": 5000,
            "evidence_anchors": [
                "overweight_single_fund (severity=high)",
                "insufficient_cash_reserve (severity=medium)",
            ],
        }
        md = render_advisory_report_markdown(
            _minimal_report(
                analysis_mode="formal_trade_decision",
                decision=decision,
            )
        )
        assert "REDUCE" in md
        assert "000001" in md
        assert "overweight_single_fund" in md
        assert "insufficient_cash_reserve" in md

    def test_missing_data_disclosure_in_final_report(self):
        sections = [
            {
                "id": "data_gaps",
                "title": "数据缺口",
                "status": "PARTIAL",
                "bullets": [
                    "NAV历史数据缺失",
                    "基金资料缺失",
                    "成本基础未知（003003）",
                ],
            },
        ]
        md = render_advisory_report_markdown(
            _minimal_report(report_sections=sections)
        )
        assert "NAV历史数据缺失" in md
        assert "成本基础未知" in md

    def test_no_broker_or_order_execution_instruction(self):
        sections = _realistic_report_sections()
        decision = {
            "action": "HOLD",
            "fund_code": "000001",
            "execution_amount": 0,
            "evidence_anchors": [],
        }
        md = render_advisory_report_markdown(
            _minimal_report(
                report_sections=sections,
                analysis_mode="formal_trade_decision",
                decision=decision,
            )
        )
        lower = md.lower()
        for forbidden in ["买入指令", "卖出指令", "下单", "执行交易", "委托"]:
            assert forbidden not in lower, f"forbidden broker instruction: {forbidden}"
        assert "不包含经纪执行" in md or "不执行" in md

    def test_deterministic_with_realistic_sections(self):
        sections = _realistic_report_sections()
        r1 = render_advisory_report_markdown(
            _minimal_report(report_sections=sections, analysis_mode="report_only")
        )
        r2 = render_advisory_report_markdown(
            _minimal_report(report_sections=sections, analysis_mode="report_only")
        )
        assert r1 == r2
