"use client";

/** Search results — screen 2c: focused query bar with latency, filter chips,
 *  ranked results with highlighted snippets and relevance scores.
 *  The navy "VAULTLY ANSWER" card arrives with the AI assistant (M8). */

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { searchDocuments, type SearchResponse } from "@/lib/search";
import { CATEGORIES, categoryLabel, formatBytes } from "@/lib/categories";
import { Mark } from "@/components/Mark";

function SearchPageInner() {
  const params = useSearchParams();
  const initialQ = params.get("q") ?? "";
  const [q, setQ] = useState(initialQ);
  const [submitted, setSubmitted] = useState(initialQ);
  const [category, setCategory] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (query: string, cat: string | null) => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      setResponse(await searchDocuments(query, cat ?? undefined));
    } catch {
      setResponse(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialQ) void run(initialQ, null);
  }, [initialQ, run]);

  const chips = response ? CATEGORIES.filter((c) => (response.counts[c.key] ?? 0) > 0) : [];

  return (
    <>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(q);
          setCategory(null);
          void run(q, null);
        }}
        className="mb-[18px] flex items-center gap-2.5 rounded-[9px] border-[1.5px] border-ink bg-card px-4 py-3 shadow-[0_1px_3px_rgba(22,50,79,.08)]"
      >
        <span className="h-3.5 w-3.5 flex-none rounded-full border-2 border-ink" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search your vault…"
          className="flex-1 bg-transparent text-[14px] font-medium outline-none placeholder:text-text-faint"
        />
        {response && !loading && (
          <span className="font-mono text-[11px] text-text-faint">
            {(response.latency_ms / 1000).toFixed(2)}s
          </span>
        )}
      </form>

      {response && (
        <div className="mb-3.5 flex flex-wrap gap-2">
          <button
            onClick={() => {
              setCategory(null);
              void run(submitted, null);
            }}
            className={`rounded-[6px] px-[13px] py-1.5 text-[12px] font-semibold ${
              category === null
                ? "bg-ink text-white"
                : "border border-border bg-card text-[#4c5561]"
            }`}
          >
            All ({response.total})
          </button>
          {chips.map((c) => (
            <button
              key={c.key}
              onClick={() => {
                setCategory(c.key);
                void run(submitted, c.key);
              }}
              className={`rounded-[6px] px-[13px] py-1.5 text-[12px] ${
                category === c.key
                  ? "bg-ink font-semibold text-white"
                  : "border border-border bg-card font-medium text-[#4c5561]"
              }`}
            >
              {c.label} ({response.counts[c.key]})
            </button>
          ))}
          <span className="rounded-[6px] border border-border bg-card px-[13px] py-1.5 text-[12px] font-medium text-text-faint">
            Date · any
          </span>
          <span className="rounded-[6px] border border-border bg-card px-[13px] py-1.5 text-[12px] font-medium text-text-faint">
            Owner · anyone
          </span>
        </div>
      )}

      {response && response.results.length > 0 && (
        <div className="overflow-hidden rounded-[10px] border border-border bg-card">
          {response.results.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3.5 border-b border-hairline px-5 py-3.5 last:border-b-0 hover:bg-[#f8fafc]"
            >
              <div className="grid h-[42px] w-[34px] flex-none place-items-center rounded-[4px] border border-border bg-app font-mono text-[9px] font-semibold text-text-faint">
                {(r.file_name.split(".").pop() ?? "").toUpperCase().slice(0, 4)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-semibold text-ink">
                  <Mark text={r.title} q={submitted} />
                </div>
                <div className="mt-[3px] text-[12.5px] text-text-sub">
                  <Mark text={r.snippet} q={submitted} />
                </div>
                <div className="mt-[3px] text-[11.5px] text-text-faint">
                  {categoryLabel(r.category)} · {formatBytes(r.size_bytes)} ·{" "}
                  {new Date(r.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </div>
              </div>
              <span className="font-mono text-[11px] text-text-faint">{r.score.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {response && response.results.length === 0 && !loading && (
        <div className="rounded-card border border-dashed border-border bg-card px-6 py-10 text-center text-[12.5px] text-text-sub">
          Nothing found for “{submitted}” — try fewer or different words.
        </div>
      )}

      {!response && !loading && (
        <div className="rounded-card border border-dashed border-border bg-card px-6 py-10 text-center text-[12.5px] text-text-sub">
          Search your vault — titles, vendors, extracted fields, dates. Tip:{" "}
          <span className="font-mono text-[11.5px]">⌘K</span> works from anywhere.
        </div>
      )}
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchPageInner />
    </Suspense>
  );
}
