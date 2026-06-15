"""Tests that all file references in the skillpack manifest exist."""

import os
import yaml

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MANIFEST_PATH = os.path.join(_REPO_ROOT, "skillpack", "fund-agent.skillpack.yaml")


def _load_manifest():
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestManifestReferences:
    def test_optional_reference_workflows_exist(self):
        manifest = _load_manifest()
        workflows = manifest.get("integration", {}).get("optional_reference_workflows", [])
        for workflow_path in workflows:
            full_path = os.path.join(_REPO_ROOT, workflow_path)
            assert os.path.isfile(full_path), f"Manifest references non-existent file: {workflow_path}"
