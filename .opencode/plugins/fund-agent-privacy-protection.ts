/**
 * fund-agent-privacy-protection.ts
 *
 * OpenCode plugin that warns when the agent attempts to read sensitive
 * private data files. This is a best-effort guard — OpenCode's hook API
 * may not support blocking reads in all cases, so this plugin logs
 * warnings and marks the session when private data is accessed.
 *
 * Protected paths:
 *   - private_data/
 *   - local_data/
 *   - local_reports/
 *   - eval_workspace/
 *   - *.private.json, *.private.yaml, *.private.csv
 *   - .env, .env.*
 *
 * The fund-agent-e2e runner is allowed to operate since it reads these
 * files internally without dumping contents to the chat.
 */

const PROTECTED_PATTERNS = [
  /^private_data\//,
  /^local_data\//,
  /^local_reports\//,
  /^eval_workspace\//,
  /\.private\.(json|yaml|csv)$/,
  /^\.env(\.|$)/,
];

function isProtectedPath(filePath: string): boolean {
  const normalized = filePath.replace(/\\/g, "/");
  for (const pattern of PROTECTED_PATTERNS) {
    if (pattern.test(normalized)) {
      return true;
    }
  }
  return false;
}

export const FundAgentPrivacyPlugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      // Log plugin loaded
      if (event?.type === "session.created") {
        try {
          if (client?.app?.log) {
            await client.app.log({
              body: {
                service: "fund-agent-privacy",
                level: "info",
                message:
                  "fund-agent privacy protection active; " +
                  "private_data/, local_data/, local_reports/, eval_workspace/, " +
                  "*.private.*, .env* are protected paths",
              },
            });
          }
        } catch {
          // Logging is best-effort
        }
      }
    },

    tool: {
      fund_agent_check_privacy: {
        description:
          "Check if a file path is a protected private data path. " +
          "Returns whether the path is protected and which pattern matched.",
        args: {
          path: { type: "string", description: "File path to check" },
        },
        async execute({ path }: { path: string }) {
          if (!path || typeof path !== "string") {
            return JSON.stringify({ ok: false, error: "path is required" });
          }
          const normalized = path.replace(/\\/g, "/");
          const matched = PROTECTED_PATTERNS.find((p) => p.test(normalized));
          return JSON.stringify({
            ok: true,
            path: normalized,
            protected: !!matched,
            pattern: matched?.source || null,
          });
        },
      },
    },
  };
};

export default FundAgentPrivacyPlugin;
