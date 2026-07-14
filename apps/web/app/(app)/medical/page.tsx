"use client";

/** Medical bills — screen 2g: summary stats + claims table. Status cycles
 *  outstanding → pending → paid on click and persists via PATCH. */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  downloadDocument,
  formatMoney,
  listDocuments,
  patchDocument,
  type DocumentItem,
} from "@/lib/documents";

const CYCLE: Record<string, string> = {
  outstanding: "pending",
  pending: "paid",
  paid: "outstanding",
};

const STATUS_STYLE: Record<string, { label: string; className: string }> = {
  outstanding: { label: "Outstanding", className: "bg-urgent-bg text-urgent" },
  pending: { label: "Claim pending", className: "bg-warn-bg text-warn" },
  paid: { label: "Paid", className: "bg-ok-bg text-ok" },
};

const status = (d: DocumentItem) => d.bill_status ?? "outstanding";

function sumByCurrency(bills: DocumentItem[]): string {
  const sums = new Map<string, number>();
  for (const b of bills) {
    if (b.extracted?.amount == null) continue;
    const cur = b.extracted.currency ?? "";
    sums.set(cur, (sums.get(cur) ?? 0) + b.extracted.amount);
  }
  if (sums.size === 0) return "—";
  return [...sums.entries()].map(([cur, total]) => formatMoney(total, cur || null)).join(" + ");
}

function mono(dateIso: string | null): string {
  if (!dateIso) return "—";
  return new Date(dateIso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
  });
}

export default function MedicalPage() {
  const [bills, setBills] = useState<DocumentItem[] | null>(null);

  useEffect(() => {
    listDocuments("medical")
      .then(setBills)
      .catch(() => setBills([]));
  }, []);

  async function cycleStatus(bill: DocumentItem) {
    const next = CYCLE[status(bill)];
    setBills((prev) =>
      (prev ?? []).map((b) => (b.id === bill.id ? { ...b, bill_status: next } : b)),
    );
    await patchDocument(bill.id, { bill_status: next }).catch(() => {
      setBills((prev) =>
        (prev ?? []).map((b) => (b.id === bill.id ? { ...b, bill_status: bill.bill_status } : b)),
      );
    });
  }

  const list = bills ?? [];
  const outstanding = list.filter((b) => status(b) === "outstanding");
  const pending = list.filter((b) => status(b) === "pending");
  const paidThisYear = list.filter(
    (b) =>
      status(b) === "paid" &&
      b.extracted?.document_date?.startsWith(String(new Date().getFullYear())),
  );

  return (
    <>
      <div className="mb-5 flex items-center">
        <div>
          <h1 className="text-[21px] font-semibold tracking-[-0.01em]">Medical bills</h1>
          <p className="mt-0.5 text-[13px] text-text-sub">
            Bills and EOBs extracted automatically from uploads. Click a status to update it.
          </p>
        </div>
        <Link
          href="/documents"
          className="ml-auto rounded-[9px] bg-ink px-[18px] py-[11px] text-[13px] font-semibold text-white"
        >
          ＋ Add bill
        </Link>
      </div>

      <div className="mb-[18px] grid grid-cols-3 gap-3.5">
        <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
          <div className="mb-2 text-[12px] text-text-sub">Outstanding</div>
          <div className="font-mono text-[26px] font-semibold text-urgent">
            {sumByCurrency(outstanding)}
          </div>
        </div>
        <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
          <div className="mb-2 text-[12px] text-text-sub">Claims pending</div>
          <div className="font-mono text-[26px] font-semibold">{pending.length}</div>
        </div>
        <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
          <div className="mb-2 text-[12px] text-text-sub">Paid this year</div>
          <div className="font-mono text-[26px] font-semibold text-ok">
            {sumByCurrency(paidThisYear)}
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-[10px] border border-border bg-card">
        <div className="grid grid-cols-[1.4fr_90px_110px_150px_90px_80px] border-b border-hairline px-5 py-2.5 font-mono text-[10px] font-semibold uppercase tracking-[.1em] text-text-faint">
          <span>Provider</span>
          <span>Date</span>
          <span>Amount</span>
          <span>Insurance</span>
          <span>Due</span>
          <span>Action</span>
        </div>
        {bills === null ? (
          <div className="space-y-2 p-5">
            {[0, 1].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-control bg-hairline" />
            ))}
          </div>
        ) : list.length === 0 ? (
          <div className="m-4 rounded-control border border-dashed border-border px-4 py-6 text-center text-[12.5px] text-text-sub">
            No medical bills yet — upload one and Vaultly extracts provider, amount, and due date.
          </div>
        ) : (
          list.map((bill) => {
            const s = STATUS_STYLE[status(bill)];
            return (
              <div
                key={bill.id}
                className="grid grid-cols-[1.4fr_90px_110px_150px_90px_80px] items-center border-b border-[#f4f6f8] px-5 py-[13px] text-[13px] last:border-b-0"
              >
                <span className="truncate pr-3 font-medium">
                  {bill.extracted?.vendor ?? bill.title}
                </span>
                <span className="font-mono text-[12px] text-text-sub">
                  {mono(bill.extracted?.document_date ?? null)}
                </span>
                <span className="font-mono text-[12.5px] font-medium">
                  {bill.extracted?.amount != null
                    ? formatMoney(bill.extracted.amount, bill.extracted.currency)
                    : "—"}
                </span>
                <span>
                  <button
                    onClick={() => void cycleStatus(bill)}
                    title="Click to change status"
                    className={`rounded-[4px] px-[9px] py-[3px] text-[11px] font-semibold ${s.className}`}
                  >
                    {s.label}
                  </button>
                </span>
                <span className="font-mono text-[12px] text-text-sub">
                  {mono(bill.expiry_date)}
                </span>
                <button
                  onClick={() =>
                    void downloadDocument(bill.id).then((url) => window.open(url, "_blank"))
                  }
                  className="text-left text-[12px] font-semibold text-link"
                >
                  Download
                </button>
              </div>
            );
          })
        )}
      </div>

      <p className="mt-3 text-[12px] text-text-faint">
        Tip: the email-in address (arrives with Gmail sync, V2) will match bills and EOBs by
        provider + amount automatically.
      </p>
    </>
  );
}
