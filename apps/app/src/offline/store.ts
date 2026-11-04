// Web: localStorage (the service worker keeps the brief page itself in Cache Storage). Wrapped: storage can be
// unavailable in private windows.
export async function getItem(key: string): Promise<string | null> {
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export async function setItem(key: string, value: string): Promise<void> {
  try {
    globalThis.localStorage?.setItem(key, value);
  } catch {
    // storage blocked: the brief is simply not kept offline
  }
}
