"use client";

/** Documents — screen 2b: dropzone, processing queue, right rail.
 *  OCR/extraction states arrive with M3; today the queue shows real upload progress. */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteDocument,
  downloadDocument,
  listDocuments,
  uploadFile,
  type DocumentItem,
} from "@/lib/documents";
import { categoryLabel, formatBytes } from "@/lib/categories";
import { createReminder } from "@/lib/reminders";

type QueueEntry = {
  key: string;
  name: string;
  pct: number;
  state: "Uploading" | "Uploaded" | "Failed";
  error?: string;
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  queued: "Queued",
  processing: "Analyzing…",
  extracted: "Extracted",
  failed: "Failed",
};

function StateTag({ state }: { state: QueueEntry["state"] | string }) {
  const label = STATUS_LABELS[state] ?? state;
  const styles =
    state === "Failed" || state === "failed"
      ? "bg-urgent-bg text-urgent"
      : state === "Uploading" || state === "queued" || state === "processing"
        ? "bg-warn-bg text-warn"
        : "bg-ok-bg text-ok";
  return (
    <span
      className={`whitespace-nowrap rounded-tag px-[9px] py-[3px] text-[11.5px] font-semibold ${styles}`}
    >
      {label}
    </span>
  );
}

const ACTIVE_STATES = new Set(["queued", "processing"]);

function formatDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Extracted-field chips + warranty suggestion banner, per design 2b. */
function ExtractionDetails({ doc }: { doc: DocumentItem }) {
  const [dismissed, setDismissed] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  if (doc.status !== "extracted" || !doc.extracted) return null;

  const chips: { label: string; value: string }[] = [];
  if (doc.extracted.vendor) chips.push({ label: "Vendor", value: doc.extracted.vendor });
  if (doc.extracted.amount != null)
    chips.push({
      label: "Amount",
      value: `${doc.extracted.currency ?? ""} ${doc.extracted.amount.toFixed(2)}`.trim(),
    });
  if (doc.extracted.document_date)
    chips.push({ label: "Date", value: formatDate(doc.extracted.document_date) });
  if (doc.extracted.expiry_date)
    chips.push({ label: "Expires", value: formatDate(doc.extracted.expiry_date) });
  chips.push(...doc.extracted.fields);

  // The design's canonical case is a warranty detected on a *receipt* (screen 2b)
  const suggestExpiry =
    !dismissed && doc.expiry_date && ["receipts", "warranties", "insurance"].includes(doc.category);

  return (
    <div className="ml-[42px]">
      {chips.length > 0 && (
        <div className="mt-[11px] flex flex-wrap gap-2">
          {chips.slice(0, 6).map((f, i) => (
            <span
              key={`${f.label}-${i}`}
              className="rounded-tag border border-border bg-app px-[9px] py-1 text-[11.5px]"
            >
              <span className="text-text-faint">{f.label}</span>{" "}
              <strong className="font-semibold">{f.value}</strong>
            </span>
          ))}
        </div>
      )}
      {suggestExpiry && (
        <div className="mt-[11px] flex items-center gap-3 rounded-control bg-nav-active px-3.5 py-2.5">
          <span className="flex-1 text-[12.5px] text-ink">
            {doc.category === "insurance" ? "Policy" : "Warranty"} until{" "}
            {formatDate(doc.expiry_date!)} detected. Create{" "}
            {doc.category === "insurance" ? "policy record" : "warranty record"} + expiry reminder?
          </span>
          <button
            onClick={async () => {
              try {
                await createReminder({
                  title: `${doc.title} — ${doc.category === "insurance" ? "policy renews" : "warranty expires"}`,
                  due_date: doc.expiry_date!,
                  document_id: doc.id,
                });
                setNote(
                  `Reminder set — you'll get emails 30, 7, and 1 day before ${formatDate(doc.expiry_date!)}.`,
                );
                setDismissed(true);
              } catch {
                setNote("Could not create the reminder — try again.");
              }
            }}
            className="whitespace-nowrap rounded-[6px] bg-ink px-3 py-1.5 text-[12px] font-semibold text-white"
          >
            Create both
          </button>
          <button
            onClick={() => setDismissed(true)}
            className="whitespace-nowrap text-[12px] font-semibold text-[#4c5561]"
          >
            Dismiss
          </button>
        </div>
      )}
      {note && <div className="mt-1.5 text-[11.5px] text-ok">{note}</div>}
    </div>
  );
}

function FileGlyph({ name }: { name: string }) {
  const ext = (name.split(".").pop() ?? "").toUpperCase().slice(0, 4);
  return (
    <div className="grid h-9 w-[30px] flex-none place-items-center rounded-[4px] border border-border bg-app font-mono text-[8.5px] font-semibold text-text-faint">
      {ext}
    </div>
  );
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setDocs(await listDocuments().catch(() => []));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll while any document is queued/processing so extraction states appear live
  useEffect(() => {
    if (!docs?.some((d) => ACTIVE_STATES.has(d.status))) return;
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [docs, refresh]);

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      for (const file of Array.from(files)) {
        const key = `${file.name}-${Date.now()}-${Math.random()}`;
        setQueue((q) => [{ key, name: file.name, pct: 0, state: "Uploading" }, ...q]);
        uploadFile(file, (pct) =>
          setQueue((q) => q.map((e) => (e.key === key ? { ...e, pct } : e))),
        )
          .then(() => {
            setQueue((q) =>
              q.map((e) => (e.key === key ? { ...e, pct: 100, state: "Uploaded" } : e)),
            );
            void refresh();
          })
          .catch((err: Error) => {
            setQueue((q) =>
              q.map((e) => (e.key === key ? { ...e, state: "Failed", error: err.message } : e)),
            );
          });
      }
    },
    [refresh],
  );

  async function onDownload(id: string) {
    const url = await downloadDocument(id);
    window.open(url, "_blank");
  }

  async function onDelete(id: string) {
    await deleteDocument(id);
    void refresh();
  }

  return (
    <>
      <h1 className="mb-0.5 text-[21px] font-semibold tracking-[-0.01em]">Add documents</h1>
      <p className="mb-5 text-[13px] text-text-sub">
        Drop files, forward email, or scan from your phone — Vaultly files them for you.
      </p>
      <div className="grid grid-cols-[1.6fr_1fr] items-start gap-4">
        <div className="grid gap-4">
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInput.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && fileInput.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFiles(e.dataTransfer.files);
            }}
            data-testid="dropzone"
            className={`cursor-pointer rounded-xl border-[1.5px] border-dashed bg-card p-[38px] text-center transition-colors ${
              dragOver ? "border-ink bg-nav-active" : "border-[#b7c2cc]"
            }`}
          >
            <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-[10px] bg-nav-active font-mono text-[18px] font-semibold text-ink">
              ↑
            </div>
            <div className="text-[14.5px] font-semibold">Drag &amp; drop files here</div>
            <div className="mt-1 text-[12.5px] text-text-sub">
              PDF, JPG, PNG, HEIC · up to 25 MB each · or{" "}
              <span className="font-medium text-link">browse</span>
            </div>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.heic,.webp"
              className="hidden"
              onChange={(e) => e.target.files && handleFiles(e.target.files)}
            />
          </div>

          {queue.length > 0 && (
            <div className="overflow-hidden rounded-[10px] border border-border bg-card">
              <div className="px-[18px] pb-[11px] pt-3.5 text-[14px] font-semibold">
                Processing queue
              </div>
              {queue.map((e) => (
                <div key={e.key} className="border-t border-hairline px-[18px] py-[13px]">
                  <div className="flex items-center gap-3">
                    <FileGlyph name={e.name} />
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-[13px] font-medium">{e.name}</div>
                      <div className="mt-[7px] h-1 rounded-[2px] bg-hairline">
                        <div
                          className={`h-1 rounded-[2px] ${e.state === "Failed" ? "bg-urgent" : "bg-ink"}`}
                          style={{ width: `${e.pct}%` }}
                        />
                      </div>
                      {e.error && <div className="mt-1 text-[11.5px] text-urgent">{e.error}</div>}
                    </div>
                    <StateTag state={e.state} />
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="overflow-hidden rounded-[10px] border border-border bg-card">
            <div className="flex items-baseline justify-between px-[18px] pb-[11px] pt-3.5">
              <span className="text-[14px] font-semibold">Documents</span>
              <span className="font-mono text-[11.5px] text-text-faint">
                {docs?.length ?? 0} total
              </span>
            </div>
            {docs === null ? (
              <div className="space-y-2 px-[18px] pb-4">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-10 animate-pulse rounded-control bg-hairline" />
                ))}
              </div>
            ) : docs.length === 0 ? (
              <div className="m-[0_18px_16px] rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
                Nothing here yet — your first upload appears in this list.
              </div>
            ) : (
              docs.map((d) => (
                <div
                  key={d.id}
                  className="border-t border-hairline px-[18px] py-3 hover:bg-[#f8fafc]"
                >
                  <div className="flex items-center gap-3">
                    <FileGlyph name={d.file_name} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-medium">{d.title}</div>
                      <div className="mt-0.5 font-mono text-[11px] text-text-faint">
                        {formatBytes(d.size_bytes)} ·{" "}
                        {new Date(d.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </div>
                    </div>
                    <span className="rounded-tag border border-hairline bg-app px-[9px] py-[3px] text-[11.5px]">
                      {categoryLabel(d.category)}
                    </span>
                    <StateTag state={d.status} />
                    <button
                      onClick={() => void onDownload(d.id)}
                      className="rounded-[6px] border border-input-border px-3 py-1.5 text-[12px] font-semibold text-ink hover:bg-app"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => void onDelete(d.id)}
                      className="rounded-[6px] px-2 py-1.5 text-[12px] font-semibold text-urgent hover:bg-urgent-bg"
                    >
                      Delete
                    </button>
                  </div>
                  <ExtractionDetails doc={d} />
                </div>
              ))
            )}
          </div>
        </div>

        <div className="grid gap-4">
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[14px] font-semibold">Gmail sync</span>
              <span className="relative inline-block h-5 w-[34px] rounded-[10px] bg-[#e6eaee]">
                <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm" />
              </span>
            </div>
            <div className="text-[12.5px] leading-[1.55] text-text-sub">
              Receipts and bills detected in your inbox, filed automatically. Arrives in V2 —
              pending Google verification.
            </div>
          </div>
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-1 text-[14px] font-semibold">Email-in address</div>
            <div className="rounded-[6px] border border-border bg-app px-2.5 py-2 font-mono text-[12px] text-[#4c5561]">
              coming with reminders (M5)
            </div>
            <div className="mt-2 text-[12px] text-text-faint">
              Forward any receipt or bill — it lands in your vault.
            </div>
          </div>
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-1 text-[14px] font-semibold">Scan with phone</div>
            <div className="text-[12.5px] leading-[1.55] text-text-sub">
              Point your camera at a paper document — cropped, enhanced, and OCR&apos;d on upload.
              Arrives with mobile (V3).
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
