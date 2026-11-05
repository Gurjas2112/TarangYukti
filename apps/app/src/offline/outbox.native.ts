// Position outbox on Android (spec §17.4): every trip-mode fix is written to SQLite first and sent to channels
// /positions when the phone is online, so a trip with no signal is still recorded and synced later.
// Raw coordinates stay on the phone and in Supabase only (rule 8); they never reach logs.
import * as SQLite from "expo-sqlite";

import { api, type Fix } from "../api/channels";
import { supabase } from "../auth/supabase";

const BATCH = 100;
let db: SQLite.SQLiteDatabase | null = null;

async function open(): Promise<SQLite.SQLiteDatabase> {
  if (db) return db;
  db = await SQLite.openDatabaseAsync("ty-outbox.db");
  await db.execAsync(`create table if not exists outbox (
    id integer primary key autoincrement, boat_id text not null, lat real not null, lon real not null,
    speed_knots real, recorded_at text not null)`);
  return db;
}

export async function add(boatId: string, fix: Fix): Promise<void> {
  const d = await open();
  await d.runAsync(
    "insert into outbox (boat_id, lat, lon, speed_knots, recorded_at) values (?, ?, ?, ?, ?)",
    boatId,
    fix.lat,
    fix.lon,
    fix.speed_knots ?? null,
    fix.recorded_at,
  );
}

export async function pending(): Promise<number> {
  const d = await open();
  const row = await d.getFirstAsync<{ n: number }>("select count(*) as n from outbox");
  return row?.n ?? 0;
}

type Row = { id: number; boat_id: string; lat: number; lon: number; speed_knots: number | null; recorded_at: string };

/** Send everything queued, oldest first, in batches. Returns how many were sent; stops quietly when offline. */
export async function sync(): Promise<number> {
  const token = (await supabase().auth.getSession()).data.session?.access_token;
  if (!token) return 0;
  const d = await open();
  let sent = 0;
  for (;;) {
    const rows = await d.getAllAsync<Row>("select * from outbox order by id limit ?", BATCH);
    if (rows.length === 0) return sent;
    const boatId = rows[0].boat_id;
    const same = rows.filter((r) => r.boat_id === boatId);
    try {
      await api.positions(
        token,
        boatId,
        "mobile_app",
        same.map((r) => ({ lat: r.lat, lon: r.lon, recorded_at: r.recorded_at, speed_knots: r.speed_knots })),
      );
    } catch {
      return sent; // offline or server busy: try again on the next fix
    }
    await d.runAsync(`delete from outbox where id in (${same.map(() => "?").join(",")})`, ...same.map((r) => r.id));
    sent += same.length;
  }
}
