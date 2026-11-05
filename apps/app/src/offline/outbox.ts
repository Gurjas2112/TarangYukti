// Web build: no trip mode, so no position outbox (the open page sends live positions directly).
import type { Fix } from "../api/channels";

export async function add(_boatId: string, _fix: Fix): Promise<void> {}
export async function pending(): Promise<number> {
  return 0;
}
export async function sync(): Promise<number> {
  return 0;
}
