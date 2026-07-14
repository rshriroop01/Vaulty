"use client";

/** Insurance center — screen 2f: policy cards built from Claude-extracted
 *  insurance documents (provider, policy #, coverage lines, premium, renewal). */

import { useEffect, useState } from "react";
import Link from "next/link";
import { formatMoney, listDocuments, type DocumentItem } from "@/lib/documents";

const TYPE_KEYWORDS: [RegExp, string][] = [
  [/auto|vehicle|car/i, "AUTO"],
  [/home|house|property/i, "HOME"],
  [/health|medic/i, "HLTH"],
  [/life/i, "LIFE"],
  [/rent/i, "RENT"],
  [/travel/i, "TRVL"],
  [/dental/i, "DENT"],
];

function policyType(doc: DocumentItem): string {
  const haystack = `${doc.title} ${doc.extracted?.fields.map((f) => `${f.label} ${f.value}`).join(" ") ?? ""}`;
  for (const [pattern, code] of TYPE_KEYWORDS) {
    if (pattern.test(haystack)) return code;
  }
  return "POL";
}

function policyNumber(doc: DocumentItem): string | null {
  const field = doc.extracted?.fields.find((f) => /policy|number|#/i.test(f.label));
  return field?.value ?? null;
}

function renewalTag(doc: DocumentItem): { label: string; className: string } {
  if (!doc.expiry_date) return { label: "Active", className: "bg-ok-bg text-ok" };
  const days = Math.ceil(
    (new Date(doc.expiry_date + "T00:00:00").getTime() - Date.now()) / 86400000,
  );
  if (days < 0) return { label: "Lapsed", className: "bg-urgent-bg text-urgent" };
  if (days <= 30) return { label: "Renews soon", className: "bg-warn-bg text-warn" };
  return { label: "Active", className: "bg-ok-bg text-ok" };
}

function fmtDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function InsurancePage() {
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);

  useEffect(() => {
    listDocuments("insurance")
      .then(setDocs)
      .catch(() => setDocs([]));
  }, []);

  const policies = docs ?? [];
  const nextRenewal = policies
    .filter((d) => d.expiry_date && new Date(d.expiry_date) >= new Date())
    .sort((a, b) => (a.expiry_date! < b.expiry_date! ? -1 : 1))[0];

  return (
    <>
      <div className="mb-5 flex items-center">
        <div>
          <h1 className="text-[21px] font-semibold tracking-[-0.01em]">Insurance</h1>
          <p className="mt-0.5 text-[13px] text-text-sub">
            {policies.length === 0
              ? "Upload a policy — Vaultly extracts coverage, premiums, and renewal dates."
              : `${policies.length} ${policies.length === 1 ? "policy" : "policies"}${
                  nextRenewal ? ` · next renewal ${fmtDate(nextRenewal.expiry_date!)}` : ""
                }`}
          </p>
        </div>
        <Link
          href="/documents"
          className="ml-auto rounded-[9px] bg-ink px-[18px] py-[11px] text-[13px] font-semibold text-white"
        >
          ＋ Add policy
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {policies.map((doc) => {
          const tag = renewalTag(doc);
          const num = policyNumber(doc);
          const lines = (doc.extracted?.fields ?? [])
            .filter((f) => !/policy|number|#/i.test(f.label))
            .slice(0, 3);
          return (
            <div key={doc.id} className="rounded-[10px] border border-border bg-card p-[18px_20px]">
              <div className="mb-3.5 flex items-center gap-2.5">
                <div className="grid h-[34px] w-[34px] place-items-center rounded-control bg-nav-active font-mono text-[11px] font-semibold text-ink">
                  {policyType(doc)}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-[14.5px] font-semibold">
                    {doc.extracted?.vendor ?? doc.title}
                  </div>
                  {num && <div className="font-mono text-[11.5px] text-text-faint">#{num}</div>}
                </div>
                <span
                  className={`ml-auto rounded-tag px-[9px] py-[3px] text-[11.5px] font-semibold ${tag.className}`}
                >
                  {tag.label}
                </span>
              </div>
              {lines.map((line) => (
                <div
                  key={line.label}
                  className="flex justify-between border-t border-[#f2f4f6] py-[7px] text-[12.5px]"
                >
                  <span className="text-text-sub">{line.label}</span>
                  <span className="max-w-[60%] truncate text-right font-medium">{line.value}</span>
                </div>
              ))}
              <div className="mt-3 flex items-center justify-between border-t border-hairline pt-3">
                <div>
                  {doc.extracted?.amount != null ? (
                    <span className="font-mono text-[16px] font-semibold">
                      {formatMoney(doc.extracted.amount, doc.extracted.currency)}
                    </span>
                  ) : (
                    <span className="text-[12.5px] text-text-faint">premium not detected</span>
                  )}
                  {doc.expiry_date && (
                    <span className="text-[11.5px] text-text-faint">
                      {" "}
                      · renews {fmtDate(doc.expiry_date)}
                    </span>
                  )}
                </div>
                <Link
                  href="/documents?category=insurance"
                  className="text-[12px] font-medium text-link"
                >
                  View document
                </Link>
              </div>
            </div>
          );
        })}

        <Link
          href="/documents"
          className="grid min-h-[220px] place-items-center rounded-[10px] border-[1.5px] border-dashed border-[#c8cfd7] hover:border-ink"
        >
          <div className="text-center">
            <div className="mx-auto mb-2.5 grid h-[38px] w-[38px] place-items-center rounded-[9px] bg-nav-active font-mono text-[16px] font-semibold text-ink">
              ＋
            </div>
            <div className="text-[13.5px] font-semibold">
              {policies.length === 0 ? "Add your first policy" : "Add life / umbrella / renters"}
            </div>
            <div className="mt-[3px] text-[12px] text-text-faint">
              Upload the policy — we extract the rest
            </div>
          </div>
        </Link>
      </div>
    </>
  );
}
