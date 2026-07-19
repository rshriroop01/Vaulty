"use client";

/** Billing — M9. No approved design screen for this exists (docs/design
 *  handoff covers 2a–2k only), so this is composed conservatively from the
 *  Ledger system's existing card/tag/button patterns (see insurance and
 *  family pages) — same tokens, IBM Plex Mono for every price/date/number. */

import { useEffect, useState } from "react";
import { formatBytes } from "@/lib/categories";
import {
  getBillingSummaryOutcome,
  openPortal,
  startCheckout,
  type BillingSummary,
  type Plan,
} from "@/lib/billing";
import { ApiError } from "@/lib/api";
import { getMembers } from "@/lib/family";

type PlanCard = {
  id: Plan;
  name: string;
  price: string;
  cadence: string;
  bullets: string[];
};

const PLANS: PlanCard[] = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    cadence: "/mo",
    bullets: ["100MB storage", "25 documents", "OCR on 5 documents/month", "Basic reminders"],
  },
  {
    id: "premium",
    name: "Premium",
    price: "$8.99",
    cadence: "/mo",
    bullets: [
      "Unlimited OCR",
      "AI assistant",
      "Unlimited reminders",
      "Gmail sync",
      "Unlimited storage",
    ],
  },
  {
    id: "family",
    name: "Family",
    price: "$14.99",
    cadence: "/mo",
    bullets: [
      "Up to 6 members",
      "Shared vault",
      "Shared reminders",
      "Emergency access",
      "Family dashboard",
    ],
  },
];

const PLAN_LABEL: Record<string, string> = { free: "Free", premium: "Premium", family: "Family" };
const STATUS_TAG: Record<string, { label: string; className: string }> = {
  active: { label: "Active", className: "bg-ok-bg text-ok" },
  past_due: { label: "Payment failed", className: "bg-urgent-bg text-urgent" },
  canceled: { label: "Canceled", className: "bg-nav-active text-text-sub" },
};

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function BillingPage() {
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [unconfigured, setUnconfigured] = useState(false);
  const [isOwner, setIsOwner] = useState(true);
  const [busy, setBusy] = useState<Plan | "portal" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBillingSummaryOutcome()
      .then((outcome) => {
        if (outcome.kind === "unconfigured") {
          setUnconfigured(true);
        } else {
          setSummary(outcome.data);
        }
      })
      .catch(() => setUnconfigured(true));
    // No role field on the billing summary — reuse the members list (already
    // includes is_me/role, same trick app/(app)/family/page.tsx uses) so the
    // owner-only actions can be disabled up front instead of only on a 403.
    getMembers()
      .then((data) => {
        const me = data.members.find((m) => m.is_me);
        setIsOwner(me?.role === "owner");
      })
      .catch(() => {});
  }, []);

  async function onUpgrade(plan: "premium" | "family") {
    setError(null);
    setBusy(plan);
    try {
      const { url } = await startCheckout(plan);
      window.location.assign(url);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setIsOwner(false);
        setError("Only the vault owner can change plans.");
      } else {
        setError(e instanceof Error ? e.message : "Could not start checkout");
      }
      setBusy(null);
    }
  }

  async function onManageBilling() {
    setError(null);
    setBusy("portal");
    try {
      const { url } = await openPortal();
      window.location.assign(url);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setIsOwner(false);
        setError("Only the vault owner can manage billing.");
      } else if (e instanceof ApiError && e.status === 404) {
        setError("No billing account yet — upgrade a plan first.");
      } else {
        setError(e instanceof Error ? e.message : "Could not open the billing portal");
      }
      setBusy(null);
    }
  }

  if (unconfigured) {
    return (
      <>
        <div className="mb-5">
          <h1 className="text-[21px] font-semibold tracking-[-0.01em]">Billing</h1>
        </div>
        <div className="rounded-[10px] border border-dashed border-border bg-card px-6 py-8 text-center">
          <div className="text-[13.5px] font-medium text-text-sub">Billing not configured</div>
          <p className="mx-auto mt-1.5 max-w-[420px] text-[12.5px] text-text-faint">
            This environment doesn&apos;t have Stripe keys set up, so plans can&apos;t be changed
            here yet.
          </p>
        </div>
      </>
    );
  }

  const currentPlan = summary?.plan ?? "free";
  const status = summary?.status ? STATUS_TAG[summary.status] : null;

  return (
    <>
      <div className="mb-5 flex items-center">
        <div>
          <h1 className="text-[21px] font-semibold tracking-[-0.01em]">Billing</h1>
          <p className="mt-0.5 text-[13px] text-text-sub">
            {summary
              ? `${PLAN_LABEL[currentPlan]} plan · ${summary.member_count} member${summary.member_count === 1 ? "" : "s"}`
              : "Loading…"}
          </p>
        </div>
        {summary && summary.plan !== "free" && (
          <button
            onClick={onManageBilling}
            disabled={busy !== null || !isOwner}
            title={isOwner ? undefined : "Only the vault owner can manage billing"}
            className="ml-auto rounded-[9px] border border-input-border bg-card px-[18px] py-[11px] text-[13px] font-semibold text-ink disabled:opacity-50"
          >
            {busy === "portal" ? "Opening…" : "Manage billing"}
          </button>
        )}
      </div>

      {error && (
        <div className="mb-3 rounded-tag bg-urgent-bg px-3 py-2 text-[12px] font-medium text-urgent">
          {error}
        </div>
      )}

      {summary && (
        <div className="mb-4 rounded-[10px] border border-border bg-card px-[18px] py-4">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12.5px]">
            <div>
              <span className="text-text-sub">Documents </span>
              <span className="font-mono font-medium">
                {summary.document_count}
                {summary.document_limit != null ? ` / ${summary.document_limit}` : ""}
              </span>
            </div>
            <div>
              <span className="text-text-sub">Storage </span>
              <span className="font-mono font-medium">
                {formatBytes(summary.storage_bytes)}
                {summary.storage_limit_bytes != null
                  ? ` / ${formatBytes(summary.storage_limit_bytes)}`
                  : ""}
              </span>
            </div>
            <div>
              <span className="text-text-sub">Members </span>
              <span className="font-mono font-medium">{summary.member_count} / 6</span>
            </div>
            {status && (
              <span
                className={`rounded-tag px-[9px] py-[3px] text-[11.5px] font-semibold ${status.className}`}
              >
                {status.label}
              </span>
            )}
            {summary.current_period_end && (
              <div>
                <span className="text-text-sub">Renews </span>
                <span className="font-mono font-medium">{fmtDate(summary.current_period_end)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {PLANS.map((plan) => {
          const isCurrent = plan.id === currentPlan;
          const canUpgrade = plan.id !== "free" && !isCurrent;
          return (
            <div
              key={plan.id}
              className={`rounded-[10px] border bg-card p-[18px_20px] ${
                isCurrent ? "border-[1.5px] border-ink" : "border-border"
              }`}
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[14.5px] font-semibold">{plan.name}</span>
                {isCurrent && (
                  <span className="rounded-tag bg-nav-active px-[9px] py-[3px] text-[11.5px] font-semibold text-ink">
                    Current plan
                  </span>
                )}
              </div>
              <div className="mb-3.5">
                <span className="font-mono text-[22px] font-semibold">{plan.price}</span>
                <span className="text-[12.5px] text-text-sub">{plan.cadence}</span>
              </div>
              <ul className="mb-4 space-y-1.5">
                {plan.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-1.5 text-[12.5px] text-text-sub">
                    <span className="mt-[1px] text-ok">✓</span>
                    {b}
                  </li>
                ))}
              </ul>
              {canUpgrade ? (
                <button
                  onClick={() => onUpgrade(plan.id as "premium" | "family")}
                  disabled={busy !== null || !isOwner}
                  title={isOwner ? undefined : "Only the vault owner can change plans"}
                  className="w-full rounded-control bg-ink px-4 py-[10px] text-[13px] font-semibold text-white disabled:opacity-50"
                >
                  {busy === plan.id ? "Redirecting…" : `Upgrade to ${plan.name}`}
                </button>
              ) : isCurrent ? (
                <div className="text-center text-[12px] text-text-faint">
                  You&apos;re on this plan
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {!isOwner && (
        <p className="mt-3 text-[12px] text-text-faint">
          Only the vault owner can upgrade the plan or manage billing.
        </p>
      )}
    </>
  );
}
