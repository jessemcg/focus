const fs = require("node:fs");
const path = require("node:path");

const PRIORITY_SETTING_KEY = "fireworksPriorityServiceTier";

function readPriorityConfiguration(cwd) {
  const projectDir = path.join(cwd, ".pi");
  const settings = JSON.parse(
    fs.readFileSync(path.join(projectDir, "settings.json"), "utf8"),
  );
  const manifest = JSON.parse(
    fs.readFileSync(
      path.join(projectDir, "fireworks-priority-models.json"),
      "utf8",
    ),
  );
  if (!Array.isArray(manifest.models)) {
    throw new Error("Fireworks Priority manifest must contain a models list.");
  }
  const enabled = settings[PRIORITY_SETTING_KEY] ?? true;
  if (typeof enabled !== "boolean") {
    throw new Error(`${PRIORITY_SETTING_KEY} must be true or false.`);
  }
  return {
    enabled,
    modelIds: new Set(
      manifest.models.filter(
        (modelId) => typeof modelId === "string" && modelId.length > 0,
      ),
    ),
  };
}

function fireworksPriorityExtension(pi) {
  let configuration;
  pi.on("before_provider_request", (event, ctx) => {
    const model = ctx.model;
    if (!model || model.provider !== "fireworks") {
      return undefined;
    }
    configuration ??= readPriorityConfiguration(ctx.cwd);
    if (!configuration.enabled || !configuration.modelIds.has(model.id)) {
      return undefined;
    }
    const payload = event.payload;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return undefined;
    }
    return { ...payload, service_tier: "priority" };
  });
}

fireworksPriorityExtension.readPriorityConfiguration = readPriorityConfiguration;
module.exports = fireworksPriorityExtension;
