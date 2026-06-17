# fund-agent Codex Plugin

This directory contains the Codex plugin manifest for fund-agent.

## Status

The `.codex-plugin/plugin.json` is an **experimental** forward-compatible marker.
The Codex plugin spec is not yet stable. This manifest may change when the
official spec is published.

Codex Agent Skills are installed under `.agents/skills/` (repo-local) or
`~/.agents/skills/` (user-global).

Full Codex marketplace plugin publishing is **not implemented** in this release.
Skills are available via repo-local or user-global install only.

## Install

See `docs/install/codex.md` for install instructions.

## Skills

| Skill | Path |
|---|---|
| fund-agent-e2e | `.agents/skills/fund-agent-e2e/SKILL.md` |
| fund-agent-privacy-audit | `.agents/skills/fund-agent-privacy-audit/SKILL.md` |
| fund-agent-setup-private-data | `.agents/skills/fund-agent-setup-private-data/SKILL.md` |
