# Generic Subprocess Host Cookbook

This is the canonical technical integration path for any host that can run a
local subprocess. The host keeps orchestration and data fetching outside
`fund-agent`, then invokes the runtime bridge with JSON input.
Host owns data fetching, provider SDKs, credentials, MCP providers, retries,
memory, planning, and final UX.

## Prerequisites

- Source checkout of this repository.
- Python 3.11 or newer.
- Editable install:

```bash
pip install -e .
```

`fund-agent` does not need provider API keys. The host should not pass
credentials into `fund-agent` unless it has a clear local policy.

## Discovery

Read the manifest:

```bash
python scripts/run_skill.py --list-skills --pretty
```

The manifest source is `skillpack/fund-agent.skillpack.yaml`. Runtime IDs use
underscores, such as `fund_analysis`; agent-facing Markdown slugs use hyphens,
such as `fund-analysis`.

## Input Inspection

```bash
python scripts/run_skill.py --skill fund_analysis --explain-input --pretty
```

This reads `skillpack/input-contracts.yaml` and reports accepted envelope
shapes, minimum modes, recommended fields, optional fields, and host-owned
capability mappings.

## Input Validation

```bash
python scripts/run_skill.py \
  --skill fund_analysis \
  --input examples/runtime_bridge_fund_analysis_input.json \
  --validate-input \
  --pretty
```

Branch on `validation_result.valid` and `validation_result.severity`.
Validation is structural and host-assistive; it is not a guarantee of
investment correctness or data freshness.

For fake/sample scenario inputs that validate through the same bridge path, see
[`examples/scenarios/README.md`](../../examples/scenarios/README.md).
For regression checks around externally visible `fund_analysis` output, see
[`tests/golden/README.md`](../../tests/golden/README.md).
For decision_support formal decision contracts and fixtures, see
[`docs/contracts/decision-support-contract.v1.md`](../../docs/contracts/decision-support-contract.v1.md)
and
[`examples/decision_support/README.md`](../../examples/decision_support/README.md).

## Normal JSON Execution

```bash
python scripts/run_skill.py \
  --skill fund_analysis \
  --input examples/runtime_bridge_fund_analysis_input.json \
  --pretty
```

Default success output is JSON. Exit code `0` means the bridge command
succeeded. The embedded skill may still report `status: "PARTIAL"` or warnings.

## Markdown Report Emission

```bash
python scripts/run_skill.py \
  --skill fund_analysis \
  --input examples/runtime_bridge_personal_report_quality_input.json \
  --emit-report markdown \
  --output report.md
```

`--emit-report markdown` is explicit opt-in. Success output is Markdown for
`fund_analysis` only. Bridge errors remain JSON envelopes.

## Output Schema Inspection

```bash
python scripts/run_skill.py --skill fund_analysis --output-schema --pretty
```

This reads `skillpack/artifact-contracts.yaml` for known artifact keys and
forbidden formal decision artifacts.

## Host Responsibilities

- Build payloads from the host's own portfolio, NAV, holdings, ledger,
  benchmark, peer, fee, manager, market, macro, and calendar data.
- Branch on `validation_result.valid` and `validation_result.severity`.
- Branch on `SkillOutput.status`.
- Surface `warnings` and `report_limitations`.
- Never treat `suggested_rebalance_plan` as a formal order.
- Compile evidence and call `decision_support` only when a formal decision is
  needed.
- Log input/output envelopes for audit when appropriate.

## Error Handling

- Default success output is JSON.
- `--emit-report markdown` success output is Markdown.
- Errors remain JSON envelopes.
- Exit code `0` means the bridge command succeeded, not that an investment
  decision is correct or publishable.
- Exit code `2` means a bridge-level failure.

## Minimal Orchestration Example

```python
import json
import subprocess
import sys

BASE = [sys.executable, "scripts/run_skill.py", "--skill", "fund_analysis"]
INPUT = "examples/runtime_bridge_fund_analysis_input.json"

validate = subprocess.run(
    [*BASE, "--input", INPUT, "--validate-input", "--pretty"],
    check=True,
    capture_output=True,
    text=True,
)
validation = json.loads(validate.stdout)["validation_result"]
if not validation["valid"]:
    raise SystemExit(
        "missing or invalid input: "
        + json.dumps(validation["errors"], ensure_ascii=False)
    )

run = subprocess.run(
    [*BASE, "--input", INPUT, "--pretty"],
    check=True,
    capture_output=True,
    text=True,
)
output = json.loads(run.stdout)
if output["status"] in {"PARTIAL", "FAILED"}:
    print(output.get("warnings", []))

subprocess.run(
    [
        *BASE,
        "--input",
        "examples/runtime_bridge_personal_report_quality_input.json",
        "--emit-report",
        "markdown",
        "--output",
        "report.md",
    ],
    check=True,
)
```

For formal actions, compile `evidence_items` and invoke `decision_support`.
Formal decisions require `decision_support`.
`fund_analysis` itself does not produce formal `Decision` or `ExecutionLedger`.
