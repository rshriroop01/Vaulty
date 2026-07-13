import { API_BASE_URL } from "@/lib/api";

type ReadyState = { status: string; checks?: Record<string, boolean> };

async function getReadiness(): Promise<ReadyState | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/readyz`, { cache: "no-store" });
    return (await res.json()) as ReadyState;
  } catch {
    return null;
  }
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded-tag px-[9px] py-[3px] text-[11.5px] font-semibold ${
        ok ? "bg-ok-bg text-ok" : "bg-urgent-bg text-urgent"
      }`}
    >
      {label}
    </span>
  );
}

/** Operational status page — the end-to-end smoke test for the local stack. */
export default async function Status() {
  const ready = await getReadiness();
  const checks = ready?.checks ?? {};

  return (
    <main className="mx-auto max-w-xl px-8 py-20">
      <div className="mb-8 flex items-center gap-2.5">
        <div className="grid h-7 w-7 place-items-center rounded-[7px] bg-ink font-mono text-[13px] font-bold text-white">
          V
        </div>
        <span className="text-base font-bold tracking-tight">Vaultly</span>
      </div>

      <div className="rounded-card border border-border bg-card p-6 shadow-card">
        <h1 className="text-[21px] font-semibold">System status</h1>
        <div className="mt-5 flex flex-col gap-3 border-t border-hairline pt-5">
          <div className="flex items-center justify-between">
            <span className="text-[13.5px]">API</span>
            <StatusPill ok={ready !== null} label={ready !== null ? "Reachable" : "Unreachable"} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[13.5px]">PostgreSQL</span>
            <StatusPill ok={checks.database === true} label={checks.database ? "Ready" : "Down"} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[13.5px]">Redis</span>
            <StatusPill ok={checks.redis === true} label={checks.redis ? "Ready" : "Down"} />
          </div>
        </div>
        <p className="mt-5 border-t border-hairline pt-4 font-mono text-[11px] text-text-faint">
          {API_BASE_URL}
        </p>
      </div>
    </main>
  );
}
