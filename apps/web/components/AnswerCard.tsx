"use client";

/** The navy "VAULTLY ANSWER" card, screen 2c: AI answer, source citations,
 *  and action buttons (create reminder / open document). Plain pending state
 *  while the request is in flight — the assistant API isn't streaming. */

import { useState } from "react";
import Link from "next/link";
import type { AskResponse, SuggestedAction } from "@/lib/assistant";
import { createReminder } from "@/lib/reminders";

function formatDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function ActionButton({ action }: { action: SuggestedAction }) {
  const [state, setState] = useState<"idle" | "saving" | "done" | "error">("idle");

  if (action.type === "open_document") {
    // No per-document detail route exists yet (M8 scope) — land on the
    // documents list, same target CommandK uses for a result click.
    return (
      <Link
        href="/documents"
        className="rounded-control border border-white/25 bg-white/10 px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-white/20"
      >
        {action.label}
      </Link>
    );
  }

  async function handleCreateReminder() {
    if (!action.date) return;
    setState("saving");
    try {
      await createReminder({
        title: action.label,
        due_date: action.date,
        document_id: action.document_id,
      });
      setState("done");
    } catch {
      setState("error");
    }
  }

  if (!action.date) return null;

  return (
    <button
      onClick={handleCreateReminder}
      disabled={state === "saving" || state === "done"}
      className="rounded-control bg-white px-3 py-1.5 text-[12px] font-semibold text-ink hover:bg-white/90 disabled:opacity-70"
    >
      {state === "done" ? (
        "Reminder created ✓"
      ) : state === "saving" ? (
        "Creating…"
      ) : state === "error" ? (
        "Couldn't create — retry"
      ) : (
        <>
          {action.label} · <span className="font-mono">{formatDate(action.date)}</span>
        </>
      )}
    </button>
  );
}

export function AnswerCardLoading() {
  return (
    <div className="mb-[18px] rounded-card bg-ink px-6 py-5 shadow-card">
      <div className="text-[10.5px] font-semibold uppercase tracking-[.1em] text-white/60">
        Vaultly Answer
      </div>
      <div className="mt-2 text-[13.5px] text-white/70">Thinking…</div>
    </div>
  );
}

export function AnswerUpgradeCard({ detail }: { detail: string }) {
  return (
    <div className="mb-[18px] rounded-card border border-dashed border-border bg-card px-6 py-5">
      <div className="text-[10.5px] font-semibold uppercase tracking-[.1em] text-text-faint">
        Vaultly Answer
      </div>
      <div className="mt-2 text-[13.5px] text-text-sub">{detail}</div>
    </div>
  );
}

export function AnswerCard({ data }: { data: AskResponse }) {
  return (
    <div className="mb-[18px] rounded-card bg-ink px-6 py-5 shadow-card">
      <div className="flex items-center justify-between">
        <div className="text-[10.5px] font-semibold uppercase tracking-[.1em] text-white/60">
          Vaultly Answer
        </div>
        <div className="font-mono text-[11px] text-white/50">
          {data.retrieved_count} source{data.retrieved_count === 1 ? "" : "s"}
        </div>
      </div>

      <p className="mt-2.5 text-[14px] leading-relaxed text-white">{data.answer}</p>

      {data.citations.length > 0 && (
        <div className="mt-3.5 flex flex-wrap gap-2">
          {data.citations.map((c) => (
            <Link
              key={c.document_id}
              href={`/documents?category=${encodeURIComponent(c.category)}`}
              className="rounded-tag border border-white/25 bg-white/10 px-[9px] py-1 text-[11.5px] text-white/90 hover:bg-white/20"
            >
              {c.title}
            </Link>
          ))}
        </div>
      )}

      {data.suggested_actions.length > 0 && (
        <div className="mt-3.5 flex flex-wrap gap-2">
          {data.suggested_actions.map((action, i) => (
            <ActionButton key={`${action.type}-${action.document_id}-${i}`} action={action} />
          ))}
        </div>
      )}
    </div>
  );
}
