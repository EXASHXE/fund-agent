# Host Compatibility Matrix

`fund-agent` is a host-agnostic skill pack. It does not depend on any specific
agent host runtime. All hosts should treat `skillpack/fund-agent.skillpack.yaml`
as the entrypoint.

Hosts should also read the Markdown-first skill docs at
`skills/<slug>/SKILL.md` for usage policy. The manifest supplies runtime skill
IDs such as `fund_analysis`; hyphenated folders such as `fund-analysis` are
documentation slugs only. `fund-analyst` is legacy/reference-only material.

## Matrix

| Host | Reads manifest | Resolves runtime | Injects MCP adapter | Runs SkillInput/SkillOutput | External orchestration | Notes |
|---|---|---|---|---|---|---|
| OpenCode | Yes | Yes | Yes | Yes | Yes | Read AGENTS.md, load skillpack manifest, call runtime skills |
| Claude Code | Yes | Yes | Yes | Yes | Yes | Skill tool invocation; host owns planning |
| Codex | Yes | Yes | Yes | Yes | Yes | Manifest-driven skill discovery |
| OpenClaw | Yes | Yes | Yes | Yes | Yes | Plugin contract alignment required |
| Hermes | Yes | Yes | Yes | Yes | Yes | Agent host owns full orchestration loop |
| Generic Python Host | Yes | Yes | Yes | Yes | Yes | See `examples/minimal_host_news_to_decision.py` |

## Integration Principles

1. **Entrypoint:** `skillpack/fund-agent.skillpack.yaml`
2. **Orchestration:** Owned by external host
3. **MCP Providers:** Injected by external host via `MCPHostAdapter`
4. **Provider SDKs:** Not shipped with fund-agent
5. **ResearchOS:** Not required for host integration
6. **Minimal Demo:** `examples/minimal_host_news_to_decision.py`
7. **Skill Docs:** `skills/<slug>/SKILL.md` is policy, not discovery
8. **Directory Names:** Do not infer runtime skill IDs from folder names

## Host Requirements

- Python >= 3.11
- Ability to import `src.skillpack.loader` and `src.schemas.skill`
- Implement `MCPHostAdapter` for skills requiring MCP data
- Own retry policy and provider credentials
