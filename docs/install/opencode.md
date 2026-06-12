# OpenCode Install

This document describes the **first native install target** for
`fund-agent`: mounting it as an OpenCode plugin so the agent sees the
fund-agent skill catalog and can read the Markdown-first
`skills/<slug>/SKILL.md` documents.

The install is metadata + docs only. The Python runtime is **host-driven**:
the host owns data fetching, orchestration, MCP provider wiring, and
final user interaction. The plugin does not become an autonomous agent.

## Skill Surface (Superpowers-compatible)

`fund-agent` registers a **composable collection of Markdown skills**,
Superpowers-style: one hyphenated `skills/<slug>/SKILL.md` directory
per skill, with the directory name matching the frontmatter `name`
field. The collection is:

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
- `docs/host-integrations/opencode.md` — OpenCode cookbook and
  Mode A / Mode B boundary

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

There are three install modes. **Mode A** is the only one that runs
fund-agent code at OpenCode startup; **Mode B** lets OpenCode's
native Agent Skills discovery see the canonical Markdown skill
collection; **Mode C** is a future runtime bridge that is not
required today.

OpenCode itself distinguishes two things that are easy to conflate:

- **Plugins** — JavaScript / TypeScript modules loaded via the
  `plugin` field of `opencode.json`, or files under
  `.opencode/plugins/`. Plugins can add hooks, custom tools, and
  structured logging. The current `fund-agent` OpenCode install
  ships a plugin.
- **Agent Skills** — `SKILL.md` directories discovered from
  `.opencode/skills/<name>/SKILL.md`,
  `~/.config/opencode/skills/<name>/SKILL.md`, or
  `.agents/skills/<name>/SKILL.md`. OpenCode reads these natively
  and exposes them to the agent through its built-in `skill` tool.

Mode A uses the plugin mechanism only. Mode B makes the canonical
skill surface visible to OpenCode's native Agent Skills discovery
on top of Mode A. Mode C is documented for completeness.

### Mode A — Plugin metadata + doc-reader (optional, environment-dependent)

Mode A custom plugin tools are **optional and environment-dependent**. In the
verified test environment, `fund_agent_skills` returned `TOOL_UNAVAILABLE`,
meaning plugin custom tools were not registered in the current OpenCode session.
If `fund_agent_skills` returns `TOOL_UNAVAILABLE`, use the verified
**Mode B native Agent Skills** path instead. See
[opencode-troubleshooting.md](./opencode-troubleshooting.md).

The plugin is a project-local JavaScript file that lives under
`.opencode/plugins/`. OpenCode loads it at startup. The plugin can
also be referenced as an npm package in the `plugin` field of your
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
fund-agent v0.9.0 plugin loaded; primary skill: fund-analysis;
supporting skills: decision-support, news-research, sentiment-analysis,
thesis-generation
```

`fund-analysis` is the **primary / default skill**; the four
supporting skills are loaded only when their description matches
the subtask. See the `fund-analysis` SKILL.md "When to load
supporting skills" table for the matching policy.

> **Note:** If `fund_agent_skills` returns `TOOL_UNAVAILABLE` or
> project-local skills are not discovered, see
> [opencode-troubleshooting.md](./opencode-troubleshooting.md).

#### Plugin metadata only — no runtime bridge

The plugin exposes **only** the metadata + doc-reader
tools listed above. The plugin does not shell out to Python, does
not start a sidecar, and does not embed the deterministic Python
runtime. If the agent wants to actually invoke
`FundAnalysisSkill.run()` or `DecisionSupportSkill.run()`, it must
follow [`docs/install/manual-host.md`](./manual-host.md) for a
separate Python host integration.

This is a deliberate scope cut: the OpenCode install is about agent
**discoverability** of the skill catalog, not about wiring the Python
runtime into the agent's tool call path. Wiring a runtime bridge
through the OpenCode plugin would require either a sidecar process
(violates "no autonomous loop" constraint) or an embedded interpreter
(bloats the plugin and pulls in transitive npm deps), neither of which
is appropriate for the current release.

### Mode B — Native Agent Skills install (recommended, verified)

OpenCode's native `Agent Skills` discovery looks for `SKILL.md`
files under `.opencode/skills/<slug>/SKILL.md` (and the other
canonical locations above). Mode A is **not** enough on its own to
make the canonical skills visible to that native discovery — the
plugin only exposes the metadata + doc-reader tools.

Project-local `.opencode/skills` are discovered when OpenCode is
launched from the target project directory. On Windows/Git Bash,
prefer relative paths or `C:/Users/...` paths when invoking Python
install scripts.

To make the canonical Markdown skill collection visible to
OpenCode's native skill discovery, run the bundled sync helper:

```bash
# From the cloned fund-agent repo
python scripts/install_opencode_skills.py            # copy into .opencode/skills/
python scripts/install_opencode_skills.py --dry-run  # list what would be copied
python scripts/install_opencode_skills.py --target /elsewhere/.opencode/skills
python scripts/install_opencode_skills.py --clean    # remove only the skills this script wrote
```

The helper copies the five canonical hyphenated skill directories
(`fund-analysis`, `decision-support`, `news-research`,
`sentiment-analysis`, `thesis-generation`) from `skills/` into
`.opencode/skills/`. It writes a marker file
(`.opencode/skills/.fund-agent-generated.json`) so `--clean` can
remove only the skills it wrote, not user-authored files.

The helper is a **plain file copy**; it does not edit
`opencode.json`, does not install or call the Python runtime, and
does not start a subprocess. It is metadata + Markdown only.

After running the helper, OpenCode's native skill discovery will
see the same five skills as the plugin:

```
fund-analysis              (primary)
decision-support           (supporting)
news-research              (supporting)
sentiment-analysis         (supporting)
thesis-generation          (supporting)
```

Use Mode A + Mode B together if you want both the plugin's
metadata + doc-reader tools and OpenCode's native Agent Skills
discovery to see the fund-agent collection.

> **Note:** Project-local `.opencode/skills` are discovered only when
> OpenCode is launched from the target project directory. On
> Windows/Git Bash, prefer relative paths or `C:/Users/...` paths
> when invoking Python install scripts. See
> [opencode-troubleshooting.md](./opencode-troubleshooting.md) for
> details.

### Mode C — Future runtime bridge (design only)

The design for a future runtime bridge is documented in
[`docs/design/runtime-bridge.md`](../design/runtime-bridge.md). In
short, the plugin would optionally spawn a Python subprocess
(`python -m fund_agent.run_skill`) on demand and proxy
`SkillInput` / `SkillOutput` JSON in/out. This is **not implemented**
and is explicitly out of scope for the current release.

## Why a plugin and not just a config block

OpenCode already supports loading skill docs from
`.opencode/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md`,
and `.agents/skills/<name>/SKILL.md`. The current release ships the
`scripts/install_opencode_skills.py` helper (Mode B above) so the
canonical hyphenated `skills/<slug>/SKILL.md` directories can be
copied to one of those locations on demand.

The plugin approach was chosen because:

1. Mode A (the plugin) works without any user-side file copying
   and provides the three `fund_agent_*` tools even before Mode B
   has been run.
2. It gives us a single integration surface for the
   `fund_agent_skills` / `fund_agent_skill_doc` /
   `fund_agent_runtime_hint` tools, with the manifest runtime ID
   → doc slug mapping held in code where it can be tested.
3. Mode B (the native skill sync helper) is layered on top of Mode
   A: it is opt-in, idempotent, and safe (`--clean` only removes
   files this script wrote, marked by
   `.opencode/skills/.fund-agent-generated.json`).
4. The plugin is a small, honest change: zero runtime
   dependencies, no provider SDKs, no network IO, and verified
   only for file presence and metadata (not for "this works
   inside OpenCode" — that requires running OpenCode itself, which
   is out of scope for the test gate).

## Verifying the install

### Manual verification

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

### Automated verification

The `verify_install_discovery.py` script automates install discovery
checks:

```bash
python scripts/verify_install_discovery.py \
  --project ../demo-project \
  --fund-agent-root . \
  --json
```

Skip runtime bridge subprocess checks:

```bash
python scripts/verify_install_discovery.py \
  --project ../demo-project \
  --fund-agent-root . \
  --skip-runtime \
  --json
```

This script does **not** verify `fund_agent_skills` custom tool
registration. It verifies native Agent Skills files, manifest roles,
and optionally runtime bridge readiness. Mode A custom tools remain
environment-dependent. Mode B native Agent Skills remain the
recommended verified path.

See [opencode-troubleshooting.md](./opencode-troubleshooting.md) for
the full troubleshooting guide.

## Pinning / version management

`fund-agent` uses git tags for versioning. The current version is
`v0.9.0` and matches the `VERSION` file, the `package.json` `version`
field, and the `skillpack/fund-agent.skillpack.yaml` `version` field.

Pin to a specific version:

```bash
git clone --branch v0.9.0 https://github.com/EXASHXE/fund-agent.git
cd fund-agent
git checkout v0.9.0 # if you cloned without --branch
```

For a project that already has the symlink in place, update the
checkout:

```bash
cd /path/to/fund-agent
git fetch
git checkout v0.9.0
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
- For a process-boundary host: see
  `docs/install/runtime-bridge-cli.md`.
- For OpenClaw / Hermes: see `docs/host-compatibility.md` for what is
  supported today. No native installer is shipped.

## Honesty about current capability

- ✅ OpenCode can **discover** fund-agent skills via this plugin
  (Mode A).
- ✅ OpenCode can **discover** the same five canonical skills via
  its native Agent Skills directory discovery **if** Mode B
  (`python scripts/install_opencode_skills.py`) has been run
  (the plugin alone does not install the native skill
  directories).
- ✅ OpenCode can **read** any `skills/<slug>/SKILL.md` or
  `skills/<slug>/references/*.md` via `fund_agent_skill_doc`.
- ✅ OpenCode can **map** runtime IDs to doc slugs via
  `fund_agent_skills`.
- ❌ OpenCode cannot yet **invoke** the Python runtime skills directly
  through the plugin. That requires the manual host integration flow
  (or the runtime bridge CLI, which is host-invoked, not
  plugin-invoked).
- ❌ OpenCode cannot yet **fetch** NAV, news, or sentiment. The host
  must own those calls.
- ❌ The plugin does not implement an autonomous agent loop. OpenCode owns orchestration and planning.

The OpenCode install is therefore a discoverability + docs layer, not
a runtime bridge. The runtime bridge CLI
([`docs/install/runtime-bridge-cli.md`](./runtime-bridge-cli.md)) is
a **separate**, host-invoked surface that the OpenCode plugin does
not shell out to and does not depend on.
