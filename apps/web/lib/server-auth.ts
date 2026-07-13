import { cookies } from "next/headers";
import { API_BASE_URL } from "@/lib/api";
import type { Me } from "@/lib/types";

// Server-side fetches run inside the web container/process, where the API may be
// reachable at a different host (http://api:8000 in Docker) than from the browser.
const INTERNAL_API_URL = process.env.API_URL_INTERNAL ?? API_BASE_URL;

/** Server-side session lookup — forwards the browser's cookies to the API. */
export async function getMe(): Promise<Me | null> {
  const cookieStore = await cookies();
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/me`, {
      headers: { cookie: cookieStore.toString() },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Me;
  } catch {
    return null;
  }
}
