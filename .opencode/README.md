# fund-agent — OpenCode Integration

Private mutual fund portfolio reconstruction and KG/news report pipeline.

## Skills

| Skill | Description |
|---|---|
| `fund-agent-e2e` | Run the full E2E pipeline via `bin/fund-agent-e2e` |
| `fund-agent-privacy-audit` | Check for private data leaks via `bin/fund-agent-privacy-check` |
| `fund-agent-setup-private-data` | Set up and verify private data files |

## Agents

| Agent | Description |
|---|---|
| `fund-report-e2e` | Orchestrate E2E pipeline run |
| `fund-data-auditor` | Audit privacy compliance |

## Plugin

- `plugins/fund-agent-privacy-protection.ts` — warns when agent reads protected paths

## Install

See [INSTALL.md](./INSTALL.md) for detailed install instructions.

## Safety

- Private data (private_data/, local_data/, *.private.*) is never committed
- API keys are set via environment variables only
- The E2E runner never prints private contents to chat
