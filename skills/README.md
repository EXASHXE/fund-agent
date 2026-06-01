# fund-agent Skills

`fund-agent` is Markdown-first at the skill layer. External hosts should read
this directory for agent-facing workflow, policy, constraints, and report style,
then call the deterministic Python runtime declared by the manifest.

## Canonical Runtime Skill IDs

The callable skill IDs are the underscore names declared in
`skillpack/fund-agent.skillpack.yaml`:

| Runtime skill ID | Markdown doc slug | Runtime |
|---|---|---|
| `fund_analysis` | `fund-analysis` | `src.skills_runtime.fund_analysis:FundAnalysisSkill` |
| `news_research` | `news-research` | `src.skills_runtime.news_research:NewsResearchSkill` |
| `sentiment_analysis` | `sentiment-analysis` | `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill` |
| `thesis_generation` | `thesis-generation` | `src.skills_runtime.thesis_generation:ThesisGenerationSkill` |
| `decision_support` | `decision-support` | `src.skills_runtime.decision_support:DecisionSupportSkill` |

External hosts must discover callable skills from
`skillpack/fund-agent.skillpack.yaml`, not from folder names.

## Directory Policy

- Hyphenated directories such as `fund-analysis/` are the canonical Markdown
  skill documentation slugs.
- Each canonical skill directory has a `SKILL.md` file. This is the primary
  agent-facing instruction file.
- `references/*.md` files contain longer policies, examples, templates, and
  method documents.
- Underscore directories such as `fund_analysis/` are compatibility shims only
  when retained for older imports or tests. They are not Markdown skill docs and
  must not be presented as second runtime skills.
- `fund-analyst/` is legacy/reference-only persona material. It is not a
  runtime entrypoint and must not be used for host invocation.
- `src/` contains deterministic runtime, schemas, and pure tool
  implementation only.

## Host Usage

1. Load `skillpack/fund-agent.skillpack.yaml`.
2. Select a manifest runtime skill ID such as `fund_analysis`.
3. Read `skills/<slug>/SKILL.md` for usage policy, where `<slug>` is the
   hyphenated documentation slug such as `fund-analysis`.
4. Provide host-owned data and MCP adapters as required.
5. Call the manifest runtime class with `SkillInput`.

Do not infer `fund_analysis` from `skills/fund-analysis/`, and do not infer a
callable runtime from `skills/fund_analysis/`.
