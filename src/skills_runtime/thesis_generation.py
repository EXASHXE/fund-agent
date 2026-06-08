"""Thesis generation skill runtime.

This skill creates deterministic ThesisDraft artifacts from host-supplied
evidence and context. It does NOT produce formal Decision or ExecutionLedger.
Formal decisions require decision_support.
"""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.base import BaseSkillRuntime


class ThesisGenerationSkill(BaseSkillRuntime):
    """Artifact-only thesis draft skill with deterministic draft generation."""

    def run(self, skill_input: SkillInput) -> SkillOutput:
        payload = skill_input.payload or {}
        if not isinstance(payload, dict):
            return self.failed_output(
                skill_input,
                "INVALID_INPUT",
                "ThesisGenerationSkill payload must be a dictionary",
            )

        entities = self.normalize_entities_from_input(skill_input)
        topic = self._resolve_topic(payload, skill_input)
        evidence_items_raw = self._collect_evidence_items(payload, skill_input)
        fund_analysis_report = payload.get("fund_analysis_report")
        artifacts_payload = payload.get("artifacts")
        constraints = payload.get("constraints", {})
        risk_profile = payload.get("risk_profile", {})
        research_focus = payload.get("research_focus")

        supporting, counter, neutral, missing = self._classify_evidence(
            evidence_items_raw,
        )

        source_summary = self._build_source_summary(evidence_items_raw)

        confidence = self._assess_confidence(
            supporting, counter, neutral, missing, fund_analysis_report, artifacts_payload,
        )

        watch_conditions = self._derive_watch_conditions(
            topic, supporting, counter, risk_profile,
        )
        invalidating_conditions = self._derive_invalidating_conditions(
            topic, counter, risk_profile,
        )
        next_questions = self._derive_next_research_questions(
            topic, missing, research_focus,
        )
        limitations = self._derive_limitations(
            missing, evidence_items_raw, fund_analysis_report,
        )

        thesis_statement = self._build_thesis_statement(
            topic, supporting, counter, neutral, confidence,
        )

        thesis_draft = {
            "task_id": skill_input.task_id,
            "topic": topic,
            "related_entities": entities,
            "thesis_statement": thesis_statement,
            "supporting_evidence": supporting,
            "counter_evidence": counter,
            "neutral_evidence": neutral,
            "missing_evidence": missing,
            "confidence_assessment": confidence,
            "watch_conditions": watch_conditions,
            "invalidating_conditions": invalidating_conditions,
            "next_research_questions": next_questions,
            "source_summary": source_summary,
            "limitations": limitations,
            "decision_boundary_note": (
                "Draft only; formal Decision / ExecutionLedger requires decision_support."
            ),
        }

        has_context = bool(
            evidence_items_raw
            or fund_analysis_report
            or artifacts_payload
            or skill_input.evidence_context,
        )
        status = "OK" if has_context and confidence["level"] != "LOW" else "PARTIAL"
        if not has_context:
            status = "PARTIAL"
            thesis_draft["limitations"].append(
                "No evidence context, fund analysis report, or artifacts were provided; "
                "thesis is based on minimal input."
            )

        warnings = []
        if missing:
            warnings.append(
                f"Thesis has {len(missing)} missing evidence area(s); "
                "confidence may be overstated."
            )

        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts={"thesis_draft": thesis_draft},
            warnings=warnings,
            status=status,
        )

    def _resolve_topic(self, payload: dict, skill_input: SkillInput) -> str:
        topic = payload.get("thesis_question") or payload.get("topic")
        if topic and isinstance(topic, str) and topic.strip():
            return topic.strip()
        objective = payload.get("objective")
        if objective and isinstance(objective, str) and objective.strip():
            return objective.strip()
        entities = self.normalize_entities_from_input(skill_input)
        if entities and entities != ["research_task"]:
            return f"Investment thesis for {', '.join(entities[:3])}"
        return "General investment thesis"

    def _collect_evidence_items(
        self, payload: dict, skill_input: SkillInput,
    ) -> list[dict]:
        items: list[dict] = []
        evidence_graph = payload.get("evidence_graph")
        if isinstance(evidence_graph, dict):
            graph_items = evidence_graph.get("items", {})
            if isinstance(graph_items, dict):
                for eid, item in graph_items.items():
                    if isinstance(item, dict):
                        items.append(item)
            elif isinstance(graph_items, list):
                for item in graph_items:
                    if isinstance(item, dict):
                        items.append(item)
        evidence_items = payload.get("evidence_items")
        if isinstance(evidence_items, list):
            for item in evidence_items:
                if isinstance(item, dict):
                    items.append(item)
        for ctx_ref in skill_input.evidence_context:
            items.append({"claim": ctx_ref, "direction": "neutral", "source_type": "evidence_context"})
        return items

    def _classify_evidence(
        self, items: list[dict],
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        supporting = []
        counter = []
        neutral = []
        missing = []

        for item in items:
            direction = str(item.get("direction", "neutral")).lower()
            category = str(item.get("category", "")).lower()
            claim = item.get("claim", "")

            if category in ("missing", "gap", "absent"):
                missing.append(self._evidence_summary(item))
                continue

            if direction == "positive" or category in ("supporting", "bullish"):
                supporting.append(self._evidence_summary(item))
            elif direction == "negative" or category in ("counter", "bearish", "risk"):
                counter.append(self._evidence_summary(item))
            else:
                neutral.append(self._evidence_summary(item))

        if not items:
            missing.append({
                "area": "general",
                "description": "No evidence items were provided",
                "priority": "high",
            })

        return supporting, counter, neutral, missing

    @staticmethod
    def _evidence_summary(item: dict) -> dict:
        return {
            "claim": item.get("claim", ""),
            "source_type": item.get("source_type", "unknown"),
            "direction": item.get("direction", "neutral"),
            "confidence_weight": item.get("confidence_weight", item.get("confidence", None)),
            "related_entities": item.get("related_entities", []),
        }

    def _assess_confidence(
        self,
        supporting: list[dict],
        counter: list[dict],
        neutral: list[dict],
        missing: list[dict],
        fund_analysis_report: Any,
        artifacts_payload: Any,
    ) -> dict:
        total = len(supporting) + len(counter) + len(neutral)
        has_report = fund_analysis_report is not None
        has_artifacts = artifacts_payload is not None

        if total == 0 and not has_report and not has_artifacts:
            return {
                "level": "LOW",
                "score": 0.1,
                "reason": "No evidence items, fund analysis report, or artifacts provided.",
            }

        support_weight = len(supporting)
        counter_weight = len(counter)
        balance = support_weight - counter_weight if total > 0 else 0

        base_score = 0.5
        if total > 0:
            base_score = min(max(support_weight / total, 0.1), 0.9)
        if has_report:
            base_score = min(base_score + 0.1, 0.9)
        if has_artifacts:
            base_score = min(base_score + 0.05, 0.95)

        if len(missing) > 2:
            base_score = max(base_score - 0.15, 0.1)
        if counter_weight > support_weight:
            base_score = max(base_score - 0.1, 0.1)

        base_score = round(base_score, 2)

        if base_score >= 0.7:
            level = "HIGH"
        elif base_score >= 0.4:
            level = "MEDIUM"
        else:
            level = "LOW"

        reasons = []
        if support_weight > 0:
            reasons.append(f"{support_weight} supporting evidence item(s)")
        if counter_weight > 0:
            reasons.append(f"{counter_weight} counter evidence item(s)")
        if missing:
            reasons.append(f"{len(missing)} missing evidence area(s)")
        if has_report:
            reasons.append("fund analysis report available")
        if has_artifacts:
            reasons.append("artifacts available")

        return {
            "level": level,
            "score": base_score,
            "reason": "; ".join(reasons) if reasons else "Minimal evidence context.",
        }

    def _build_thesis_statement(
        self,
        topic: str,
        supporting: list[dict],
        counter: list[dict],
        neutral: list[dict],
        confidence: dict,
    ) -> str:
        level = confidence.get("level", "LOW")
        if level == "LOW":
            return (
                f"Insufficient evidence to form a strong thesis on '{topic}'. "
                "Further research is recommended before any investment action."
            )
        if level == "MEDIUM":
            if len(supporting) > len(counter):
                return (
                    f"Moderate evidence supports a cautiously favorable view on '{topic}', "
                    "but counter evidence and gaps warrant further investigation."
                )
            return (
                f"Evidence on '{topic}' is mixed; no clear directional thesis emerges. "
                "Additional research is needed."
            )
        return (
            f"Evidence supports a favorable thesis on '{topic}', "
            "though ongoing monitoring for counter signals is recommended."
        )

    @staticmethod
    def _derive_watch_conditions(
        topic: str,
        supporting: list[dict],
        counter: list[dict],
        risk_profile: dict,
    ) -> list[str]:
        conditions = []
        if counter:
            conditions.append(
                "Counter evidence intensifies or new contradicting signals emerge"
            )
        if risk_profile:
            tolerance = risk_profile.get("risk_tolerance", "")
            if tolerance in ("conservative", "low"):
                conditions.append("Portfolio risk exceeds conservative tolerance threshold")
        if not supporting:
            conditions.append("Supporting evidence remains absent or insufficient")
        if not conditions:
            conditions.append("Significant change in underlying evidence direction")
        return conditions

    @staticmethod
    def _derive_invalidating_conditions(
        topic: str,
        counter: list[dict],
        risk_profile: dict,
    ) -> list[str]:
        conditions = []
        if len(counter) >= 2:
            conditions.append("Multiple independent counter signals confirmed")
        conditions.append("Evidence quality degrades below minimum threshold")
        return conditions

    @staticmethod
    def _derive_next_research_questions(
        topic: str,
        missing: list[dict],
        research_focus: Any,
    ) -> list[str]:
        questions = []
        for gap in missing[:3]:
            area = gap.get("area", gap.get("description", "unknown area"))
            questions.append(f"What evidence exists for {area}?")
        if research_focus and isinstance(research_focus, str):
            questions.append(f"Deepen research on: {research_focus}")
        if not questions:
            questions.append(f"What additional data would strengthen the thesis on '{topic}'?")
        return questions

    @staticmethod
    def _derive_limitations(
        missing: list[dict],
        evidence_items: list[dict],
        fund_analysis_report: Any,
    ) -> list[str]:
        limitations = []
        if not evidence_items:
            limitations.append("No structured evidence items were provided")
        if missing:
            limitations.append(
                f"{len(missing)} evidence area(s) have gaps"
            )
        if not fund_analysis_report:
            limitations.append("No fund analysis report was provided for context")
        limitations.append("Thesis is a draft artifact; formal decisions require decision_support")
        return limitations

    @staticmethod
    def _build_source_summary(evidence_items: list[dict]) -> dict:
        source_counts: dict[str, int] = {}
        for item in evidence_items:
            source = item.get("source_type", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        return source_counts
