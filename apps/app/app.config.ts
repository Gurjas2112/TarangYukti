import type { ExpoConfig } from "expo/config";

// APP_ENV: development | preview | live | store | capture (EAS build profiles, spec §17.12)
const appEnv = process.env.APP_ENV ?? "development";
const isDev = appEnv === "development";
// Plain HTTP to the laptop backend: development builds and the never-distributed capture build only (spec §17.14).
const laptopBackend = isDev || appEnv === "capture";

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
    permissions: ["android.permission.RECORD_AUDIO", "android.permission.POST_NOTIFICATIONS"],
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
    [
      "expo-notifications",
      { icon: "./assets/images/android-icon-monochrome.png", color: "#0B1D2E", defaultChannel: "default" },
    ],
    "expo-sqlite",
    [
      "expo-audio",
      {
        microphonePermission: "Kadal Mitra listens only while you hold the speak button, to answer your question.",
      },
    ],
    "@react-native-google-signin/google-signin",
    ["expo-build-properties", { android: { usesCleartextTraffic: laptopBackend } }],
    // TODO(tarangyukti): Milestones 7–11 add @maplibre/maplibre-react-native, expo-location (background) and
    // expo-build-properties (cleartext only when isDev).
  ],
  experiments: { typedRoutes: true },
  extra: { appEnv, cleartextAllowed: laptopBackend, eas: { projectId: "3d825c81-c777-423d-a423-b8b2e96a648f" } },
};

export default config;
