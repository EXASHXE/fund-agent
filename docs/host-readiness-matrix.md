# Host Readiness Matrix

Concise factual reference for external agent hosts (OpenCode, Claude Code,
Codex, Hermes, OpenClaw, custom subprocess host). Defines what fund-agent
provides and what the host must own.

## Execution Modes

| Host Mode | Python Runtime | Data Fetching | MCP Providers | Decision Support |
|---|---|---|---|---|
| Source checkout + runtime bridge | Yes (local) | Host-owned only | Host-injected adapter | Yes |
| OpenCode plugin | No (metadata/doc-reader only) | Host-owned only | Host-owned | Host-driven via Python bridge |
| Generic subprocess host | Yes (local CLI) | Host-owned only | Host-injected adapter | Yes |
| Codex / Claude / Hermes / OpenClaw | Host-driven via bridge | Host-owned only | Host-owned | Host-driven via Python bridge |

## Skill Coverage

| Skill | Deterministic Runtime | Requires MCP | Produces | Formal Decision? |
|---|---|---|---|---|
| `fund_analysis` | Yes | No | `HardEvidence`, report sections, artifacts | No |
| `news_research` | Yes | Yes (web_search, financial_news) | `SoftEvidence` | No |
| `sentiment_analysis` | Yes | Yes (social_sentiment) | `SoftEvidence` | No |
| `thesis_generation` | Yes | No | `ThesisDraft` (artifact-only) | No |
| `decision_support` | Yes | No | `Decision`, `ExecutionLedger` | **Yes (only)** |

## Host Responsibilities

| Concern | Owned By |
|---|---|
| Data fetching (NAV, holdings, news, sentiment, market, macro, calendar) | Host |
| Provider SDKs (Tavily, Finnhub, Exa, Firecrawl, Reddit, AkShare) | Host |
| MCP capability implementation | Host |
| Network access, credentials, retries | Host |
| Planning, orchestration, memory | Host |
| Broker/order execution | Host (not in fund-agent) |
| Final UX, portfolio display, order confirmation | Host |
| Python 3.11+ runtime (for deterministic skills) | Host |
| Skill selection and ordering | Host |

## Boundary Rules

- **OpenCode plugin** is metadata + doc-reader only. It does **not** invoke
  Python or run the runtime bridge.
- **Runtime bridge** requires source checkout and manual host invocation.
  There is no bundled HTTP API, daemon, or server.
- **fund-agent** does not include provider SDKs or network-fetching code.
- **No broker/order execution** is included.
- **Fixtures** are fake/sample data only; not investment advice.
- Deprecated src surfaces have been removed.
  workflow wrappers, compatibility paths) have been removed.
- **Only `decision_support`** may produce formal `Decision` and
  `ExecutionLedger` artifacts.
- **`fund_analysis`** and **`thesis_generation`** do not produce
  formal decisions.
