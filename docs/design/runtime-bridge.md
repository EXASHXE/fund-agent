# Runtime Bridge — Design (Future)

> Status: **design only**. Not implemented in v0.4.3. This document
> describes the shape of a future optional runtime bridge between an
> OpenCode / Codex plugin and the deterministic Python runtime in
> `src/skills_runtime/`.
>
> The v0.4.3 OpenCode install is **plugin metadata + doc reader only**
> and does not run a runtime bridge. See
> [`docs/install/opencode.md`](../install/opencode.md) for the current
> install.

## Why a runtime bridge is a future concern, not a v0.4.3 one

The OpenCode plugin in v0.4.3 registers three custom tools
(`fund_agent_skills`, `fund_agent_skill_doc`,
`fund_agent_runtime_hint`) and logs at startup. It deliberately does
**not** invoke the Python runtime from inside the plugin.

A runtime bridge would require one of:

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

The v0.4.3 milestone therefore ships the **metadata + doc reader**
plugin and documents a future, opt-in runtime bridge here.

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

### Python CLI wrapper

```text
python -m fund_agent.run_skill \
    --skill fund_analysis \
    --input payload.json
```

Behavior:

- Read `payload.json` from disk and validate it against
  `src.schemas.skill.SkillInput`.
- Resolve the manifest runtime path
  (`src.skills_runtime.fund_analysis:FundAnalysisSkill`).
- If the resolved skill needs MCP capabilities, read a host-supplied
  `MCPHostAdapter` from `--adapter-config` (path to a JSON file
  describing capability names, schemas, and handler script paths).
- Call `skill.run(SkillInput)`.
- Print a JSON document to stdout with `status`, `evidence_items`,
  `artifacts`, `warnings`, and `errors`.
- Exit 0 on success, exit 2 on validation error, exit 3 on
  `MCP_CALL_FAILED`, exit 1 on other failures.

The same CLI works for all five manifest runtime skills
(`fund_analysis`, `news_research`, `sentiment_analysis`,
`thesis_generation`, `decision_support`). The `--skill` flag selects
the runtime class; the manifest's `runtime` field is the canonical
mapping.

The CLI is small. Most of the work is in the existing Python
runtime; the CLI is just an `argparse` shim that loads the manifest,
parses the input, calls the skill, and prints the output.

### JSON in / JSON out contract

The input JSON is the `SkillInput` shape, with one extension for the
adapter config:

```json
{
  "task_id": "host-task-1",
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "payload": { "...": "host-supplied data" },
  "required_mcp_capabilities": ["web_search"],
  "adapter_config_path": "/path/to/mcp_handlers.json"
}
```

The output JSON is the `SkillOutput` shape, serialized with
`to_dict()`:

```json
{
  "status": "OK",
  "evidence_items": [ ... ],
  "artifacts": { "...": "..." },
  "warnings": [ ... ],
  "errors": [ ... ]
}
```

The OpenCode / Codex plugin wraps this CLI in a custom tool:

```javascript
// Pseudocode — not part of v0.4.3
fund_agent_run_skill: tool({
  description: "Run a fund-agent Python runtime skill and return its output.",
  args: {
    skill_name: stringSchema(),
    payload_json: stringSchema(),
  },
  async execute(args, ctx) {
    // 1. Write payload_json to a temp file.
    // 2. Spawn: python -m fund_agent.run_skill --skill <skill_name> --input <temp>
    // 3. Capture stdout, return as the tool result.
  },
})
```

This keeps the bridge opt-in: a host that does not have Python
available simply does not call this tool. The host that does have
Python uses the same pattern.

### Codex plugin wrapper

Codex has no stable plugin spec yet, so the Codex path is
"shell out to the same CLI". A future Codex-specific plugin can
wrap `python -m fund_agent.run_skill` once the Codex plugin spec
stabilizes.

### Keeping deterministic outputs

The bridge must not introduce nondeterminism:

- The CLI does not call any LLM. All behavior is the existing
  deterministic Python runtime.
- The CLI does not perform retries. The host owns retry policy.
- The CLI does not batch or coalesce. Each invocation is one
  `SkillInput` → one `SkillOutput`.
- The CLI does not cache results. The host owns caching.

### Keeping provider access host-owned

The CLI accepts an `adapter_config_path` for MCP handlers. The CLI
itself never imports a provider SDK; it only loads a JSON file that
describes handler scripts. The host runs the actual providers.

For example:

```json
{
  "capabilities": [
    {
      "name": "web_search",
      "handler_command": ["python", "/path/to/host_web_search.py"]
    },
    {
      "name": "financial_news",
      "handler_command": ["python", "/path/to/host_news.py"]
    }
  ]
}
```

The bridge spawns these as subprocesses only on demand, passes the
MCP request as JSON on stdin, and reads the response as JSON on
stdout. This is the same pattern `examples/minimal_host_*.py`
already uses, just with a CLI boundary.

## OpenCode plugin tool wrapper (future)

When the runtime bridge ships, the OpenCode plugin will gain a
fourth tool:

```text
fund_agent_run_skill
  - args: { skill_name: string, payload_json: string }
  - description: |
      Run a fund-agent Python runtime skill via the CLI bridge.
      Returns the SkillOutput JSON. Requires a `python` interpreter
      on PATH and an adapter_config for skills that need MCP data.
  - behavior:
      - write payload_json to a temp file
      - spawn `python -m fund_agent.run_skill --skill <skill_name> --input <temp>`
      - read stdout, return as the tool result
```

The plugin will check for `python` on PATH at startup and log a
warning if it is missing. The tool will return a structured error
(`PYTHON_RUNTIME_UNAVAILABLE`) when `python` is missing rather than
silently failing.

## What we are NOT doing in the runtime bridge

- We are not making the OpenCode plugin a planner / agent loop.
- We are not bundling provider SDKs in the plugin.
- We are not adding npm dependencies heavier than `@opencode-ai/plugin`
  for the plugin itself.
- We are not adding a daemon / service.
- We are not changing the Python runtime. The bridge is a thin CLI
  shim over the existing `src/skills_runtime/` classes.

## Acceptance criteria for the runtime bridge (when implemented)

1. `python -m fund_agent.run_skill --help` works.
2. `python -m fund_agent.run_skill --skill fund_analysis --input <good>`
   exits 0 and prints a `SkillOutput` JSON.
3. `python -m fund_agent.run_skill --skill fund_analysis --input <bad>`
   exits non-zero with a structured error code.
4. The CLI never imports a provider SDK.
5. The CLI never calls `requests`, `urllib`, `httpx`, `openai`,
   `anthropic`, `langchain`, `tavily`, `finnhub`, `exa`,
   `firecrawl`, or `praw` directly. Network access is mediated
   only through the host-supplied `adapter_config_path`.
6. The OpenCode plugin's `fund_agent_run_skill` tool returns a
   structured error when `python` is missing on PATH.
7. The OpenCode plugin still works in log-only mode when
   `@opencode-ai/plugin` peer dep is not resolved.

## Tracking

This design is the candidate spec for a future milestone
(likely `v0.5.x-runtime-bridge`). It is not on the v0.4.3
critical path. If you need to wire the Python runtime into OpenCode
today, use the manual host integration in
[`docs/install/manual-host.md`](../install/manual-host.md) — it
is the supported path.
