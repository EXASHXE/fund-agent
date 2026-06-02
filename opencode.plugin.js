// fund-agent OpenCode plugin
//
// Scope (v0.4.6, native skill install hardening):
//   1. Logs that the plugin is loaded and which hyphenated skills are
//      available, distinguishing the primary skill from the four
//      supporting skills in both the message text and the structured
//      `extra` payload.
//   2. Registers three custom tools:
//        - fund_agent_skills          list manifest runtime IDs + doc slugs
//        - fund_agent_skill_doc       read a SKILL.md or reference doc
//                                     (hyphenated slugs only)
//        - fund_agent_runtime_hint    map hyphenated slug or runtime ID
//                                     to the Python runtime class
//   3. Does NOT fetch data, run an autonomous loop, or place trades.
//
// Skill surface (v0.4.6, Superpowers-compatible):
//   - Agent-facing skill names are hyphenated Markdown doc slugs:
//       fund-analysis              (primary / default)
//       decision-support           (supporting)
//       news-research              (supporting)
//       sentiment-analysis         (supporting)
//       thesis-generation          (supporting)
//   - Python runtime IDs remain underscore names in the manifest and
//     Python (fund_analysis, decision_support, news_research,
//     sentiment_analysis, thesis_generation).
//   - The OpenCode plugin does NOT expose underscore skill slugs as
//     agent-facing skill names.
//   - The archived `fund-analyst` persona material is NOT exposed as
//     a skill and is NOT installable.
//
// What this plugin intentionally does NOT do:
//   - No provider SDK imports (Tavily, Finnhub, Exa, Firecrawl, Reddit,
//     AkShare, OpenAI, Anthropic, LangChain).
//   - No network calls.
//   - No subprocess spawn. The Python runtime is host-driven; see
//     docs/install/manual-host.md.
//   - No planner loop. OpenCode owns planning, MCP, retries, memory, UX.
//   - No native Agent Skills sync. The plugin is a metadata + doc
//     reader only; the canonical skill surface is the hyphenated
//     Markdown directories under `skills/<slug>/SKILL.md`. For the
//     optional native OpenCode Agent Skills install, run
//     `python scripts/install_opencode_skills.py`.
//
// The @opencode-ai/plugin import is optional: if it is not available in
// the host runtime, the plugin degrades to log-only mode and still emits
// the same startup metadata.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, normalize, relative } from "node:path";
import { createRequire } from "node:module";

const PLUGIN_VERSION = "0.4.7-dev";
const PLUGIN_NAME = "fund-agent";

// Manifest runtime skill ID -> hyphenated Markdown doc slug.
// This map is the source of truth for the v0.4.6 install and MUST match
// skillpack/fund-agent.skillpack.yaml. A test
// (tests/install/test_skill_doc_slug_mapping.py) guards this invariant.
// The `role` field marks fund-analysis as the primary / default skill
// and the rest as supporting skills. It is metadata only.
const SKILL_CATALOG = Object.freeze([
  Object.freeze({
    runtime_id: "fund_analysis",
    doc_slug: "fund-analysis",
    runtime_class: "src.skills_runtime.fund_analysis:FundAnalysisSkill",
    requires_mcp: [],
    produces: ["HardEvidence", "fund_analysis_report", "portfolio_summary"],
    role: "primary",
  }),
  Object.freeze({
    runtime_id: "decision_support",
    doc_slug: "decision-support",
    runtime_class: "src.skills_runtime.decision_support:DecisionSupportSkill",
    requires_mcp: [],
    produces: ["Decision", "ExecutionLedger"],
    role: "supporting",
  }),
  Object.freeze({
    runtime_id: "news_research",
    doc_slug: "news-research",
    runtime_class: "src.skills_runtime.news_research:NewsResearchSkill",
    requires_mcp: ["web_search", "financial_news"],
    produces: ["SoftEvidence"],
    role: "supporting",
  }),
  Object.freeze({
    runtime_id: "sentiment_analysis",
    doc_slug: "sentiment-analysis",
    runtime_class:
      "src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill",
    requires_mcp: ["social_sentiment"],
    produces: ["SoftEvidence"],
    role: "supporting",
  }),
  Object.freeze({
    runtime_id: "thesis_generation",
    doc_slug: "thesis-generation",
    runtime_class:
      "src.skills_runtime.thesis_generation:ThesisGenerationSkill",
    requires_mcp: [],
    produces: ["ThesisDraft"],
    forbidden: ["formal_decision_generation"],
    role: "supporting",
  }),
]);

const RUNTIME_ID_TO_SLUG = Object.freeze(
  Object.fromEntries(SKILL_CATALOG.map((s) => [s.runtime_id, s.doc_slug])),
);
const SLUG_TO_RUNTIME_ID = Object.freeze(
  Object.fromEntries(SKILL_CATALOG.map((s) => [s.doc_slug, s.runtime_id])),
);

// Set of valid hyphenated doc slugs (the agent-facing skill names).
const VALID_SLUGS = Object.freeze(new Set(SKILL_CATALOG.map((s) => s.doc_slug)));
// Set of valid underscore runtime IDs.
const VALID_RUNTIME_IDS = Object.freeze(
  new Set(SKILL_CATALOG.map((s) => s.runtime_id)),
);

function isHyphenatedSlug(slug) {
  // Reject any input that is not a hyphenated kebab-case string in
  // our catalog. This blocks underscore skill slugs and the archived
  // `fund-analyst` persona from being treated as agent-facing skills.
  if (typeof slug !== "string" || slug.length === 0) return false;
  if (slug.includes("_")) return false;
  if (slug.includes("/") || slug.includes("\\") || slug.includes("\0")) {
    return false;
  }
  return VALID_SLUGS.has(slug);
}

function getPluginDir() {
  // When loaded by Bun/OpenCode the plugin file URL is the canonical
  // source for the on-disk location. The repo root is the parent of
  // opencode.plugin.js.
  try {
    return dirname(fileURLToPath(import.meta.url));
  } catch {
    return process.cwd();
  }
}

function resolveSafePath(pluginDir, requestedRelative) {
  // Hard-deny absolute paths and any traversal that escapes the
  // skills/ or docs/ subtree.
  if (typeof requestedRelative !== "string" || requestedRelative.length === 0) {
    return null;
  }
  if (requestedRelative.includes("\0")) {
    return null;
  }
  const cleaned = normalize(requestedRelative).replace(/^[/\\]+/, "");
  if (cleaned.startsWith("..") || cleaned.includes("..\\") || cleaned.includes("../")) {
    return null;
  }
  const abs = join(pluginDir, cleaned);
  const rel = relative(pluginDir, abs);
  if (rel.startsWith("..") || rel.includes("..\\") || rel.includes("../")) {
    return null;
  }
  return abs;
}

function listSkills() {
  return {
    plugin: PLUGIN_NAME,
    version: PLUGIN_VERSION,
    schema_version: "skillpack.v1",
    // The OpenCode plugin exposes the five hyphenated Markdown doc
    // slugs as the agent-facing skill names. Underscore runtime IDs
    // are included as Python integration metadata, but are NOT
    // agent-facing skill names.
    skills: SKILL_CATALOG.map((s) => ({
      skill: s.doc_slug,            // agent-facing skill name
      runtime_id: s.runtime_id,     // Python runtime ID
      role: s.role,                 // primary | supporting
      runtime_class: s.runtime_class,
      requires_mcp: s.requires_mcp,
      produces: s.produces,
    })),
    primary_skill: "fund-analysis",
    supporting_skills: [
      "decision-support",
      "news-research",
      "sentiment-analysis",
      "thesis-generation",
    ],
  };
}

async function readSkillDoc({ slug, reference }) {
  if (typeof slug !== "string") {
    return { ok: false, error: "INVALID_INPUT: slug must be a string" };
  }
  // Reject underscore skill slugs (e.g. fund_analysis). The
  // agent-facing skill name is the hyphenated Markdown doc slug.
  if (slug.includes("_")) {
    return {
      ok: false,
      error:
        `INVALID_INPUT: doc slug '${slug}' is an underscore runtime ID, not a hyphenated ` +
        `agent-facing skill name. Valid: ${Array.from(VALID_SLUGS).join(", ")}`,
    };
  }
  // Reject the archived fund-analyst persona explicitly.
  if (slug === "fund-analyst" || slug.startsWith("fund-analyst/")) {
    return {
      ok: false,
      error:
        `INVALID_INPUT: '${slug}' is archived legacy persona material and is not a ` +
        `fund-agent skill. See docs/archive/fund-analyst/.`,
    };
  }
  if (!isHyphenatedSlug(slug)) {
    return {
      ok: false,
      error: `INVALID_INPUT: unknown doc slug '${slug}'. Valid: ${Array.from(VALID_SLUGS).join(", ")}`,
    };
  }
  const pluginDir = getPluginDir();
  const relPath =
    reference && typeof reference === "string"
      ? join("skills", slug, "references", reference)
      : join("skills", slug, "SKILL.md");
  const abs = resolveSafePath(pluginDir, relPath);
  if (!abs) {
    return { ok: false, error: "INVALID_INPUT: unsafe path" };
  }
  try {
    const text = await readFile(abs, "utf8");
    return {
      ok: true,
      skill: slug,                       // agent-facing skill name
      runtime_id: SLUG_TO_RUNTIME_ID[slug],
      path: relPath,
      content: text,
    };
  } catch (err) {
    return {
      ok: false,
      error: `NOT_FOUND: ${relPath} (${err && err.code ? err.code : "UNKNOWN"})`,
    };
  }
}

function runtimeHint({ runtime_id, slug }) {
  // Accept either a hyphenated agent-facing slug (preferred) or an
  // underscore Python runtime ID. This lets a host pass the name it
  // already has on hand and still resolve the Python class.
  let entry = null;
  let inputKind = null;
  if (typeof runtime_id === "string" && runtime_id.length > 0) {
    if (runtime_id.includes("_")) {
      // underscore runtime ID
      if (VALID_RUNTIME_IDS.has(runtime_id)) {
        entry = SKILL_CATALOG.find((s) => s.runtime_id === runtime_id);
        inputKind = "runtime_id";
      }
    } else {
      // treat as hyphenated slug
      if (VALID_SLUGS.has(runtime_id)) {
        entry = SKILL_CATALOG.find((s) => s.doc_slug === runtime_id);
        inputKind = "doc_slug";
      }
    }
  }
  if (!entry && typeof slug === "string" && slug.length > 0) {
    if (VALID_SLUGS.has(slug)) {
      entry = SKILL_CATALOG.find((s) => s.doc_slug === slug);
      inputKind = "doc_slug";
    } else if (VALID_RUNTIME_IDS.has(slug)) {
      entry = SKILL_CATALOG.find((s) => s.runtime_id === slug);
      inputKind = "runtime_id";
    }
  }
  if (!entry) {
    return {
      ok: false,
      error:
        `INVALID_INPUT: cannot resolve skill. Provide a hyphenated ` +
        `agent-facing slug (${Array.from(VALID_SLUGS).join(", ")}) or an ` +
        `underscore runtime ID (${Array.from(VALID_RUNTIME_IDS).join(", ")}).`,
    };
  }
  return {
    ok: true,
    input_kind: inputKind,
    skill: entry.doc_slug,              // agent-facing skill name
    runtime_id: entry.runtime_id,       // Python runtime ID
    runtime_class: entry.runtime_class,
    role: entry.role,
    requires_mcp: entry.requires_mcp,
    produces: entry.produces,
    note:
      "Python runtime integration is host-driven. See docs/install/manual-host.md " +
      "and examples/minimal_host_news_to_decision.py for a complete flow.",
  };
}

// Best-effort import of the @opencode-ai/plugin helper. If it is not
// available (e.g. running outside OpenCode, or before `bun install` has
// resolved peers) we fall back to log-only mode and still emit startup
// metadata. This keeps the plugin testable with `node --check` and
// keeps the install honest about what runs.
let toolHelper = null;
let toolSchema = null;
try {
  const require = createRequire(import.meta.url);
  const mod = require("@opencode-ai/plugin");
  toolHelper = mod && mod.tool ? mod.tool : null;
  toolSchema = mod && mod.tool && mod.tool.schema ? mod.tool.schema : null;
} catch {
  // Optional peer dep not resolved; log-only mode.
}

function buildTools() {
  if (!toolHelper) {
    return {};
  }
  const stringSchema = () =>
    toolSchema && toolSchema.string ? toolSchema.string() : { type: "string" };
  return {
    fund_agent_skills: toolHelper({
      description:
        "List the fund-agent Superpowers-compatible skill collection. " +
        "Returns the five hyphenated agent-facing skill names (primary " +
        "skill fund-analysis, plus four supporting skills), their " +
        "underscore Python runtime IDs, the primary skill, and the list " +
        "of supporting skills. Use this to discover what skills are " +
        "available before reading a specific SKILL.md.",
      args: {},
      async execute() {
        return JSON.stringify(listSkills(), null, 2);
      },
    }),
    fund_agent_skill_doc: toolHelper({
      description:
        "Read a fund-agent SKILL.md (or a file under skills/<slug>/references/) " +
        "by hyphenated doc slug. The agent-facing skill names are " +
        "hyphenated Markdown doc slugs (e.g. 'fund-analysis'). The plugin " +
        "rejects underscore skill slugs (e.g. 'fund_analysis') and the " +
        "archived 'fund-analyst' persona. Returns the file contents as text.",
      args: {
        slug: stringSchema(),
        reference: toolSchema && toolSchema.string ? toolSchema.string().optional() : stringSchema(),
      },
      async execute(args) {
        const result = await readSkillDoc(args || {});
        return JSON.stringify(result, null, 2);
      },
    }),
    fund_agent_runtime_hint: toolHelper({
      description:
        "Map a fund-agent skill identifier to its Python runtime class " +
        "path and required MCP capabilities. Accepts either a " +
        "hyphenated agent-facing slug (e.g. 'fund-analysis') or an " +
        "underscore Python runtime ID (e.g. 'fund_analysis'). The two " +
        "resolve to the same Python class. This is metadata only; the " +
        "Python runtime is host-driven.",
      args: {
        runtime_id: toolSchema && toolSchema.string ? toolSchema.string().optional() : stringSchema(),
        slug: toolSchema && toolSchema.string ? toolSchema.string().optional() : stringSchema(),
      },
      async execute(args) {
        return JSON.stringify(runtimeHint(args || {}), null, 2);
      },
    }),
  };
}

export function buildStartupLogMessage() {
  // The agent-facing skill names are the hyphenated Markdown doc slugs.
  // The plugin never logs or registers underscore skill slugs.
  // Distinguish the primary skill from the supporting skills so the
  // log message never misclassifies fund-analysis as a supporting
  // skill. (v0.4.6 install-hardening.)
  const primaryEntry = SKILL_CATALOG.find((s) => s.role === "primary");
  const supportingEntries = SKILL_CATALOG.filter((s) => s.role === "supporting");
  const primarySkill = primaryEntry ? primaryEntry.doc_slug : null;
  const supportingSkills = supportingEntries.map((s) => s.doc_slug);
  return {
    primary_skill: primarySkill,
    supporting_skills: supportingSkills,
    message:
      `${PLUGIN_NAME} v${PLUGIN_VERSION} plugin loaded; ` +
      `primary skill: ${primarySkill}; ` +
      `supporting skills: ${supportingSkills.join(", ")}`,
  };
}

export const FundAgentPlugin = async ({ client, directory, worktree }) => {
  // The agent-facing skill names are the hyphenated Markdown doc slugs.
  // The plugin never logs or registers underscore skill slugs.
  // Distinguish the primary skill from the supporting skills so the
  // log message never misclassifies fund-analysis as a supporting
  // skill. (v0.4.6 install-hardening: listSkills() already returned
  // the right split; the startup log now matches.)
  const { message, primary_skill, supporting_skills } = buildStartupLogMessage();

  // Best-effort structured log. If the OpenCode client is not available
  // (e.g. running outside OpenCode for syntax checks) we silently skip.
  try {
    if (client && client.app && client.app.log) {
      await client.app.log({
        body: {
          service: PLUGIN_NAME,
          level: "info",
          message: message,
          extra: {
            directory: directory || null,
            worktree: worktree || null,
            mode: toolHelper ? "tools+log" : "log-only",
            primary_skill: primary_skill,
            supporting_skills: supporting_skills,
          },
        },
      });
    }
  } catch {
    // Logging is best-effort; never throw from a plugin initializer.
  }

  const tools = buildTools();

  return {
    // Event hook: log on session start so the user can confirm the
    // plugin is alive in the OpenCode session log.
    event: async ({ event }) => {
      if (!event) return;
      if (event.type !== "session.created") return;
      try {
        if (client && client.app && client.app.log) {
          await client.app.log({
            body: {
              service: PLUGIN_NAME,
              level: "debug",
              message: "fund-agent skills available; start with fund-analysis, load supporting skills only when their description matches",
              extra: { sessionID: event.properties && event.properties.id },
            },
          });
        }
      } catch {
        // ignore
      }
    },
    // Custom tool surface. Empty object in log-only mode keeps the
    // plugin shape stable across installs.
    tool: tools,
  };
};

export default FundAgentPlugin;
