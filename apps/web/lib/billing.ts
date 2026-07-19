import { ApiError, apiFetch } from "@/lib/api";

export type Plan = "free" | "premium" | "family";

export type BillingSummary = {
  plan: Plan;
  status: string | null;
  member_count: number;
  document_count: number;
  storage_bytes: number;
  document_limit: number | null;
  storage_limit_bytes: number | null;
  current_period_end: string | null;
};

const withCreds: RequestInit = { credentials: "include" };
const post = (body?: unknown): RequestInit => ({
  method: "POST",
  ...withCreds,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const getBillingSummary = () =>
  apiFetch<BillingSummary>("/api/v1/billing/summary", withCreds);

export const startCheckout = (plan: "premium" | "family") =>
  apiFetch<{ url: string }>("/api/v1/billing/checkout", post({ plan }));

export const openPortal = () => apiFetch<{ url: string }>("/api/v1/billing/portal", post());

/** Distinguishable outcomes the billing page needs to render differently:
 *  a real summary, or "billing isn't set up in this environment" (503, no
 *  Stripe keys — mirrors lib/assistant.ts's AskOutcome pattern). */
export type BillingSummaryOutcome =
  { kind: "ready"; data: BillingSummary } | { kind: "unconfigured" };

export async function getBillingSummaryOutcome(): Promise<BillingSummaryOutcome> {
  try {
    const data = await getBillingSummary();
    return { kind: "ready", data };
  } catch (err) {
    if (err instanceof ApiError && err.status === 503) {
      return { kind: "unconfigured" };
    }
    throw err;
  }
}
