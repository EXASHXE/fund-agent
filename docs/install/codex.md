# Codex Install

> Scope: **manual / light install** for Codex in v0.4.3. There is no
> OMO-style Codex installer in this milestone. The intent is to keep
> Codex working with `fund-agent` through the same host-agnostic
> skill-pack flow that the Python and OpenCode installs use, without
> writing a fragile auto-installer that depends on Codex internals.

## What this install actually gives you

After following this document, Codex can:

- Discover the five fund-agent manifest skills from
  `skillpack/fund-agent.skillpack.yaml`.
- Read `skills/<slug>/SKILL.md` for agent-facing workflow, policy, and
  report style.
- Call the Python runtime through a host-side wrapper, if a Python
  interpreter is available.

It will **not**:

- Auto-install via a Codex-specific `~/.codex/config.toml` plugin
  block. We are not writing that file in v0.4.3.
- Behave like an OMO-style bundle. There is no Codex marketplace entry
  in v0.4.3.
- Fetch NAV, news, or sentiment. The host owns data fetching. The
  plugin / skill pack does not synthesize data; the host must wire
  provider implementations.

Codex as the host agent owns planning, MCP provider wiring, retries,
memory, and final user interaction. The fund-agent skill pack is
host-driven. The host injects any data the agent needs.

## Why no OMO-style installer in v0.4.3

A "Codex plugin" in the OMO sense would require either:

1. A Codex-specific config block in `~/.codex/config.toml` or
   `.codex/config.toml`, or
2. A Codex plugin cache / marketplace publication.

Both of those depend on Codex platform internals that change
frequently, and either path would lock the install to a specific
Codex version. The current Codex plugin spec is not yet stable enough
to be a host-agnostic installer target.

The honest, version-independent path is the same manual / light
install that any Python host uses, plus a pointer from Codex
project instructions to the fund-agent skill pack manifest.

## Prerequisites

- A Codex-capable environment with Codex installed.
- `git`.
- Optional: Python 3.11+ if you want to call the Python runtime from
  Codex. If you only want the Markdown skill layer, Python is not
  required.

## Install

### 1. Clone the skill pack

```bash
git clone https://github.com/EXASHXE/fund-agent.git
cd fund-agent
```

Pin a specific version:

```bash
git clone --branch v0.4.3 https://github.com/EXASHXE/fund-agent.git
cd fund-agent
```

### 2. Expose the skill pack to Codex

Codex reads project instructions and any skill-pack-style surfaces
its host supports. The most robust, version-independent way to
expose `fund-agent` to Codex is to point Codex at the cloned repo in
one of two ways:

**Option A — Codex project instructions (recommended).** Add the
following snippet to your Codex project instructions (e.g.
`.codex/AGENTS.md`, `.codex/PROJECT.md`, or whatever your Codex
deployment uses for project-level system context):

```text
# External skill pack: fund-agent
# Repo: https://github.com/EXASHXE/fund-agent
# Path on this machine: /absolute/path/to/fund-agent

Discovery entrypoint: /absolute/path/to/fund-agent/skillpack/fund-agent.skillpack.yaml
Skill docs: /absolute/path/to/fund-agent/skills/<slug>/SKILL.md
Skill doc slugs: fund-analysis, news-research, sentiment-analysis,
                 thesis-generation, decision-support

When the user asks for fund analysis, news research, sentiment
analysis, thesis generation, or decision support, read the
corresponding SKILL.md from the path above, then use the manifest
runtime IDs to call the Python runtime as described in
docs/install/manual-host.md.
```

**Option B — Vendor the skill docs into the Codex skill surface.**
If your Codex deployment supports a project-level `skills/` directory
analogous to OpenCode's `.opencode/skills/<name>/SKILL.md` or
Claude Code's `.claude/skills/<name>/SKILL.md`, you can copy or
symlink the relevant fund-agent skill docs into that location:

```bash
# Example: symlink into a Codex-style skill directory
ln -s /absolute/path/to/fund-agent/skills/fund-analysis .codex/skills/fund-analysis
ln -s /absolute/path/to/fund-agent/skills/news-research .codex/skills/news-research
ln -s /absolute/path/to/fund-agent/skills/sentiment-analysis .codex/skills/sentiment-analysis
ln -s /absolute/path/to/fund-agent/skills/thesis-generation .codex/skills/thesis-generation
ln -s /absolute/path/to/fund-agent/skills/decision-support .codex/skills/decision-support
```

If Codex does not have a `skills/` directory convention yet, prefer
Option A. The agent will discover the docs from the manifest and the
absolute path.

### 3. (Optional) Wire the Python runtime

If you want Codex to actually invoke the deterministic Python runtime
(`FundAnalysisSkill.run(...)` and friends), follow
[`docs/install/manual-host.md`](./manual-host.md) for the
`pip install -e .` step and the in-memory adapter pattern. Codex is
treated as just another Python host in that flow.

If you only want Codex to **read** the skill docs and use the
knowledge embedded in them (without invoking the Python runtime),
skip the Python step. The Markdown layer is fully usable on its own.

## Verify

1. In a Codex session, ask: "List the fund-agent skills."
   The agent should reference the manifest and return the five
   runtime IDs.
2. Ask: "Read `skills/fund-analysis/SKILL.md` and summarize the
   report structure."
   The agent should read the file from the cloned repo path.
3. (Optional, Python only) Run
   `python examples/minimal_host_news_to_decision.py` from inside
   the cloned repo. It should print a JSON document with a
   `decision` key.

## Update

```bash
cd /path/to/fund-agent
git pull
# if Python was wired, re-run pip install -e .
pip install -e .
```

## Uninstall

```bash
# Remove the symlinks / vendored docs
rm .codex/skills/fund-analysis .codex/skills/news-research \
   .codex/skills/sentiment-analysis .codex/skills/thesis-generation \
   .codex/skills/decision-support

# Remove the project-instructions snippet from your Codex project file

# Remove the cloned repo
rm -rf /path/to/fund-agent
```

## Future Codex install work

The following are explicitly **not** in v0.4.3 and are tracked as
future milestones:

- A Codex plugin cache publication under
  `~/.codex/plugins/fund-agent/`.
- A `fund-agent` entry in a Codex plugin marketplace / OMO bundle.
- A Codex-specific CLI wrapper that spawns
  `python -m fund_agent.run_skill` and proxies `SkillInput` /
  `SkillOutput` JSON.
- A first-class Codex config block in `~/.codex/config.toml` that
  references the fund-agent manifest.

When the Codex plugin spec stabilizes, the install can graduate from
"manual / light" to "first-class". Until then, the manual flow above
is the supported path.

## Separate installs for other harnesses

- **OpenCode:** see [`docs/install/opencode.md`](./opencode.md). First
  native install target.
- **Manual / Python host:** see
  [`docs/install/manual-host.md`](./manual-host.md). The canonical
  install path.
- **Claude Code, OpenClaw, Hermes:** the manual host install is
  sufficient. No native installer is shipped in v0.4.3.

## Honesty about current capability

- ✅ Codex can read the fund-agent skill docs after the manual install.
- ✅ Codex can discover skills from the manifest.
- ✅ Codex can invoke the Python runtime if Python is wired.
- ❌ There is no OMO-style installer in v0.4.3.
- ❌ There is no `~/.codex/config.toml` plugin block in v0.4.3.
- ❌ fund-agent does not become an autonomous loop inside Codex.
  Codex owns planning.
