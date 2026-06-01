# OpenCode Install

This document describes the **first native install target** for
`fund-agent`: mounting it as an OpenCode plugin so the agent sees the
fund-agent skill catalog and can read the Markdown-first
`skills/<slug>/SKILL.md` documents.

The install is metadata + docs only. The Python runtime is **host-driven**:
the host owns data fetching, orchestration, MCP provider wiring, and
final user interaction. The plugin does not become a planner loop.

## Skill Surface (Superpowers-compatible)

`fund-agent` registers a **composable collection of Markdown skills**,
Superpowers-style: one hyphenated `skills/<slug>/SKILL.md` directory
per skill, with the directory name matching the frontmatter `name`
field. The collection in v0.4.4+ is:

- **Primary / default skill:** `fund-analysis`. Start here for
  ordinary fund / portfolio report requests. `fund-analysis` alone is
  sufficient for a report-only flow.
- **Supporting skills:** `decision-support`, `news-research`,
  `sentiment-analysis`, `thesis-generation`. Load a supporting skill
  only when its description matches the subtask, and only after the
  primary skill (or equivalent evidence) is in scope.

The OpenCode plugin exposes **only** the five hyphenated skill slugs
above as agent-facing skill names. It does **not** expose underscore
runtime IDs (`fund_analysis`, `decision_support`, …) as agent-facing
skill names. The Python runtime IDs are still discoverable via the
`fund_agent_runtime_hint` tool, which maps a hyphenated slug **or** an
underscore runtime ID to the same Python class path.

For other harnesses see:

- `docs/install/manual-host.md` — manual / Python host install
- `docs/install/codex.md` — Codex install (manual, light)
- `docs/host-compatibility.md` — full host compatibility matrix

## What this install actually does

`fund-agent` is a host-agnostic, Markdown-first financial research
skill pack. The OpenCode install exposes a tiny plugin entrypoint that:

1. Logs that the plugin is loaded and which hyphenated skills are
   available.
2. Registers a `fund_agent_skills` tool that returns the manifest
   runtime IDs and their hyphenated agent-facing doc slugs.
3. Registers a `fund_agent_skill_doc` tool that returns the contents of
   a specific `skills/<slug>/SKILL.md` (accepts hyphenated slugs only;
   rejects underscore slugs and the archived `fund-analyst` slug).
4. Registers a `fund_agent_runtime_hint` tool that maps a hyphenated
   agent-facing slug **or** an underscore runtime ID to the Python
   runtime class path, plus a pointer to the manual host integration
   flow for the deterministic Python runtime.

The plugin does **not**:

- become an autonomous planner or agent loop
- fetch NAV, holdings, news, or sentiment data
- place trades or call any broker API
- import provider SDKs (Tavily, Finnhub, Exa, Firecrawl, Reddit,
  AkShare, OpenAI, Anthropic, LangChain)
- require a running Python interpreter at the OpenCode side

In other words, the OpenCode install gives the agent **read access** to
the fund-agent skill catalog. The agent still owns planning, MCP
provider wiring, retries, memory, and final user interaction. The host
owns data fetching and orchestration. The host injects provider
implementations through `MCPHostAdapter`; the plugin does not
synthesize them.

## Install modes

There are two install modes. **Mode 1** is the only one shipped in
v0.4.4. **Mode 2** is a future runtime bridge; it is not required to
use `fund-agent` today.

### Mode 1 — Markdown-only skill install (current target)

The plugin is a project-local JavaScript file that lives under
`.opencode/plugins/`. OpenCode loads it at startup. The plugin can also
be referenced as an npm package in the `plugin` field of your
project's `opencode.json` config.

The full step-by-step is in [`.opencode/INSTALL.md`](../../.opencode/INSTALL.md).
The short version is:

```bash
# 1. Clone fund-agent
git clone https://github.com/EXASHXE/fund-agent.git

# 2. Wire the plugin into YOUR project
cd /path/to/your-project
ln -s /absolute/path/to/fund-agent/opencode.plugin.js .opencode/plugins/fund-agent.js
```

Restart OpenCode and you should see in the logs:

```
fund-agent v0.4.4 plugin loaded; primary skill: fund-analysis;
supporting skills: fund-analysis, decision-support, news-research,
sentiment-analysis, thesis-generation
```

#### Plugin metadata only — no runtime bridge

For v0.4.4 the plugin exposes **only** the metadata + doc-reader tools
listed above. The plugin does not shell out to Python, does not start a
sidecar, and does not embed the deterministic Python runtime. If the
agent wants to actually invoke `FundAnalysisSkill.run()` or
`DecisionSupportSkill.run()`, it must follow
[`docs/install/manual-host.md`](./manual-host.md) for a separate Python
host integration.

This is a deliberate scope cut: the OpenCode install is about agent
**discoverability** of the skill catalog, not about wiring the Python
runtime into the agent's tool call path. Wiring a runtime bridge
through the OpenCode plugin would require either a sidecar process
(violates "no autonomous loop" constraint) or an embedded interpreter
(bloats the plugin and pulls in transitive npm deps), neither of which
is appropriate for v0.4.4.

### Mode 2 — Future runtime bridge (not in v0.4.4)

The design for a future runtime bridge is documented in
[`docs/design/runtime-bridge.md`](../design/runtime-bridge.md). In
short, the plugin would optionally spawn a Python subprocess
(`python -m fund_agent.run_skill`) on demand and proxy
`SkillInput` / `SkillOutput` JSON in/out. This is **not implemented in
v0.4.4** and is explicitly out of scope for this milestone.

## Why a plugin and not just a config block

OpenCode already supports loading skill docs from
`.opencode/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md`,
and `.agents/skills/<name>/SKILL.md`. A future fund-agent install could
symlink those locations into the cloned `skills/<slug>/` directory
instead of shipping a JavaScript plugin at all.

The plugin approach was chosen for v0.4.4 because:

1. It works without any symlink gymnastics from the user's side.
2. It gives us a single integration surface for the
   `fund_agent_skills` / `fund_agent_skill_doc` /
   `fund_agent_runtime_hint` tools.
3. It keeps the manifest runtime ID → doc slug mapping in code, where
   it can be tested, rather than relying on filesystem layout.
4. It is a small, honest change: the plugin is ~50 lines, has zero
   runtime dependencies, and is verified only for file presence and
   metadata (not for "this works inside OpenCode" — that requires
   running OpenCode itself, which is out of scope for the test gate).

If OpenCode's `Agent Skills` feature proves to be a better fit, the
plugin can be slimmed down in a future milestone. The
`docs/design/runtime-bridge.md` doc calls this out.

## Verifying the install

```bash
# 1. Confirm the symlink / file is in place
ls -la .opencode/plugins/fund-agent.js

# 2. Confirm the target file exists and is readable
head -5 /path/to/fund-agent/opencode.plugin.js

# 3. Restart OpenCode and look for the load log
# 4. In a chat, ask the agent to use the fund_agent_skills tool
```

Tests that validate file presence and metadata live under
`tests/install/`. They do **not** attempt to execute OpenCode itself;
they assert that the install artifacts are coherent and honest.

## Pinning / version management

`fund-agent` uses git tags for versioning. The current version is
`v0.4.4` and matches the `VERSION` file, the `package.json` `version`
field, and the `skillpack/fund-agent.skillpack.yaml` `version` field.

Pin to a specific version:

```bash
git clone --branch v0.4.4 https://github.com/EXASHXE/fund-agent.git
cd fund-agent
git checkout v0.4.4   # if you cloned without --branch
```

For a project that already has the symlink in place, update the
checkout:

```bash
cd /path/to/fund-agent
git fetch
git checkout v0.4.4
# restart OpenCode
```

## Separate installs for other harnesses

This install is **OpenCode-specific**. The `.opencode/` directory and
the `opencode.plugin.js` file are not used by any other harness.

- For Claude Code: see the manual install in
  `docs/install/manual-host.md` (or use the project-local skill
  discovery under `.claude/skills/<name>/SKILL.md`).
- For Codex: see `docs/install/codex.md`.
- For a generic Python host: see `docs/install/manual-host.md`.
- For OpenClaw / Hermes: see `docs/host-compatibility.md` for what is
  supported today. No native installer is shipped in v0.4.4.

## Honesty about current capability

- ✅ OpenCode can **discover** fund-agent skills via this plugin.
- ✅ OpenCode can **read** any `skills/<slug>/SKILL.md` or
  `skills/<slug>/references/*.md` via `fund_agent_skill_doc`.
- ✅ OpenCode can **map** runtime IDs to doc slugs via
  `fund_agent_skills`.
- ❌ OpenCode cannot yet **invoke** the Python runtime skills directly
  through the plugin. That requires the manual host integration flow.
- ❌ OpenCode cannot yet **fetch** NAV, news, or sentiment. The host
  must own those calls.
- ❌ The plugin does not implement a planner loop. OpenCode owns that.

The OpenCode install is therefore a discoverability + docs layer, not
a runtime bridge. This is the smallest honest step toward
installable-skillpack that does not violate the host-agnostic
architecture constraints.
