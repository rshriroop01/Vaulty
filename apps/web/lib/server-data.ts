import { cookies } from "next/headers";
import { API_BASE_URL } from "@/lib/api";
import type { DocumentItem, VaultUsage } from "@/lib/documents";

const INTERNAL_API_URL = process.env.API_URL_INTERNAL ?? API_BASE_URL;

async function serverGet<T>(path: string): Promise<T | null> {
  const cookieStore = await cookies();
  try {
    const res = await fetch(`${INTERNAL_API_URL}${path}`, {
      headers: { cookie: cookieStore.toString() },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const getUsageServer = () => serverGet<VaultUsage>("/api/v1/vault/usage");
export const getDocumentsServer = () => serverGet<DocumentItem[]>("/api/v1/documents");

export const getRemindersServer = () =>
  serverGet<import("@/lib/reminders").Reminder[]>("/api/v1/reminders");
export const getReminderStatsServer = () =>
  serverGet<import("@/lib/reminders").ReminderStats>("/api/v1/reminders/stats");
