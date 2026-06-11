# OpenCode troubleshooting

This document covers common issues when installing `fund-agent` for
OpenCode, and recommends the verified path for v1.1.0. It does not
change runtime behavior, skill semantics, or plugin behavior.

## Symptom: fund_agent_skills returns TOOL_UNAVAILABLE

`fund_agent_skills` belongs to the OpenCode **plugin custom tool** path
(Mode A). If calling it returns `TOOL_UNAVAILABLE`, custom plugin tools
are not registered in the current OpenCode session.

Possible causes:

- OpenCode does not expose custom plugin tools to the model.
- `@opencode-ai/plugin` helper is unavailable.
- The plugin is effectively in log-only mode.
- The plugin file is visible as source but not registered as a tool.

This is **not release-blocking** if native Agent Skills (Mode B) work.

Mode A custom plugin tools are **optional and environment-dependent**.
In the verified test environment, `fund_agent_skills` returned
`TOOL_UNAVAILABLE`. This means plugin custom tools were not registered
in the current OpenCode session. This does **not** mean fund-agent
skills are invalid.

### Checks

1. Verify `.opencode/plugins/fund-agent.js` exists.

   ```bash
   ls -la .opencode/plugins/fund-agent.js
   ```

2. Verify it points to or copies `opencode.plugin.js`.

   ```bash
   head -5 .opencode/plugins/fund-agent.js
   ```

3. Restart OpenCode.

4. Check startup logs for `fund-agent plugin loaded` if available.

5. If the tool remains unavailable, stop debugging Mode A and use
   **Mode B native Agent Skills** instead.

## Recommended verified path: native Agent Skills

Native Agent Skills are the **recommended OpenCode path for v1.1.0**.

Install the `SKILL.md` directories into the target project:

```bash
cd /path/to/fund-agent
python scripts/install_opencode_skills.py --target ../demo-project/.opencode/skills
```

Then launch OpenCode from the target project directory:

```bash
cd ../demo-project
opencode
```

Expected installed skills:

- `fund-analysis` — primary / default skill
- `decision-support` — supporting; the only skill allowed to emit
  formal `Decision` / `ExecutionLedger`
- `news-research` — supporting skill
- `sentiment-analysis` — supporting skill
- `thesis-generation` — supporting skill

`fund-analysis` is the primary/default skill. Start here for ordinary
fund / portfolio report requests. `decision-support` is supporting and
is the only skill allowed to emit formal `Decision` / `ExecutionLedger`.
`news-research`, `sentiment-analysis`, and `thesis-generation` are
supporting skills loaded only when their description matches the subtask.

## Symptom: installed skills are not listed

If skills are installed into `demo-project/.opencode/skills` but
OpenCode is launched from `fund-agent/`, OpenCode may not see them.
Project-local `.opencode/skills` are discovered relative to the current
OpenCode project directory. Start OpenCode from the target project
directory.

```bash
cd /path/to/fund-agent
python scripts/install_opencode_skills.py --target ../demo-project/.opencode/skills
cd ../demo-project
opencode
```

Verification:

```bash
find .opencode/skills -maxdepth 2 -type f | sort
cat .opencode/skills/.fund-agent-generated.json
```

If project-local skills are still not detected, install globally:

```bash
python scripts/install_opencode_skills.py --target ~/.config/opencode/skills
```

## Windows / Git Bash path pitfalls

Avoid passing `/drives/c/...` to Windows Python. Windows Python may
interpret it as `C:\drives\c\...`, which is wrong. Prefer relative
paths:

```bash
python scripts/install_opencode_skills.py --target ../demo-project/.opencode/skills
```

Or `C:/Users/...` paths:

```bash
python scripts/install_opencode_skills.py --target C:/Users/<user>/workspace/tmp/fund-agent-install-test/demo-project/.opencode/skills
```

On Windows/Git Bash, symlinks may be confusing. Copying the plugin can
be more reliable:

```bash
cp ../fund-agent/opencode.plugin.js .opencode/plugins/fund-agent.js
```

## Verification prompts

### Native skill discovery prompt

```
List installed native OpenCode skills.
Check whether these skills are installed:
- fund-analysis
- decision-support
- news-research
- sentiment-analysis
- thesis-generation

Use the installed SKILL.md files.
Do not use fund_agent_skills.
Do not inspect fund-agent.js.
```

### fund-analysis semantics prompt

```
Load the fund-analysis skill.
A user asks: "分析下我的基金组合，给出报告。"
Which fund-agent skill should be used first?
Should decision-support be called immediately?
What data should the host provide?
Do not run Python.
Do not make a formal investment decision.
```

### decision-support semantics prompt

```
Load the decision-support skill.
A user asks: "我想今天卖出这只基金，给我正式操作决策。"
Which skill is allowed to emit formal Decision / ExecutionLedger?
What evidence or artifacts are required before calling it?
Should the agent execute broker orders?
```

## Runtime bridge verification

Runtime bridge verification is **separate** from OpenCode skill
discovery. Native Agent Skills verify discovery/instruction loading.
Runtime bridge verifies deterministic Python execution.

```bash
fund-agent-doctor --pretty
python scripts/smoke_host_install.py
python scripts/run_skill.py --skill fund_analysis --explain-input --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --pretty
python scripts/run_skill.py --skill decision_support --explain-input --pretty
```

Expected:

- `fund_analysis` emits deterministic artifacts and `evidence_items`.
- `fund_analysis` does **not** emit `Decision` / `ExecutionLedger`.
- `decision_support` is the only formal decision runtime.
- No broker/order execution occurs.
