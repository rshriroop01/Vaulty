import { ApiError, apiFetch } from "@/lib/api";

export type Citation = {
  document_id: string;
  title: string;
  category: string;
};

export type SuggestedAction = {
  type: "create_reminder" | "open_document";
  document_id: string;
  label: string;
  date: string | null;
};

export type AskResponse = {
  answer: string;
  citations: Citation[];
  suggested_actions: SuggestedAction[];
  retrieved_count: number;
  latency_ms: number;
};

const PLAN_UPGRADE_TYPE_SUFFIX = "/plan-upgrade-required";

/** Distinguishable outcomes the search page needs to render differently:
 *  a real answer, a Premium upsell, or "say nothing" (flag off / no key). */
export type AskOutcome =
  | { kind: "answer"; data: AskResponse }
  | { kind: "upgrade"; detail: string }
  | { kind: "unavailable" };

export function askAssistant(question: string): Promise<AskResponse> {
  return apiFetch<AskResponse>("/api/v1/assistant/ask", {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({ question }),
  });
}

/** Wraps askAssistant so the caller can render three states without a
 *  try/catch of its own — 403 plan-upgrade becomes an upsell, every other
 *  gate (flag off, 503 no key) becomes "render nothing", search stays
 *  unaffected either way. */
export async function askAssistantOutcome(question: string): Promise<AskOutcome> {
  try {
    const data = await askAssistant(question);
    return { kind: "answer", data };
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 403 && err.type?.endsWith(PLAN_UPGRADE_TYPE_SUFFIX)) {
        return { kind: "upgrade", detail: err.message };
      }
      // 403 (flag off) or 503 (no key): assistant just stays quiet.
      return { kind: "unavailable" };
    }
    return { kind: "unavailable" };
  }
}
