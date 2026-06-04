# Runtime Bridge CLI

> Status: **shipped in v0.4.7-dev**. The runtime bridge CLI is a
> thin local JSON-in / JSON-out Python shim over the existing
> manifest runtime skills. It is independent of the OpenCode
> plugin; the plugin still does not call Python.

The runtime bridge is for **host integration and testing**. It lets
external hosts call `fund-agent` runtime skills without importing
internal Python modules directly, by spawning a Python subprocess
and reading JSON envelopes from stdout.

## Install (source checkout only)

The runtime bridge is **git-clone-only**. The npm
package (Mode A: plugin + skill docs) does **not** ship
`scripts/run_skill.py`, `src/skillpack/run_skill.py`, or the
runtime bridge examples. To use the bridge, hosts must work from a
Python source checkout:

```bash
git clone --branch v0.4.8 https://github.com/EXASHXE/fund-agent.git
cd fund-agent
pip install -e .        # editable install into your Python environment
```

The bridge then lives at `scripts/run_skill.py` (executable
wrapper) and `src/skillpack/run_skill.py` (importable module).
Examples live at `examples/runtime_bridge_*_input.json` and
`examples/minimal_runtime_bridge_fund_analysis.py`.

The bridge requires **no** npm dependency, **no** OpenCode install,
and **no** provider SDK. A working `python` (3.10+) interpreter is
the only prerequisite.

## What it is and is not

The runtime bridge:

- Is a **thin CLI shim** over `src/skills_runtime/`.
- Reads a JSON input, calls one manifest runtime skill, and prints
  a JSON envelope to stdout.
- Resolves runtime classes from the manifest
  (`skillpack/fund-agent.skillpack.yaml`) via
  `src.skillpack.loader.resolve_runtime`.
- Accepts in-memory MCP canned responses via a `mcp_responses`
  block in the input JSON; it never spawns subprocesses for MCP
  handlers.
- Works for all five manifest runtime skills
  (`fund_analysis`, `news_research`, `sentiment_analysis`,
  `thesis_generation`, `decision_support`).

The runtime bridge is **not**:

- An agent loop, planner, scheduler, or daemon.
- A server, broker, or persistent service.
- A provider integration. It does not import Tavily, Finnhub, Exa,
  Firecrawl, Reddit, AkShare, OpenAI, Anthropic, or LangChain.
- A network caller. It does not call `requests`, `httpx`, or
  `urllib.request`.
- A subprocess caller. It does not shell out to OpenCode, does not
  call `opencode.plugin.js`, and does not import
  `@opencode-ai/plugin`.
- Wired into the OpenCode plugin. The plugin still does not call
  Python.

The deeper runtime-bridge design (subprocess handlers, OpenCode
plugin `fund_agent_run_skill` tool) is still future. See
[`docs/design/runtime-bridge.md`](../design/runtime-bridge.md) for
the full design.

## When to use it

Use the runtime bridge CLI when:

- You are a host (OpenCode, Codex, Claude Code, OpenClaw, Hermes,
  custom Python, etc.) and want a process boundary between your
  code and the `fund-agent` runtime skills.
- You want to test the runtime skills without writing a Python
  import boilerplate.
- You want a JSON-only envelope you can log, diff, or pipe.

Do not use the runtime bridge CLI when:

- You already have a Python process in scope. Import the runtime
  classes directly via
  `src.skillpack.loader.resolve_runtime` and call
  `skill.run(skill_input)` yourself.
- You need a planner / agent loop. The bridge does not orchestrate
  multiple skills; the host owns orchestration.

## Quick start

### 1. List the available skills

```bash
python scripts/run_skill.py --list-skills --pretty
```

Output (truncated):

```json
{
  "ok": true,
  "manifest_version": "0.4.8",
  "schema_version": "skillpack.v1",
  "skills": [
    {
      "runtime_id": "fund_analysis",
      "doc_slug": "fund-analysis",
      "runtime": "src.skills_runtime.fund_analysis:FundAnalysisSkill",
      "requires_mcp": [],
      "produces": ["HardEvidence"],
      "forbidden": []
    },
    ...
  ]
}
```

### 2. Run a skill

```bash
python scripts/run_skill.py \
    --skill fund_analysis \
    --input examples/runtime_bridge_fund_analysis_input.json \
    --pretty
```

The bridge writes the JSON envelope to stdout and exits 0 on
success.

### 2b. List host-owned data capabilities

```bash
python scripts/run_skill.py --list-capabilities --pretty
```

### 2c. Describe a single capability

```bash
python scripts/run_skill.py --describe-capability fund_nav_history --pretty
```

### 3. Run from stdin

```bash
echo '{"payload": {"portfolio": null}}' \
  | python scripts/run_skill.py --skill fund_analysis --input -
```

### 4. Write the output to a file

```bash
python scripts/run_skill.py \
    --skill fund_analysis \
    --input examples/runtime_bridge_fund_analysis_input.json \
    --output /tmp/fund_analysis_output.json
```

### 5. Personal report quality example

```bash
python scripts/run_skill.py \
    --skill fund_analysis \
    --input examples/runtime_bridge_personal_report_quality_input.json \
    --pretty
```

This example includes all optional data (benchmarks, peer group, factor
exposures, fee schedules, redemption rules, manager profiles). The output
includes `data_completeness` (grade A-D), `analysis_coverage` (per-section
availability), `report_limitations` (user-facing caveats),
`report_sections` (deterministic host-displayable sections), and
`report_quality_gate` (whether the report is publishable as a professional
report). The CLI still only runs host-invoked JSON skill calls; it does not
fetch data, call providers, or generate formal decisions outside
`decision_support`.

## CLI reference

```text
python scripts/run_skill.py [options]

  --skill RUNTIME_ID_OR_SLUG
      Required unless --list-skills, --list-capabilities, or
      --describe-capability is passed. Accepts either a manifest
      runtime_id (fund_analysis, decision_support, ...) or a
      hyphenated agent-facing slug (fund-analysis, ...).

  --input PATH
      Path to a JSON input file. Use '-' to read JSON from stdin.
      Either a full SkillInput envelope or a convenience
      {"payload": {...}} shape is accepted.

  --output PATH
      Optional path to write the JSON output to. Defaults to stdout.

  --manifest PATH
      Path to the skillpack manifest YAML. Defaults to
      skillpack/fund-agent.skillpack.yaml.

  --list-skills
      List the manifest runtime skills and exit. JSON envelope on stdout.

  --list-capabilities
      List all host-owned data capabilities, MCP capabilities, and
      local capabilities from skillpack/capabilities.yaml. JSON only.

  --describe-capability NAME
      Describe a single capability by name (e.g. fund_nav_history).
      JSON envelope on stdout. Returns UNKNOWN_CAPABILITY for unknown names.

  --pretty
      Pretty-print the JSON output (indent=2). Default is compact.
```

## JSON contracts

### Input

The bridge accepts two envelope shapes.

**Full `SkillInput` envelope:**

```json
{
  "task_id": "host-task-1",
  "step_id": "fund-analysis-1",
  "skill_name": "fund_analysis",
  "payload": { "...": "host-supplied data" },
  "kg_context": {},
  "required_mcp_capabilities": [],
  "evidence_context": [],
  "metadata": {},
  "mcp_responses": {
    "web_search": { "items": [...] }
  }
}
```

**Convenience `{"payload": {...}}` envelope:**

```json
{
  "payload": { "...": "host-supplied data" },
  "mcp_responses": { "...": "host-supplied canned responses" }
}
```

When the convenience envelope is used, the bridge injects
`task_id` (`runtime-bridge-task`), `step_id` (`<skill>-1`), and
`skill_name` (from `--skill`).

### Output (success)

```json
{
  "ok": true,
  "skill_name": "fund_analysis",
  "step_id": "fund-analysis-1",
  "status": "OK",
  "artifacts": { "...": "..." },
  "evidence_items": [],
  "warnings": [],
  "errors": [],
  "used_mcp_capabilities": [],
  "metadata": {
    "manifest_path": "skillpack/fund-agent.skillpack.yaml",
    "runtime_path": "src.skills_runtime.fund_analysis:FundAnalysisSkill",
    "missing_mcp_capabilities": []
  }
}
```

The `status` field is the embedded skill's status and may be
`OK`, `PARTIAL`, or `FAILED`.

### Output (bridge-level failure)

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INPUT|UNKNOWN_SKILL|RUNTIME_LOAD_FAILED|SKILL_RUN_FAILED|JSON_SERIALIZATION_FAILED",
    "message": "...",
    "details": { "...": "..." }
  }
}
```

Bridge-level error codes:

| Code | When |
|---|---|
| `INVALID_INPUT` | Input is not valid JSON, is not a JSON object, or has a wrong `payload` shape. |
| `UNKNOWN_SKILL` | `--skill` is not a manifest runtime_id or known slug. |
| `RUNTIME_LOAD_FAILED` | Manifest could not be loaded, the runtime path could not be imported, or the skill class could not be instantiated. |
| `SKILL_RUN_FAILED` | The skill raised an exception while running. |
| `JSON_SERIALIZATION_FAILED` | The output envelope could not be serialized to JSON. |

### Exit codes

- `0` — the bridge itself succeeded. The embedded skill's `status`
  is reported inside the envelope.
- `2` — the bridge itself failed (one of the error codes above).

## MCP boundary

The runtime bridge is **host-agnostic for MCP**: it does not call
any provider SDK and does not make network requests. The host owns
MCP providers.

For skills that require MCP capabilities (e.g. `news_research`
requires `web_search` and `financial_news`):

- The host can supply a `mcp_responses` block in the input JSON.
  The bridge wraps that block in an
  `InMemoryMCPHostAdapter` and passes it to the skill.
- If no `mcp_responses` is supplied for a required capability, the
  bridge reports the skill output and downgrades `ok` to `false`
  with a `MISSING_MCP_CAPABILITY` error. The host is expected to
  inject MCP providers or run the skill with a real adapter in
  scope.

The bridge **never** spawns subprocesses for MCP handlers, **never**
imports provider SDKs, and **never** makes HTTP calls. The deeper
subprocess-handler design is documented in
[`docs/design/runtime-bridge.md`](../design/runtime-bridge.md) and
is still future.

## OpenCode plugin relationship

The OpenCode plugin (`opencode.plugin.js`) and the runtime bridge
CLI are **independent surfaces**:

- The plugin still does not call Python. It does not import
  `@opencode-ai/plugin`-triggered subprocesses that invoke
  `scripts/run_skill.py`. It is metadata + doc reader only.
- The bridge does not reference `opencode.plugin.js`, does not
  import `@opencode-ai/plugin`, and does not shell out to OpenCode.

Hosts that want OpenCode to use the bridge today can:

- Run the bridge as a sidecar process from a custom tool / agent
  action.
- Spawn `scripts/run_skill.py` from any host-owned code that is
  reachable from the OpenCode session.

Hosts that want the bridge wired into the OpenCode plugin itself
must wait for the deeper runtime-bridge milestone
(`v0.5.x-runtime-bridge`), which is still design-only.

## Examples

- `examples/runtime_bridge_fund_analysis_input.json` — minimal
  convenience input for `fund_analysis` (direct portfolio mode).
- `examples/runtime_bridge_decision_support_input.json` — minimal
  convenience input for `decision_support` with a one-evidence
  graph fixture.
- `examples/runtime_bridge_ledger_snapshot_input.json` — derived
  portfolio mode: transactions + current_nav only, no host portfolio.
- `examples/runtime_bridge_research_query_plan_input.json` —
  portfolio analysis with `research_planning: true`; produces
  a `research_query_plan` artifact.
- `examples/minimal_runtime_bridge_fund_analysis.py` — minimal
  host demo that spawns the bridge CLI from Python and parses
  the JSON envelope.

### Derived portfolio mode

When a host provides `transactions`, `current_nav`, and `as_of_date`
without `portfolio.positions`, `fund_analysis` deterministically
derives a position snapshot from the transaction ledger:

```bash
python scripts/run_skill.py \
    --skill fund_analysis \
    --input examples/runtime_bridge_ledger_snapshot_input.json \
    --pretty
```

The output includes:
- `derived_portfolio_snapshot` — positions with weighted-average cost basis
- `ledger_cashflow_summary` — cashflows, dividends, fees
- `portfolio_summary` — total value, weights, concentration

Derived snapshot accuracy depends on transaction ledger completeness
and current NAV values. The host owns ledger data and NAV sourcing;
`fund-agent` does not fetch either.

## Testing the bridge

```bash
# Default test suite picks up tests/runtime_bridge via testpaths.
PYTHONPATH=. pytest tests/runtime_bridge -q

# Run the documented examples end-to-end.
python scripts/run_skill.py --list-skills --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --pretty
python scripts/run_skill.py --skill decision_support --input examples/runtime_bridge_decision_support_input.json --pretty
```
