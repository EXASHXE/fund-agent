# fund-agent — OpenCode Install (project-local)

> Goal: mount `fund-agent` as a project-local OpenCode plugin so the agent
> sees the fund-agent skill catalog and can read the Markdown-first
> `skills/<slug>/SKILL.md` documents.
>
> Scope of this milestone: **Superpowers-compatible Markdown-first skill
> install only.** OpenCode registers a **composable collection of
> hyphenated Markdown skills** (one directory per skill, name matching
> the directory). The Python runtime is optional and host-driven.
> There is no autonomous agent loop in this plugin.

## Install modes (Mode A / Mode B / Mode C)

There are three install modes for the OpenCode side. **Mode A** is
the only one that runs fund-agent code at OpenCode startup;
**Mode B** lets OpenCode's native `Agent Skills` discovery see the
canonical Markdown skill collection; **Mode C** is a future runtime
bridge that is not implemented in v0.4.6 (or any prior release).

- **Mode A — Plugin metadata + doc-reader (current target).** A
  project-local `opencode.plugin.js` registers three custom tools
  (`fund_agent_skills`, `fund_agent_skill_doc`,
  `fund_agent_runtime_hint`) and logs at startup. The plugin does
  **not** shell out to Python and does **not** implement a
  planner loop. This is what `fund-agent` ships in the npm package
  and as the symlink target below.
- **Mode B — Native Agent Skills install (optional).** Runs
  `python scripts/install_opencode_skills.py` to copy the five
  canonical `skills/<slug>/SKILL.md` directories into a target
  OpenCode Agent Skills directory. Mode B is **git-clone-only** in
  v0.4.6: the helper is part of the source checkout, not the npm
  package.
- **Mode C — Future runtime bridge (design only).** Documented at
  `docs/design/runtime-bridge.md`. Not implemented in any shipped
  release.

Use Mode A (the plugin) alone if you only need the metadata +
doc-reader tools. Use Mode A + Mode B together if you also want
OpenCode's native `Agent Skills` discovery to see the same five
skills.

## Package contents — npm vs git

The `package.json` at the repo root declares what ships in the
npm package (Mode A only) and what is git-clone-only.

**npm package contents** (Mode A only, no runtime, no helpers):

- `package.json` — package metadata.
- `opencode.plugin.js` — the Mode A plugin entrypoint.
- `skillpack/` — the manifest, contracts, tools, capabilities,
  examples, and schema.
- `skills/<slug>/SKILL.md` and `skills/<slug>/references/*.md` for
  the five canonical hyphenated skills.
- `docs/install/opencode.md`, `docs/install/manual-host.md`,
  `docs/install/codex.md` — install docs.
- `README.md` — the package README.

**Git-clone-only contents** (not in the npm package):

- `scripts/install_opencode_skills.py` — the Mode B sync helper.
  Run this from a clone of the repo.
- `.opencode/INSTALL.md` — this file (the project-local install
  guide).
- `src/`, `tests/`, `examples/`, `docs/` (other than `docs/install/`)
  — Python source, tests, host demos, and the rest of the
  documentation.
- `legacy/`, `docs/archive/`, `docs/design/runtime-bridge.md` —
  the legacy pointer, the archived `fund-analyst` persona
  material, and the future runtime bridge design doc.
- `CHANGELOG.md`, `AGENTS.md`, `docs/release-checklist.md` —
  developer and release docs.

This split keeps the npm package small and honest: a user who
installs the npm package gets a metadata + doc-reader plugin and
the skill docs, with no Python runtime, no tests, no archive
material, and no Mode B helper. A user who clones the git repo
gets the full source tree, including the Mode B helper, all
install docs, the Python runtime, and the host demos.

## Prerequisites

- OpenCode installed (https://opencode.ai)
- `git` installed
- Optional: Python 3.11+ if you also want to run the Python runtime
  examples (see `docs/install/manual-host.md`)

## Install (project-local, git-backed)

`fund-agent` ships a small OpenCode plugin entrypoint and a `package.json`
at the repository root. The plugin is a JavaScript module that follows
the OpenCode plugin contract; it does **not** bundle any provider SDKs
and does **not** run an autonomous loop.

The recommended project-local install is a symlink into OpenCode's
project-level plugin directory:

```bash
# 1. Clone the fund-agent repo anywhere on disk
git clone https://github.com/EXASHXE/fund-agent.git
cd fund-agent

# 2. Wire the plugin into your OpenCode project
#    (run from YOUR project, not from inside the fund-agent clone)
cd /path/to/your-project
ln -s /absolute/path/to/fund-agent/opencode.plugin.js .opencode/plugins/fund-agent.js
```

After restarting OpenCode, the plugin will:

- log that `fund-agent vX.Y.Z` is loaded
- register a `fund_agent_skills` tool that returns the manifest runtime
  IDs and their hyphenated doc slugs (the agent-facing skill names)
- register a `fund_agent_skill_doc` tool that returns the contents of a
  specific `skills/<slug>/SKILL.md` (the agent-facing slugs only; the
  plugin rejects underscore doc slugs)
- register a `fund_agent_runtime_hint` tool that maps a hyphenated
  agent-facing slug **or** a Python runtime ID to the runtime class
  path, plus a pointer to `docs/install/manual-host.md` for the
  deterministic Python integration flow

These tools do **not** fetch data, do **not** place trades, and do
**not** call any LLM. They are pure metadata + doc readers.

## Skill collection

OpenCode will discover the **composable Markdown skill collection** under
`skills/<slug>/SKILL.md`. The collection in v0.4.6+ is:

- **Primary / default:** `fund-analysis` — start here for ordinary
  fund analysis and report requests.
- **Supporting:** `decision-support`, `news-research`,
  `sentiment-analysis`, `thesis-generation` — load only when the
  subtask matches.

The plugin does **not** expose:

- underscore skill slugs (`fund_analysis`, `news_research`, …) as
  agent-facing skill names;
- the archived legacy persona directory (formerly at
  `skills/fund-analyst/`, now under `docs/archive/fund-analyst/`);
- any other `skills/` directory that lacks a canonical `SKILL.md`
  with a hyphenated `name` frontmatter field.

Python runtime IDs remain underscore names. Hosts call
`fund_agent_runtime_hint` with the hyphenated slug **or** the
underscore runtime ID; both resolve to the same Python class.

## Install (Mode B — native Agent Skills)

OpenCode's native `Agent Skills` discovery looks for `SKILL.md`
files under `.opencode/skills/<slug>/SKILL.md`,
`~/.config/opencode/skills/<slug>/SKILL.md`, or
`.agents/skills/<slug>/SKILL.md`. The plugin alone (Mode A) does
**not** install the canonical skills into those locations — the
plugin only exposes the metadata + doc-reader tools.

To make the canonical skill surface visible to OpenCode's native
skill discovery, run the bundled sync helper from the cloned
fund-agent repo:

```bash
# Copy the five canonical hyphenated skills into .opencode/skills/
python scripts/install_opencode_skills.py

# Or preview what would be copied
python scripts/install_opencode_skills.py --dry-run

# Or copy into a different target
python scripts/install_opencode_skills.py --target /elsewhere/.opencode/skills

# Or remove only the skills this script wrote
python scripts/install_opencode_skills.py --clean
```

The helper is a plain file copy: it writes
`SKILL.md` and `references/` for each canonical skill and a
marker file `.opencode/skills/.fund-agent-generated.json` so
`--clean` can remove only the skills it wrote, not user-authored
files. The helper does not edit `opencode.json`, does not start
the Python runtime, and does not spawn a subprocess.

After running the helper, OpenCode's native skill tool will see
the same five skills as the plugin:

- `fund-analysis` (primary)
- `decision-support` (supporting)
- `news-research` (supporting)
- `sentiment-analysis` (supporting)
- `thesis-generation` (supporting)

Use Mode A (the plugin) and Mode B (the sync helper) together if
you want both the plugin's `fund_agent_*` tools and OpenCode's
native Agent Skills discovery to see the fund-agent collection.

## Install (npm-published package)

If you prefer npm-style install, `fund-agent` also declares a
`package.json` whose `main` points at the same plugin entrypoint. If the
package is published to the npm registry under the name `fund-agent`,
add it to your `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["fund-agent"]
}
```

OpenCode will install it via Bun at startup and cache it under
`~/.cache/opencode/node_modules/`.

> **Note (v0.4.6):** the npm package is **declared but not yet
> published**. Use the project-local install above until the npm
> publication milestone is cut. The install will still work
> end-to-end via the project-local path; only the npm convenience
> install is pending.

### What the npm package actually contains (and what it does not)

The `package.json` `files` field is the authoritative list of what
ships in the npm tarball. The v0.4.6 npm package is **Mode A only**:
the plugin entrypoint, the skillpack manifest and examples, the
five canonical hyphenated `skills/<slug>/SKILL.md` directories and
their `references/`, and the three install docs. It does **not**
include the Mode B sync helper (`scripts/install_opencode_skills.py`),
the Python runtime, the tests, the host demos, the archived
`fund-analyst` persona, or the legacy pointer.

If a user installs the npm package and also wants Mode B (the
native `Agent Skills` directory copy), they must run
`scripts/install_opencode_skills.py` from a git clone of the repo,
not from the npm package. This is the same helper documented in
the "Install (Mode B — native Agent Skills)" section above. The
separation is intentional: the npm package is small, dependency-
free, and ships a pure metadata + doc reader; the git clone ships
the full source tree including the sync helper.

The exact file list is verified by
`tests/install/test_npm_pack_contents.py` (runs `npm pack
--dry-run --json` and asserts both the required and forbidden
paths). That test is the v0.4.6 install-packaging-smoke guard.

## Pin to a specific version (git tag)

```bash
git clone --branch v0.4.6 https://github.com/EXASHXE/fund-agent.git
```

or, for a fully reproducible symlink, pin the commit:

```bash
git clone https://github.com/EXASHXE/fund-agent.git
cd fund-agent
git checkout v0.4.6
# then create the symlink as above
```

For development, the project-local install with `master` is fine.

## Verify the install

After restarting OpenCode in your project:

1. Check the logs. You should see a line such as:
   `fund-agent v0.4.6 plugin loaded; primary skill: fund-analysis; supporting skills: decision-support, news-research, sentiment-analysis, thesis-generation`
   `fund-analysis` is the **primary / default skill**; the four
   supporting skills are loaded only when their description matches
   the subtask (see the `fund-analysis` SKILL.md "When to load
   supporting skills" table).
2. Ask the agent to use the `fund_agent_skills` tool. It should return
   a JSON list of the five manifest runtime skill IDs and their doc
   slugs.
3. Ask the agent to read `skills/fund-analysis/SKILL.md` via
   `fund_agent_skill_doc` with `slug: "fund-analysis"`. It should
   return the file contents.

If the plugin is not loaded, see the troubleshooting section below.

## What this plugin does NOT do

- It does not become an autonomous ResearchOS / Planner loop.
- It does not fetch NAV, holdings, news, or sentiment data.
- It does not place trades or call any broker API.
- It does not import provider SDKs (Tavily, Finnhub, Exa, Firecrawl,
  Reddit, AkShare, OpenAI, Anthropic, LangChain).
- It does not run a Python interpreter. Python runtime integration is
  host-driven; see `docs/install/manual-host.md`.
- It does not expose underscore skill slugs or the archived legacy
  persona directory as agent-facing skills. The persona material is
  historical reference only and is not a runtime entrypoint.

The agent host (OpenCode) owns planning, MCP provider wiring, and
final user interaction. `fund-agent` provides deterministic skill
descriptions, Markdown docs, and the optional Python runtime.

## Troubleshooting

### Plugin not loading

- Confirm the symlink target is an absolute path and the file exists.
- Confirm the symlink lives directly under `.opencode/plugins/` and
  ends in `.js`.
- Restart OpenCode. The plugin loader reads `opencode.json` and
  `.opencode/plugins/` once at startup.

### Skills not found

- Confirm the symlink target points at the **root** of the fund-agent
  repo, not at a subdirectory.
- Confirm `skills/README.md` and `skills/fund-analysis/SKILL.md` exist
  in the cloned repo.
- The plugin only ships the manifest; it does not synthesize missing
  docs.

### Python runtime not available

The Python runtime is **optional** for the OpenCode install. The
Markdown skill layer is fully usable without it. If you want to call
`FundAnalysisSkill` / `DecisionSupportSkill` etc. from Python, follow
`docs/install/manual-host.md`.

### Windows / WSL

- Use forward slashes in the symlink target.
- If `ln -s` is not available, copy the file instead:
  `cp /path/to/fund-agent/opencode.plugin.js .opencode/plugins/fund-agent.js`
- OpenCode on Windows is supported via WSL; see
  https://opencode.ai/docs/windows-wsl.

## Update / uninstall

Update:

```bash
cd /path/to/fund-agent
git pull
# restart OpenCode
```

Uninstall:

```bash
cd /path/to/your-project
rm .opencode/plugins/fund-agent.js
# restart OpenCode
```

## Separate installs for other harnesses

This install path is for **OpenCode only**. Other harnesses (Claude
Code, Codex, OpenClaw, Hermes, or any Python host) have their own
install instructions:

- Manual / Python host: `docs/install/manual-host.md`
- Codex: `docs/install/codex.md`
- Claude Code, OpenClaw, Hermes: manual install for now; see
  `docs/host-compatibility.md` for what is supported.
