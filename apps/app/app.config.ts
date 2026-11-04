import type { ExpoConfig } from "expo/config";

// APP_ENV: development | preview | live | store | capture (EAS build profiles, spec §17.12)
const appEnv = process.env.APP_ENV ?? "development";
const isDev = appEnv === "development";

const config: ExpoConfig = {
  name: "Kadal Mitra",
  slug: "tarangyukti",
  owner: "gurjas_gandhi",
  version: "0.1.0",
  orientation: "portrait",
  icon: "./assets/images/icon.png",
  scheme: "tarangyukti",
  userInterfaceStyle: "light", // sunlight theme by default (prompt §10.9)
  platforms: ["android", "web"],
  android: {
    package: "in.tarangyukti.kadalmitra",
    allowBackup: false,
    adaptiveIcon: {
      backgroundColor: "#FFFFFF",
      foregroundImage: "./assets/images/android-icon-foreground.png",
      backgroundImage: "./assets/images/android-icon-background.png",
      monochromeImage: "./assets/images/android-icon-monochrome.png",
    },
  },
  web: {
    bundler: "metro",
    output: "single",
    favicon: "./assets/images/favicon.png",
  },
  updates: { enabled: false }, // no over-the-air updates in live testing
  plugins: [
    "expo-router",
    "expo-localization",
    [
      "expo-splash-screen",
      { backgroundColor: "#FFFFFF", image: "./assets/images/splash-icon.png", imageWidth: 76 },
    ],
    // TODO(tarangyukti): Milestones 6–11 add @maplibre/maplibre-react-native, expo-notifications,
    // expo-sqlite, expo-location (background) and expo-build-properties (cleartext only when isDev).
  ],
  experiments: { typedRoutes: true },
  extra: { appEnv, cleartextAllowed: isDev, eas: { projectId: "3d825c81-c777-423d-a423-b8b2e96a648f" } },
};

export default config;
