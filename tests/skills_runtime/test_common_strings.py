"""Tests for src/skills_runtime/common/strings.unique_strings."""

from src.skills_runtime.common.strings import unique_strings
from src.skills_runtime.base import BaseSkillRuntime


def test_single_list():
    assert unique_strings(["a", "b", "a"]) == ["a", "b"]


def test_multiple_groups():
    assert unique_strings(["a", "b"], ["b", "c"]) == ["a", "b", "c"]


def test_string_group():
    assert unique_strings("hello", ["world"]) == ["hello", "world"]


def test_none_group():
    assert unique_strings(None, ["a"]) == ["a"]


def test_empty_group():
    assert unique_strings([], ["a"]) == ["a"]


def test_skip_empty_true():
    assert unique_strings(["a", "", "b"], skip_empty=True) == ["a", "b"]


def test_skip_empty_false():
    assert unique_strings(["a", "", "b"], skip_empty=False) == ["a", "", "b"]


def test_preserves_order():
    assert unique_strings(["c", "a", "b", "a"]) == ["c", "a", "b"]


def test_str_coercion():
    assert unique_strings([1, 2, 1]) == ["1", "2"]


def test_empty_input():
    assert unique_strings() == []


def test_delegation_base():
    assert BaseSkillRuntime._unique_strings(["a", "b", "a"]) == ["a", "b"]


def test_delegation_base_skip_empty_false():
    assert BaseSkillRuntime._unique_strings(["a", "", "b"]) == ["a", "", "b"]
