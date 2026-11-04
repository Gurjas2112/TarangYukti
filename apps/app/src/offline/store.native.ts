// Android: small key-value store in SQLite (the saved brief opens with no signal, spec §7.8).
import Storage from "expo-sqlite/kv-store";

export async function getItem(key: string): Promise<string | null> {
  return Storage.getItem(key);
}

export async function setItem(key: string, value: string): Promise<void> {
  await Storage.setItem(key, value);
}
