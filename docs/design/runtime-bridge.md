# Runtime Bridge — Design

> Status: **partially implemented in v0.4.8-dev**. The thin local
> JSON-in / JSON-out CLI bridge is shipped in v0.4.8-dev
> (`scripts/run_skill.py`, `src/skillpack/run_skill.py`). The
> deeper parts of this design — subprocess-based MCP handler
> spawning, the OpenCode plugin `fund_agent_run_skill` tool, and
> the "deeper" host-side runtime-bridge surface — are still
> future and are not on the v0.4.8-dev critical path. This
> document describes the **full** design; the v0.4.8-dev
> implementation realizes a subset.
>
> The OpenCode plugin (current release) is **plugin metadata + doc
> reader only** and does not run a runtime bridge. See
> [`docs/install/opencode.md`](../install/opencode.md) for the current
> install.

## Why the deeper runtime bridge is still future

Historically, the OpenCode plugin registers three custom tools
(`fund_agent_skills`, `fund_agent_skill_doc`,
`fund_agent_runtime_hint`) and logs at startup. It deliberately does
**not** invoke the Python runtime from inside the plugin.

The v0.4.8-dev runtime bridge CLI ships a **separate, independent
surface**: a thin Python CLI that hosts can call from any process
boundary. The bridge is **not** wired into the OpenCode plugin and
the plugin still does not call Python. Hosts that want a process
boundary invoke the bridge directly; hosts that already have a
Python process continue to import the runtime classes directly.

A **deeper** runtime bridge (one that lives inside the OpenCode
plugin) would require one of:

1. A sidecar Python process spawned by the plugin and proxied through
   a tool call.
2. An embedded Python interpreter inside the plugin.
3. A persistent host service that the plugin talks to over a socket.

All three add real complexity:

- A sidecar requires the plugin to manage a child process, lifecycle,
  crashes, and re-spawns. That pulls the plugin closer to a
  "planner loop" in violation of the host-agnostic architecture
  constraints.
- An embedded interpreter (e.g. via `pythonia` or `node-python-bridge`)
  pulls in large transitive npm dependencies and platform-specific
  binaries. That violates "no node dependency bloat".
- A persistent service requires the host to install and run a daemon,
  which the user has to manage and which is not "installable" in the
  Superpowers / OMO sense.

The v0.4.8-dev milestone therefore ships the **thin CLI runtime
bridge** as an independent surface (host-invoked, not
plugin-invoked) and continues to document the **deeper** runtime
bridge here. The OpenCode plugin remains metadata + doc reader
only.

## Goals of the future runtime bridge

1. Stay **host-agnostic**. The bridge does not know whether the
   caller is OpenCode, Codex, Claude Code, OpenClaw, Hermes, or a
   custom CLI. It speaks a stable JSON in / JSON out contract.
2. Stay **deterministic**. The Python runtime is the source of
   truth; the bridge does not add LLM calls, prompt logic, or
   heuristic shortcuts.
3. Stay **optional**. Hosts that already have a Python process can
   call the runtime directly and skip the bridge. The bridge is a
   convenience for plugin-based hosts.
4. Stay **safe by default**. The bridge must refuse to call any
   provider SDK, must refuse to place trades, and must validate the
   `SkillInput` shape before invoking the skill.

## Proposed shape

### v0.4.8-dev: thin CLI bridge (SHIPPED)

The v0.4.8-dev implementation is a thin Python CLI shim that
hosts invoke as a separate process. It is **not** wired into the
OpenCode plugin and the plugin does not shell out to it.

```text
python scripts/run_skill.py \
    --skill fund_analysis \
    --input payload.json
```

Behavior:

- Read `payload.json` from disk (or read JSON from stdin via
  `--input -`) and validate it.
- Resolve the manifest runtime path
  (`src.skills_runtime.fund_analysis:FundAnalysisSkill`) via
  `src.skillpack.loader.resolve_runtime`.
- If the resolved skill needs MCP capabilities, the host may
  supply an in-memory `mcp_responses` block in the input JSON.
  The bridge wraps that block in an
  `InMemoryMCPHostAdapter`. The bridge never spawns subprocesses
  for MCP handlers (the deeper "subprocess handler" model is still
  future; see below).
- Call `skill.run(SkillInput)`.
- Print a JSON envelope on stdout with `ok`, `skill_name`,
  `status`, `artifacts`, `evidence_items`, `warnings`, `errors`,
  and `metadata`. Diagnostics go to stderr.
- Exit 0 on bridge success, exit 2 on bridge failure. The
  embedded skill `status` is reported inside the envelope.

The same CLI works for all five manifest runtime skills
(`fund_analysis`, `news_research`, `sentiment_analysis`,
`thesis_generation`, `decision_support`). The `--skill` flag
accepts either a runtime_id (e.g. `fund_analysis`) or a hyphenated
agent-facing slug (e.g. `fund-analysis`); the manifest's
`runtime` field is the canonical mapping.

The CLI is small. Most of the work is in the existing Python
runtime; the CLI is just an `argparse` shim that loads the
manifest, parses the input, calls the skill, and prints the
output.

### JSON in / JSON out contract

The input JSON is the `SkillInput` shape, with one extension for
the optional in-memory MCP responses:

```json
{
  "task_id": "host-task-1",
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "payload": { "...": "host-supplied data" },
  "required_mcp_capabilities": ["web_search"],
  "mcp_responses": {
    "web_search": { "items": [...] }
  }
}
```

Or, a convenience envelope that the bridge expands to a full
`SkillInput` (the bridge injects `task_id`, `step_id`, and
`skill_name`):

```json
{
  "payload": { "...": "host-supplied data" },
  "mcp_responses": { "...": "host-supplied canned responses" }
}
```

The output JSON is a stable envelope that always parses as
JSON:

```json
{
  "ok": true,
  "skill_name": "fund_analysis",
  "step_id": "fund-analysis-1",
  "status": "OK",
  "artifacts": { "...": "..." },
  "evidence_items": [ ... ],
  "warnings": [ ... ],
  "errors": [ ... ],
  "metadata": { "...": "..." }
}
```

Bridge-level failures look like:

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INPUT|UNKNOWN_SKILL|RUNTIME_LOAD_FAILED|SKILL_RUN_FAILED|JSON_SERIALIZATION_FAILED|MISSING_MCP_CAPABILITY",
    "message": "...",
    "details": { "...": "..." }
  }
}
```

### Determinism and provider isolation

The bridge must not introduce nondeterminism:

- The CLI does not call any LLM. All behavior is the existing
  deterministic Python runtime.
- The CLI does not perform retries. The host owns retry policy.
- The CLI does not batch or coalesce. Each invocation is one
  `SkillInput` → one `SkillOutput`.
- The CLI does not cache results. The host owns caching.

The bridge must not import provider SDKs:

- The CLI itself never imports Tavily, Finnhub, Exa, Firecrawl,
  Reddit, AkShare, OpenAI, Anthropic, LangChain, or similar
  vendor SDKs.
- The CLI never spawns subprocesses for MCP handlers.
- The CLI never shells out to OpenCode or to
  `opencode.plugin.js`.

The host owns provider access: the host injects `mcp_responses`
directly into the input JSON, or calls `run_skill.py` from a
process that already has the `MCPHostAdapter` in scope.

### Future: deeper runtime bridge

A future milestone may realize the **deeper** runtime bridge
that lives inside the OpenCode plugin. That deeper bridge would
add:

- An OpenCode plugin `fund_agent_run_skill` tool that spawns
  `scripts/run_skill.py` as a subprocess and returns the JSON
  envelope as the tool result.
- A subprocess-based `adapter_config_path` mode that lets the
  host declare MCP capability handler commands
  (e.g. `["python", "/path/to/host_web_search.py"]`) and lets
  the bridge spawn those handlers on demand.
- A `PYTHON_RUNTIME_UNAVAILABLE` plugin error when `python` is
  missing on PATH.

These are **not** in v0.4.8-dev. The v0.4.8-dev thin CLI
bridge is independent of the OpenCode plugin surface.

## What we are NOT doing in the runtime bridge

- We are not making the OpenCode plugin a planner / agent loop.
- We are not bundling provider SDKs in the plugin.
- We are not adding npm dependencies heavier than `@opencode-ai/plugin`
  for the plugin itself.
- We are not adding a daemon / service.
- We are not changing the Python runtime. The bridge is a thin CLI
  shim over the existing `src/skills_runtime/` classes.
- The v0.4.8-dev thin CLI bridge does **not** wire into the
  OpenCode plugin. The plugin still does not call Python.

## Acceptance criteria for the runtime bridge (when implemented)

1. `python scripts/run_skill.py --help` works.
2. `python scripts/run_skill.py --skill fund_analysis --input <good>`
   exits 0 and prints the bridge JSON envelope.
3. `python scripts/run_skill.py --skill fund_analysis --input <bad>`
   exits non-zero with a structured error code.
4. The CLI never imports a provider SDK.
5. The CLI never calls `requests`, `urllib`, `httpx`, `openai`,
   `anthropic`, `langchain`, `tavily`, `finnhub`, `exa`,
   `firecrawl`, or `praw` directly. Network access is mediated
   only through the host-supplied `mcp_responses` block.
6. The deeper OpenCode plugin `fund_agent_run_skill` tool is
   **future** and is not in v0.4.8-dev.
7. The OpenCode plugin still works in log-only mode when
   `@opencode-ai/plugin` peer dep is not resolved.

## Tracking

The thin CLI bridge is shipped in v0.4.8-dev. The deeper
runtime-bridge surface (subprocess handler spawning, OpenCode
plugin tool wrapper) is still future and is the candidate spec
for `v0.5.x-runtime-bridge`. If you need to wire the Python
runtime into OpenCode today, use the manual host integration in
[`docs/install/manual-host.md`](../install/manual-host.md) — it
is the supported path. The runtime bridge CLI is documented in
[`docs/install/runtime-bridge-cli.md`](../install/runtime-bridge-cli.md).
