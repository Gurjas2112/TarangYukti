// Metro config: Expo defaults + the CopilotKit override that resolves only `jose` with the
// `browser` condition (needed for release bundles; spec §17.8).
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);
const upstreamResolve = config.resolver.resolveRequest;

config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === "jose" || moduleName.startsWith("jose/")) {
    return context.resolveRequest(
      { ...context, unstable_conditionNames: ["browser", "import", "require", "default"] },
      moduleName,
      platform,
    );
  }
  return (upstreamResolve ?? context.resolveRequest)(context, moduleName, platform);
};

module.exports = config;
