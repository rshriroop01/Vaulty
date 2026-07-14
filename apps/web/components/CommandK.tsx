"use client";

/** Global ⌘K search overlay — reachable from anywhere in the app (design rule:
 *  any item ≤3 clicks from dashboard). TopBar's ask bar opens it too via the
 *  `vaultly:open-search` event. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { searchDocuments, type SearchResponse } from "@/lib/search";
import { categoryLabel } from "@/lib/categories";
import { Mark } from "@/components/Mark";

export function CommandK() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    function onOpenEvent() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("vaultly:open-search", onOpenEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("vaultly:open-search", onOpenEvent);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 30);
    } else {
      setQ("");
      setResponse(null);
    }
  }, [open]);

  const runSearch = useCallback((value: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (!value.trim()) {
      setResponse(null);
      return;
    }
    debounce.current = setTimeout(() => {
      searchDocuments(value)
        .then(setResponse)
        .catch(() => setResponse(null));
    }, 200);
  }, []);

  function goToFullSearch() {
    if (!q.trim()) return;
    setOpen(false);
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-[rgba(22,50,79,0.35)]"
      onClick={() => setOpen(false)}
      data-testid="cmdk-overlay"
    >
      <div
        className="mx-auto mt-[12vh] w-[640px] max-w-[92vw] overflow-hidden rounded-xl bg-card shadow-[0_12px_40px_rgba(22,50,79,0.25)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-hairline px-4 py-3">
          <span className="h-3.5 w-3.5 flex-none rounded-full border-2 border-ink" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              runSearch(e.target.value);
            }}
            onKeyDown={(e) => e.key === "Enter" && goToFullSearch()}
            placeholder="Ask Vaultly — “which warranties expire next month?”"
            className="flex-1 bg-transparent text-[14px] font-medium outline-none placeholder:text-text-faint"
          />
          {response && (
            <span className="font-mono text-[11px] text-text-faint">
              {(response.latency_ms / 1000).toFixed(2)}s
            </span>
          )}
        </div>

        {response && response.results.length > 0 && (
          <div className="max-h-[360px] overflow-y-auto">
            {response.results.slice(0, 8).map((r) => (
              <button
                key={r.id}
                onClick={() => {
                  setOpen(false);
                  router.push("/documents");
                }}
                className="flex w-full items-center gap-3 border-b border-hairline px-4 py-2.5 text-left hover:bg-[#f8fafc]"
              >
                <div className="grid h-9 w-[30px] flex-none place-items-center rounded-[4px] border border-border bg-app font-mono text-[8.5px] font-semibold text-text-faint">
                  {(r.file_name.split(".").pop() ?? "").toUpperCase().slice(0, 4)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] font-semibold text-ink">
                    <Mark text={r.title} q={q} />
                  </div>
                  <div className="truncate text-[12px] text-text-sub">
                    <Mark text={r.snippet} q={q} />
                  </div>
                </div>
                <span className="rounded-tag border border-hairline bg-app px-2 py-[2px] text-[11px]">
                  {categoryLabel(r.category)}
                </span>
              </button>
            ))}
          </div>
        )}
        {response && response.results.length === 0 && (
          <div className="px-4 py-6 text-center text-[12.5px] text-text-sub">
            Nothing found for “{q}”.
          </div>
        )}

        <div className="flex items-center justify-between bg-app px-4 py-2 text-[11px] text-text-faint">
          <span>
            <span className="font-mono">↵</span> full results ·{" "}
            <span className="font-mono">esc</span> close
          </span>
          <span className="font-mono">⌘K</span>
        </div>
      </div>
    </div>
  );
}
