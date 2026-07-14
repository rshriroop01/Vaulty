import { API_BASE_URL, apiFetch } from "@/lib/api";

export type ExtractedData = {
  vendor: string | null;
  document_date: string | null;
  expiry_date: string | null;
  amount: number | null;
  currency: string | null;
  fields: { label: string; value: string }[];
};

export type DocumentItem = {
  id: string;
  title: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  category: string;
  status: string;
  bill_status: string | null;
  extracted: ExtractedData | null;
  expiry_date: string | null;
  created_at: string;
};

export type VaultUsage = {
  vault_id: string;
  plan: string;
  document_count: number;
  storage_bytes: number;
  document_limit: number | null;
  storage_limit_bytes: number | null;
  member_count: number;
  categories: Record<string, number>;
};

const withCreds: RequestInit = { credentials: "include" };

export const listDocuments = (category?: string) =>
  apiFetch<DocumentItem[]>(
    `/api/v1/documents${category ? `?category=${category}` : ""}`,
    withCreds,
  );

export const patchDocument = (
  id: string,
  patch: { title?: string; category?: string; bill_status?: string },
) =>
  apiFetch<DocumentItem>(`/api/v1/documents/${id}`, {
    method: "PATCH",
    ...withCreds,
    body: JSON.stringify(patch),
  });

/** "$412.70" / "₹3,201.20" / "EUR 12.00" */
export function formatMoney(amount: number, currency: string | null): string {
  const symbols: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£" };
  const sym = currency ? symbols[currency] : undefined;
  const value = amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return sym ? `${sym}${value}` : `${currency ?? ""} ${value}`.trim();
}

export const getUsage = () => apiFetch<VaultUsage>("/api/v1/vault/usage", withCreds);

export const deleteDocument = (id: string) =>
  fetch(`${API_BASE_URL}/api/v1/documents/${id}`, { method: "DELETE", ...withCreds });

export async function downloadDocument(id: string): Promise<string> {
  const { url } = await apiFetch<{ url: string }>(`/api/v1/documents/${id}/download`, withCreds);
  return url;
}

/** Full upload flow: initiate → direct PUT to storage (with progress) → complete. */
export async function uploadFile(
  file: File,
  onProgress: (pct: number) => void,
): Promise<DocumentItem> {
  const ticket = await apiFetch<{ document_id: string; upload_url: string }>(
    "/api/v1/documents/uploads",
    {
      method: "POST",
      ...withCreds,
      body: JSON.stringify({
        file_name: file.name,
        content_type: file.type || "application/pdf",
        size_bytes: file.size,
      }),
    },
  );

  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", ticket.upload_url);
    xhr.setRequestHeader("Content-Type", file.type || "application/pdf");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Storage upload failed (${xhr.status})`));
    xhr.onerror = () => reject(new Error("Storage upload failed"));
    xhr.send(file);
  });

  return apiFetch<DocumentItem>(`/api/v1/documents/${ticket.document_id}/complete`, {
    method: "POST",
    ...withCreds,
  });
}
