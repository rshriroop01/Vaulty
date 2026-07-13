export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly title: string,
    detail: string,
  ) {
    super(detail);
  }
}

/**
 * Thin typed fetch wrapper for the Vaultly API.
 * The backend always returns RFC 7807 problem+json on failure.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const problem = await res
      .json()
      .catch(() => ({ title: res.statusText, detail: res.statusText }));
    throw new ApiError(res.status, problem.title, problem.detail);
  }
  return res.json() as Promise<T>;
}
