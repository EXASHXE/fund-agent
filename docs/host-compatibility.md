# Host Compatibility Matrix

`fund-agent` is a host-agnostic skill pack. It does not depend on any specific
agent host runtime. All hosts should treat `skillpack/fund-agent.skillpack.yaml`
as the entrypoint.

Hosts should also read the Markdown-first skill docs at
`skills/<slug>/SKILL.md` for usage policy. The manifest supplies runtime skill
IDs such as `fund_analysis`; hyphenated folders such as `fund-analysis` are
documentation slugs only. `fund-analyst` is legacy/reference-only material.

For host-specific cookbooks, see
[`docs/host-integrations/README.md`](./host-integrations/README.md).

## Matrix

| Host | Reads manifest | Resolves runtime | Injects MCP adapter | Runs SkillInput/SkillOutput | External orchestration | Native install | Notes |
|---|---|---|---|---|---|---|---|
| OpenCode | Yes | Yes | Yes | Yes | Yes | Yes (metadata + docs only) | See `docs/install/opencode.md` |
| Claude Code | Yes | Yes | Yes | Yes | Yes | Manual only | Skill tool invocation; host owns planning |
| Codex | Yes | Yes | Yes | Yes | Yes | Manual / light | See `docs/install/codex.md` |
| OpenClaw | Yes | Yes | Yes | Yes | Yes | Manual only | Plugin contract alignment required |
| Hermes | Yes | Yes | Yes | Yes | Yes | Manual only | Agent host owns full orchestration loop |
| Generic Python Host | Yes | Yes | Yes | Yes | Yes | Yes (manual) | See `docs/install/manual-host.md` |

## Integration Principles

1. **Entrypoint:** `skillpack/fund-agent.skillpack.yaml`
2. **Orchestration:** Owned by external host
3. **MCP Providers:** Injected by external host via `MCPHostAdapter`
4. **Provider SDKs:** Not shipped with fund-agent
5. **ResearchOS:** Historical reference only (see `v0.1.0-skillpack-alpha` tag); not required for host integration
6. **Minimal Demo:** `examples/minimal_host_news_to_decision.py`
7. **Skill Docs:** `skills/<slug>/SKILL.md` is policy, not discovery
8. **Directory Names:** Do not infer runtime skill IDs from folder names
9. **Install Surface:**
   - OpenCode: `docs/install/opencode.md` (first native target, metadata + docs only)
   - Manual / Python host: `docs/install/manual-host.md`
   - Codex: `docs/install/codex.md` (manual / light)
   - Other harnesses: follow the manual host install; native installers are
     available for OpenCode only (Mode A/B); other hosts use manual Python
     integration.

## Install Reality Check

The OpenCode install is a thin plugin wrapper that exposes a
`fund_agent_skills` tool, a `fund_agent_skill_doc` tool, and a
`fund_agent_runtime_hint` tool. It does **not** run the Python runtime
from inside the OpenCode plugin. The plugin is metadata +
docs only (Mode A/B). The runtime bridge CLI (`scripts/run_skill.py`)
is available for source-checkout and manual-host users as a thin,
host-invoked JSON CLI. A deeper OpenCode plugin runtime wrapper
remains future, as documented in `docs/design/runtime-bridge.md`.

## Host Requirements

- Python >= 3.11
- Ability to import `src.skillpack.loader` and `src.schemas.skill`
- Implement `MCPHostAdapter` for skills requiring MCP data
- Own retry policy and provider credentials
