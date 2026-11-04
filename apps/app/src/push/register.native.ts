// Android: Expo push token → channels /push/subscribe (kind "expo"). Called only after "Turn on alerts".
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "../api/channels";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerPush(token: string): Promise<boolean> {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "Advice",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
    await Notifications.setNotificationChannelAsync("danger", {
      name: "Danger alerts",
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 600, 300, 600, 300, 600],
      bypassDnd: true,
    });
  }
  if (!Device.isDevice) return false;
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== "granted") return false;
  const projectId = Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
  const { data } = await Notifications.getExpoPushTokenAsync({ projectId });
  await api.subscribe(token, { kind: "expo", endpoint: data, user_agent: `android ${Device.osVersion ?? ""}`.trim() });
  return true;
}

/** Path to open when a push is tapped (payload `data.url`, never coordinates). */
export function pushUrl(response: Notifications.NotificationResponse): string | null {
  const url = response.notification.request.content.data?.url;
  return typeof url === "string" && url.startsWith("/") ? url : null;
}
