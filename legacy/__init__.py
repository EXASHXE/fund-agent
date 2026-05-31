"""Legacy pipeline — historical archive only. Not part of plugin contract.

Use the host-agnostic skill pack instead:
    skillpack/fund-agent.skillpack.yaml
    src/skills_runtime/
"""
import warnings
warnings.warn("legacy modules are deprecated — use skillpack manifest and skills_runtime", DeprecationWarning, stacklevel=2)