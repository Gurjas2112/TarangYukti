// Voice out (spec §6.5): Bulbul audio from channels /tts for Group A languages; Group B gets text only.
// Audio URLs are cached per (text, language) for the session; the server caches the mp3 itself.
import { type AudioPlayer, createAudioPlayer } from "expo-audio";

import { api } from "../api/channels";
import { languageInfo } from "../i18n";

const urls = new Map<string, string | null>();
let player: AudioPlayer | null = null;

export function hasVoice(lang: string): boolean {
  return languageInfo(lang)?.group === "A";
}

export async function audioUrl(text: string, lang: string): Promise<string | null> {
  if (!hasVoice(lang)) return null;
  const k = `${lang}|${text}`;
  if (!urls.has(k)) urls.set(k, (await api.tts(text, lang)).url);
  return urls.get(k) ?? null;
}

export function stop(): void {
  player?.pause();
  player?.remove();
  player = null;
}

export async function speak(text: string, lang: string): Promise<boolean> {
  const url = await audioUrl(text, lang).catch(() => null);
  if (!url) return false;
  stop();
  player = createAudioPlayer({ uri: url });
  player.play();
  return true;
}
