# fund-agent — OpenCode Install (project-local)

> Goal: mount `fund-agent` as a project-local OpenCode plugin so the agent
> sees the fund-agent skill catalog and can read the Markdown-first
> `skills/<slug>/SKILL.md` documents.
>
> Scope of this milestone: **Markdown-first skill install only.** The
> Python runtime is optional and host-driven. There is no autonomous
> agent loop in this plugin.

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
  IDs and their hyphenated doc slugs
- register a `fund_agent_skill_doc` tool that returns the contents of a
  specific `skills/<slug>/SKILL.md`
- register a `fund_agent_runtime_hint` tool that returns the runtime
  Python class path for a given runtime skill ID, plus a pointer to
  `docs/install/manual-host.md` for the deterministic Python integration
  flow

These tools do **not** fetch data, do **not** place trades, and do
**not** call any LLM. They are pure metadata + doc readers.

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

> **Note:** As of v0.4.3, the npm package is declared but not yet
> published. Use the project-local install above until the npm
> publication milestone is cut. The install will still work end-to-end
> via the project-local path; only the npm convenience install is
> pending.

## Pin to a specific version (git tag)

```bash
git clone --branch v0.4.3 https://github.com/EXASHXE/fund-agent.git
```

or, for a fully reproducible symlink, pin the commit:

```bash
git clone https://github.com/EXASHXE/fund-agent.git
cd fund-agent
git checkout v0.4.3
# then create the symlink as above
```

For development, the project-local install with `master` is fine.

## Verify the install

After restarting OpenCode in your project:

1. Check the logs. You should see a line such as:
   `fund-agent v0.4.3 plugin loaded; skills: fund-analysis, news-research, sentiment-analysis, thesis-generation, decision-support`
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
