export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly title: string,
    detail: string,
    public readonly type?: string,
  ) {
    super(detail);
  }
}

/** Rotate the session using the refresh cookie. Returns true on success. */
export async function tryRefreshSession(): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
  }).catch(() => null);
  return res?.ok ?? false;
}

/**
 * Thin typed fetch wrapper for the Vaultly API.
 * The backend always returns RFC 7807 problem+json on failure.
 * A 401 triggers one silent refresh + retry (access tokens live 15 minutes).
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const doFetch = () =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });

  let res = await doFetch();
  if (res.status === 401 && (await tryRefreshSession())) {
    res = await doFetch();
  }
  if (!res.ok) {
    const problem = await res
      .json()
      .catch(() => ({ title: res.statusText, detail: res.statusText }));
    throw new ApiError(res.status, problem.title, problem.detail, problem.type);
  }
  return res.json() as Promise<T>;
}
