# fund-agent Skills

`fund-agent` is Markdown-first at the skill layer. External hosts should read
this directory for agent-facing workflow, policy, constraints, and report style,
then call the deterministic Python runtime declared by the manifest.

## Skill Surface (Superpowers-compatible)

`fund-agent` exposes a **composable collection of Markdown skills**,
Superpowers-style: one hyphenated `skills/<slug>/SKILL.md` directory per
skill, with the directory name matching the skill's frontmatter `name`
field. The agent-facing skill name is the hyphenated slug; the
underscore name is the Python runtime ID only.

### Primary / default skill

- `fund-analysis` — primary portfolio and fund report entrypoint.
  Load this first for ordinary user requests like
  `分析下我的基金给出报告`. `fund-analysis` alone is sufficient for a
  report-only flow.

### Supporting skills

Load a supporting skill only when the subtask description matches, and
only after `fund-analysis` (or equivalent evidence) is in scope:

| Supporting skill | Load when |
|---|---|
| `decision-support` | The user asks for a formal BUY / SELL / INCREASE / REDUCE / WAIT / HOLD action, and an `EvidenceGraph` plus optional trade plan already exists. This is the **only** skill that may produce a formal `Decision` / `ExecutionLedger`. |
| `news-research` | The host has a `web_search` / `financial_news` MCP capability and the user wants news-backed `SoftEvidence` for a fund, holding, theme, manager, or macro topic. |
| `sentiment-analysis` | The host has a `social_sentiment` MCP capability and the user wants sentiment-backed `SoftEvidence`. |
| `thesis-generation` | The host wants a `thesis_draft` artifact before deciding whether to escalate to a formal decision. Never produces `Decision` / `ExecutionLedger`. |

## Agent-Facing Slugs vs Python Runtime IDs

| Agent-facing skill (slug) | Python runtime ID | Runtime class |
|---|---|---|
| `fund-analysis` | `fund_analysis` | `src.skills_runtime.fund_analysis:FundAnalysisSkill` |
| `decision-support` | `decision_support` | `src.skills_runtime.decision_support:DecisionSupportSkill` |
| `news-research` | `news_research` | `src.skills_runtime.news_research:NewsResearchSkill` |
| `sentiment-analysis` | `sentiment_analysis` | `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill` |
| `thesis-generation` | `thesis_generation` | `src.skills_runtime.thesis_generation:ThesisGenerationSkill` |

- External hosts should pass the **hyphenated slug** to the OpenCode
  plugin's `fund_agent_skill_doc` tool.
- External hosts should pass the **underscore runtime ID** to
  `fund_agent_runtime_hint` and to `SkillInput(skill_name=...)`.
- The two are linked 1:1 by `skillpack/fund-agent.skillpack.yaml`; do
  not infer either from a filesystem directory name alone.

## Directory Policy

- Hyphenated directories such as `fund-analysis/` are the canonical
  Markdown skill documentation slugs and the only agent-facing skill
  directories. Each one has a `SKILL.md` file (the primary
  agent-facing instruction file) and optional `references/*.md` files
  (longer policy, examples, templates, and method documents).
- Underscore `skills/` directories (e.g. `skills/fund_analysis/`) are
  **not** part of the v0.4.4+ skill surface. They have been removed
  from this milestone. Older clones that still ship them are
  compatibility-only; they must not be discovered, must not be exposed
  by the OpenCode plugin, must not be copied by any installer, and
  must not be presented as a second runtime skill. If you are
  migrating from a pre-v0.4.4 install, delete the underscore
  directories under `skills/` and rely on the canonical
  hyphenated SKILL.md directories.
- `fund-analyst/` was the legacy persona directory. It has been moved
  to `docs/archive/fund-analyst/` and is **not** a runtime entrypoint,
  is **not** installed, and is **not** discovered.
- `src/` contains deterministic runtime, schemas, and pure tool
  implementation only.

## Host Usage

1. Load `skillpack/fund-agent.skillpack.yaml`.
2. For ordinary user requests, start with the primary skill
   `fund-analysis`. Read `skills/fund-analysis/SKILL.md` for usage
   policy, inputs, outputs, and forbidden behavior.
3. If the user is asking for news, sentiment, a thesis, or a formal
   decision, also read the matching supporting skill's `SKILL.md`.
4. Provide host-owned data and MCP adapters as required.
5. Call the manifest runtime class with `SkillInput`.

Do not infer a runtime ID from a folder name. Do not call any
underscore `skills/` directory as if it were a second runtime.
