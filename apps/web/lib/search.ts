import { apiFetch } from "@/lib/api";
import type { ExtractedData } from "@/lib/documents";

export type SearchResult = {
  id: string;
  title: string;
  file_name: string;
  category: string;
  status: string;
  size_bytes: number;
  snippet: string;
  score: number;
  expiry_date: string | null;
  extracted: ExtractedData | null;
  created_at: string;
};

export type SearchResponse = {
  query: string;
  latency_ms: number;
  total: number;
  counts: Record<string, number>;
  results: SearchResult[];
};

export function searchDocuments(q: string, category?: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (category) params.set("category", category);
  return apiFetch<SearchResponse>(`/api/v1/search?${params}`, { credentials: "include" });
}

/** Split text into plain/highlighted parts for the #FDF4DD mark style (design 2c). */
export function highlightParts(text: string, q: string): { text: string; highlight: boolean }[] {
  const terms = (q.match(/[A-Za-z0-9]+/g) ?? []).filter(Boolean);
  if (terms.length === 0) return [{ text, highlight: false }];
  const pattern = new RegExp(`(${terms.join("|")})`, "gi");
  return text
    .split(pattern)
    .filter((part) => part !== "")
    .map((part) => ({
      text: part,
      highlight: terms.some((t) => part.toLowerCase() === t.toLowerCase()),
    }));
}
