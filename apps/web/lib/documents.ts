import { API_BASE_URL, apiFetch } from "@/lib/api";

export type DocumentItem = {
  id: string;
  title: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  category: string;
  status: string;
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

export const listDocuments = () => apiFetch<DocumentItem[]>("/api/v1/documents", withCreds);

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
