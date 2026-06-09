"""Architecture/static guard for SkillOutput error contract.

Verifies that:
- Runtime modules do not obviously append raw string errors.
- src/schemas/skill.py defines normalize_skill_error.
- SkillOutput.to_dict uses normalize_skill_error.
- src/skillpack/run_skill.py _envelope_from_output uses normalize_skill_error.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(relpath: str) -> str:
    with open(os.path.join(PROJECT_ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def _find_dangerous_string_error_patterns(dirpath: str, exclude: set[str] | None = None) -> list[str]:
    """Search for dangerous string-error patterns in runtime source."""
    violations: list[str] = []
    full_path = os.path.join(PROJECT_ROOT, dirpath)
    if not os.path.isdir(full_path):
        return violations
    for root, dirs, files in os.walk(full_path):
        dirs[:] = [d for d in dirs if not d.startswith("_") and d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"):
                continue
            if exclude and f in exclude:
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding="utf-8") as fh:
                    source = fh.read()
            except Exception:
                continue
            try:
                tree = ast.parse(source, filename=filepath)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute):
                        if func.attr == "append" and isinstance(func.value, ast.Name) and func.value.id == "errors":
                            for arg in node.args:
                                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                    violations.append(
                                        f"{os.path.relpath(filepath, PROJECT_ROOT)}: "
                                        f"errors.append(\"{arg.value[:50]}\")"
                                    )
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "errors" and isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    violations.append(
                                        f"{os.path.relpath(filepath, PROJECT_ROOT)}: "
                                        f"errors=[\"{elt.value[:50]}\"]"
                                    )
    return violations


class TestNoRawStringErrorsInRuntime:
    def test_skills_runtime_no_string_errors_append(self):
        violations = _find_dangerous_string_error_patterns("src/skills_runtime")
        assert not violations, (
            f"src/skills_runtime has raw string error patterns:\n" + "\n".join(violations)
        )

    def test_skillpack_no_string_errors_append(self):
        violations = _find_dangerous_string_error_patterns(
            "src/skillpack",
            exclude={"validator.py", "doctor.py"},
        )
        assert not violations, (
            f"src/skillpack has raw string error patterns:\n" + "\n".join(violations)
        )


class TestNormalizeSkillErrorExists:
    def test_normalize_skill_error_defined(self):
        source = _read("src/schemas/skill.py")
        assert "def normalize_skill_error" in source

    def test_normalize_skill_errors_defined(self):
        source = _read("src/schemas/skill.py")
        assert "def normalize_skill_errors" in source

    def test_make_skill_error_dict_defined(self):
        source = _read("src/schemas/skill.py")
        assert "def make_skill_error_dict" in source


class TestSkillOutputToDictUsesNormalize:
    def test_to_dict_calls_normalize_skill_error(self):
        source = _read("src/schemas/skill.py")
        assert "normalize_skill_error" in source
        in_to_dict = False
        lines = source.split("\n")
        in_method = False
        for line in lines:
            if "def to_dict" in line:
                in_method = True
            if in_method and "normalize_skill_error" in line:
                in_to_dict = True
                break
            if in_method and line and not line[0].isspace() and "def " in line:
                in_method = False
        assert in_to_dict, "SkillOutput.to_dict does not call normalize_skill_error"


class TestEnvelopeFromOutputUsesNormalize:
    def test_envelope_from_output_calls_normalize(self):
        source = _read("src/skillpack/run_skill.py")
        assert "normalize_skill_error" in source
        tree = ast.parse(source, filename="run_skill.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_envelope_from_output":
                body_src = ast.get_source_segment(source, node) or ""
                if "normalize_skill_error" in body_src:
                    return
        pytest.fail("_envelope_from_output does not call normalize_skill_error")


class TestSkillErrorClassExists:
    def test_skill_error_class_defined(self):
        source = _read("src/schemas/skill.py")
        assert "class SkillError" in source

    def test_skill_error_has_to_dict(self):
        source = _read("src/schemas/skill.py")
        assert "def to_dict" in source
