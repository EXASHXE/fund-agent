# Multi-Harness Distribution

`fund-agent` ships as a **Superpowers / oh-my-openagent style** multi-harness
distribution: one repository with harness-specific plugin wrappers that all
delegate to shared deterministic runners.

## Architecture

```
fund-agent/
  bin/fund-agent-e2e              # shared E2E pipeline runner
  bin/fund-agent-privacy-check    # shared privacy audit runner
  .claude-plugin/                 # Claude Code plugin
  .codex-plugin/                  # Codex plugin manifest
  .agents/skills/                 # Codex Agent Skills
  .opencode/                      # OpenCode skills/agents/plugins
  install/                        # installer/doctor/uninstall scripts
```

All harness skills delegate to `bin/fund-agent-e2e` and
`bin/fund-agent-privacy-check`. No business logic is duplicated.

## Harnesses

| Harness | Plugin root | Skills | Install |
|---|---|---|---|
| Claude Code | `.claude-plugin/` | `skills/e2e-report/`, `audit-privacy/`, `setup-private-data/` | `claude --plugin-dir <repo>` |
| Codex | `.codex-plugin/` + `.agents/skills/` | `fund-agent-e2e/`, `fund-agent-privacy-audit/`, `fund-agent-setup-private-data/` | copy/symlink to `~/.agents/skills/` |
| OpenCode | `.opencode/` | `fund-agent-e2e/`, `fund-agent-privacy-audit/`, `fund-agent-setup-private-data/` | copy/symlink to `~/.config/opencode/` |

## Installer

```bash
# Install all harnesses (symlink mode)
python install/fund-agent-agent-install.py --target all --mode symlink

# Install specific harness (copy mode)
python install/fund-agent-agent-install.py --target claude-code --mode copy

# Doctor check
python install/fund-agent-agent-doctor.py --target all

# Uninstall (dry-run first)
python install/fund-agent-agent-uninstall.py --target all --dry-run
python install/fund-agent-agent-uninstall.py --target all
```

## Shared Runners

### bin/fund-agent-e2e

```bash
bash bin/fund-agent-e2e --as-of 2026-06-17
bash bin/fund-agent-e2e --dry-run
bash bin/fund-agent-e2e --skip-news --skip-akshare
bash bin/fund-agent-e2e --output-report /path/to/report.md
bash bin/fund-agent-e2e --run-id my-run-001
```

### bin/fund-agent-privacy-check

```bash
bash bin/fund-agent-privacy-check
```

Exits 0 if no privacy violations, 1 otherwise.

## Limitations

- Claude Code marketplace: not published
- Codex marketplace: not published
- OpenCode npm package: not published
- Provider/news availability depends on environment variables
- Private data must remain local (never committed)
- No broker execution

## Invocation Examples

- **Claude Code:** `/fund-agent:e2e-report --as-of YYYY-MM-DD`
- **Codex:** `$fund-agent-e2e`
- **OpenCode:** `fund-agent-e2e` or `@fund-report-e2e`
