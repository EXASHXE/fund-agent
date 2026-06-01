# fund-analyst (Archived)

> **Archived legacy persona material. Not a runtime skill. Not installed.
> Not discovered. Not a plugin entrypoint.**

This directory was moved from `skills/fund-analyst/` to
`docs/archive/fund-analyst/` as part of the v0.4.4
Superpowers-compatible skill surface milestone.

## What was here

The original `skills/fund-analyst/` directory was a legacy umbrella
"persona" directory: an older non-runtime skill that bundled sub-agent
personas (`agents/`), prompt templates (`prompts/`), and reference
material (`references/`) under a single `SKILL.md`. It was never a
runtime entrypoint: it had no `runtime` class path, no
`SkillInput`/`SkillOutput` contract, and was not declared in
`skillpack/fund-agent.skillpack.yaml`.

## What replaced it

The v0.4.4+ skill surface is a **composable collection of hyphenated
Markdown skills**, Superpowers-style:

- `skills/fund-analysis/` — primary / default entrypoint
- `skills/decision-support/` — supporting
- `skills/news-research/` — supporting
- `skills/sentiment-analysis/` — supporting
- `skills/thesis-generation/` — supporting

Each is declared in `skillpack/fund-agent.skillpack.yaml` and maps 1:1
to a Python runtime class under `src/skills_runtime/`.

## What you should do with this material

This material is retained for **historical reference only**. It is not
discovered by the OpenCode plugin, not copied by any installer, and
not used as a runtime entrypoint.

If any content here is still useful, it should be **merged** into the
relevant `skills/<slug>/references/*.md` file (most likely
`skills/fund-analysis/references/`), and then this archive directory
should be deleted in a follow-up cleanup milestone.

Do not introduce a runtime entrypoint under this directory. Do not add
a `SKILL.md` that is exposed by the OpenCode plugin. Do not reference
this directory from any install doc, the manifest, or the host
integration flow.
