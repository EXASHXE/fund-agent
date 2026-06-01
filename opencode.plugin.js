// fund-agent OpenCode plugin
//
// Scope (v0.4.3, Markdown-first skill install):
//   1. Logs that the plugin is loaded and which skills are available.
//   2. Registers three custom tools:
//        - fund_agent_skills          list manifest runtime IDs + doc slugs
//        - fund_agent_skill_doc       read a SKILL.md or reference doc
//        - fund_agent_runtime_hint    map runtime ID -> Python runtime class
//   3. Does NOT fetch data, run an autonomous loop, or place trades.
//
// What this plugin intentionally does NOT do:
//   - No provider SDK imports (Tavily, Finnhub, Exa, Firecrawl, Reddit,
//     AkShare, OpenAI, Anthropic, LangChain).
//   - No network calls.
//   - No subprocess spawn. The Python runtime is host-driven; see
//     docs/install/manual-host.md.
//   - No planner loop. OpenCode owns planning, MCP, retries, memory, UX.
//
// The @opencode-ai/plugin import is optional: if it is not available in
// the host runtime, the plugin degrades to log-only mode and still emits
// the same startup metadata.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, normalize, relative } from "node:path";
import { createRequire } from "node:module";

const PLUGIN_VERSION = "0.4.3";
const PLUGIN_NAME = "fund-agent";

// Manifest runtime skill ID -> hyphenated Markdown doc slug.
// This map is the source of truth for the v0.4.3 install and MUST match
// skillpack/fund-agent.skillpack.yaml. A test
// (tests/install/test_skill_doc_slug_mapping.py) guards this invariant.
const SKILL_CATALOG = Object.freeze([
  Object.freeze({
    runtime_id: "fund_analysis",
    doc_slug: "fund-analysis",
    runtime_class: "src.skills_runtime.fund_analysis:FundAnalysisSkill",
    requires_mcp: [],
    produces: ["HardEvidence", "fund_analysis_report", "portfolio_summary"],
  }),
  Object.freeze({
    runtime_id: "news_research",
    doc_slug: "news-research",
    runtime_class: "src.skills_runtime.news_research:NewsResearchSkill",
    requires_mcp: ["web_search", "financial_news"],
    produces: ["SoftEvidence"],
  }),
  Object.freeze({
    runtime_id: "sentiment_analysis",
    doc_slug: "sentiment-analysis",
    runtime_class:
      "src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill",
    requires_mcp: ["social_sentiment"],
    produces: ["SoftEvidence"],
  }),
  Object.freeze({
    runtime_id: "thesis_generation",
    doc_slug: "thesis-generation",
    runtime_class:
      "src.skills_runtime.thesis_generation:ThesisGenerationSkill",
    requires_mcp: [],
    produces: ["ThesisDraft"],
    forbidden: ["formal_decision_generation"],
  }),
  Object.freeze({
    runtime_id: "decision_support",
    doc_slug: "decision-support",
    runtime_class: "src.skills_runtime.decision_support:DecisionSupportSkill",
    requires_mcp: [],
    produces: ["Decision", "ExecutionLedger"],
  }),
]);

const RUNTIME_ID_TO_SLUG = Object.freeze(
  Object.fromEntries(SKILL_CATALOG.map((s) => [s.runtime_id, s.doc_slug])),
);
const SLUG_TO_RUNTIME_ID = Object.freeze(
  Object.fromEntries(SKILL_CATALOG.map((s) => [s.doc_slug, s.runtime_id])),
);

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
    skills: SKILL_CATALOG.map((s) => ({
      runtime_id: s.runtime_id,
      doc_slug: s.doc_slug,
      runtime_class: s.runtime_class,
      requires_mcp: s.requires_mcp,
      produces: s.produces,
    })),
  };
}

async function readSkillDoc({ slug, reference }) {
  if (typeof slug !== "string") {
    return { ok: false, error: "INVALID_INPUT: slug must be a string" };
  }
  if (!Object.prototype.hasOwnProperty.call(SLUG_TO_RUNTIME_ID, slug)) {
    return {
      ok: false,
      error: `INVALID_INPUT: unknown doc slug '${slug}'. Valid: ${SKILL_CATALOG.map((s) => s.doc_slug).join(", ")}`,
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
      runtime_id: SLUG_TO_RUNTIME_ID[slug],
      doc_slug: slug,
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

function runtimeHint({ runtime_id }) {
  if (typeof runtime_id !== "string") {
    return { ok: false, error: "INVALID_INPUT: runtime_id must be a string" };
  }
  const entry = SKILL_CATALOG.find((s) => s.runtime_id === runtime_id);
  if (!entry) {
    return {
      ok: false,
      error: `INVALID_INPUT: unknown runtime_id '${runtime_id}'. Valid: ${SKILL_CATALOG.map((s) => s.runtime_id).join(", ")}`,
    };
  }
  return {
    ok: true,
    runtime_id: entry.runtime_id,
    doc_slug: entry.doc_slug,
    runtime_class: entry.runtime_class,
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
        "List fund-agent manifest runtime skill IDs and their hyphenated Markdown doc slugs. " +
        "Use this to discover what skills are available before reading a specific SKILL.md.",
      args: {},
      async execute() {
        return JSON.stringify(listSkills(), null, 2);
      },
    }),
    fund_agent_skill_doc: toolHelper({
      description:
        "Read a fund-agent SKILL.md (or a file under skills/<slug>/references/) by doc slug. " +
        "Returns the file contents as text. Doc slugs are hyphenated, e.g. 'fund-analysis'.",
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
        "Map a fund-agent manifest runtime skill ID (e.g. 'fund_analysis') to its Python " +
        "runtime class path and required MCP capabilities. This is metadata only; the Python " +
        "runtime is host-driven.",
      args: {
        runtime_id: stringSchema(),
      },
      async execute(args) {
        return JSON.stringify(runtimeHint(args || {}), null, 2);
      },
    }),
  };
}

export const FundAgentPlugin = async ({ client, directory, worktree }) => {
  const skillSlugs = SKILL_CATALOG.map((s) => s.doc_slug).join(", ");

  // Best-effort structured log. If the OpenCode client is not available
  // (e.g. running outside OpenCode for syntax checks) we silently skip.
  try {
    if (client && client.app && client.app.log) {
      await client.app.log({
        body: {
          service: PLUGIN_NAME,
          level: "info",
          message: `${PLUGIN_NAME} v${PLUGIN_VERSION} plugin loaded; skills: ${skillSlugs}`,
          extra: {
            directory: directory || null,
            worktree: worktree || null,
            mode: toolHelper ? "tools+log" : "log-only",
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
              message: "fund-agent skills available; use fund_agent_skills to list them",
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
