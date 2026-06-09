"""Unit tests for the centralized resource resolver.

Verifies that ``src.skillpack.resources`` resolves paths correctly
from both repo-root and non-repo-root working directories.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.skillpack.resources import (
    package_root,
    resolve_manifest_path,
    resolve_resource_path,
    resolve_skillpack_file,
    resource_exists,
)


class TestPackageRoot:
    def test_package_root_contains_skillpack(self):
        root = package_root()
        assert (root / "skillpack" / "fund-agent.skillpack.yaml").exists(), (
            f"package_root()={root} does not contain skillpack/fund-agent.skillpack.yaml"
        )

    def test_package_root_is_deterministic(self):
        assert package_root() == package_root()


class TestResolveManifestPath:
    def test_default_manifest_resolves(self):
        path = resolve_manifest_path()
        assert path.exists()
        assert path.name == "fund-agent.skillpack.yaml"

    def test_explicit_relative_manifest_resolves(self):
        path = resolve_manifest_path("skillpack/fund-agent.skillpack.yaml")
        assert path.exists()

    def test_explicit_absolute_manifest_resolves(self):
        abs_path = str(package_root() / "skillpack" / "fund-agent.skillpack.yaml")
        path = resolve_manifest_path(abs_path)
        assert path.exists()


class TestResolveResourcePath:
    def test_skillpack_capabilities_from_repo_root(self):
        path = resolve_resource_path("skillpack/capabilities.yaml")
        assert path.exists()

    def test_skillpack_capabilities_from_temp_dir(self):
        original_cwd = Path.cwd()
        tmp = None
        try:
            tmp = tempfile.mkdtemp()
            os.chdir(tmp)
            path = resolve_resource_path("skillpack/capabilities.yaml")
            assert path.exists()
        finally:
            os.chdir(str(original_cwd))
            if tmp:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)

    def test_absolute_path_respected(self):
        abs_path = str(package_root() / "skillpack" / "capabilities.yaml")
        path = resolve_resource_path(abs_path)
        assert path.is_absolute()
        assert path.exists()

    def test_nonexistent_relative_returns_package_root_relative(self):
        path = resolve_resource_path("nonexistent/file.yaml")
        assert not path.exists()
        assert str(package_root()) in str(path)

    def test_cwd_preferred_when_exists(self):
        original_cwd = Path.cwd()
        tmp = None
        try:
            tmp = tempfile.mkdtemp()
            tmp_path = Path(tmp)
            (tmp_path / "test_file.yaml").write_text("test: true", encoding="utf-8")
            os.chdir(tmp)
            path = resolve_resource_path("test_file.yaml")
            assert str(tmp_path) in str(path)
        finally:
            os.chdir(str(original_cwd))
            if tmp:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)


class TestResolveSkillpackFile:
    def test_decision_contracts(self):
        path = resolve_skillpack_file("decision-contracts.yaml")
        assert path.exists()

    def test_artifact_contracts(self):
        path = resolve_skillpack_file("artifact-contracts.yaml")
        assert path.exists()

    def test_input_contracts(self):
        path = resolve_skillpack_file("input-contracts.yaml")
        assert path.exists()

    def test_thesis_contracts(self):
        path = resolve_skillpack_file("thesis-contracts.yaml")
        assert path.exists()


class TestResourceExists:
    def test_existing_resource(self):
        assert resource_exists("skillpack/capabilities.yaml") is True

    def test_nonexistent_resource(self):
        assert resource_exists("nonexistent/file.yaml") is False
