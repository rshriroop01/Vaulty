"use client";

/** Public emergency access — the PRD journey: scan QR, enter PIN, see the
 *  binder. No account, no password. Every attempt is logged and the owner
 *  is notified. */

import { use, useState } from "react";
import { accessBinder, type PublicBinder } from "@/lib/family";

export default function EmergencyAccessPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [pin, setPin] = useState("");
  const [binder, setBinder] = useState<PublicBinder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      setBinder(await accessBinder(token, pin));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Access denied");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="min-h-screen bg-app text-text">
      <div className="bg-ink px-6 py-4 text-white">
        <div className="mx-auto flex max-w-xl items-center gap-2.5">
          <div className="grid h-7 w-7 place-items-center rounded-[7px] bg-white/14 font-mono text-[13px] font-bold">
            V
          </div>
          <span className="text-[15px] font-bold">Vaultly</span>
          <span className="ml-auto text-[12px] text-[#b9c6d3]">Emergency access</span>
        </div>
      </div>

      <main className="mx-auto max-w-xl px-6 py-10">
        {binder === null ? (
          <div className="rounded-card border border-border bg-card p-7 shadow-card">
            <h1 className="text-[19px] font-semibold">Family emergency binder</h1>
            <p className="mt-1 text-[13px] text-text-sub">
              Enter the family PIN to view emergency information. The vault owner is notified of
              every access.
            </p>
            {error && (
              <div className="mt-3 rounded-tag bg-urgent-bg px-3 py-2 text-[12px] font-medium text-urgent">
                {error}
              </div>
            )}
            <form onSubmit={onSubmit} className="mt-5 flex gap-2.5">
              <input
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                inputMode="numeric"
                autoFocus
                placeholder="PIN"
                className="w-36 rounded-control border border-input-border px-3.5 py-[11px] text-center font-mono text-[16px] tracking-[.3em] outline-none focus:border-ink"
              />
              <button
                disabled={pending || !pin}
                className="rounded-control bg-ink px-5 text-[13.5px] font-semibold text-white disabled:opacity-60"
              >
                {pending ? "Checking…" : "Unlock"}
              </button>
            </form>
          </div>
        ) : (
          <div className="grid gap-4">
            <div className="rounded-card border border-border bg-card p-6 shadow-card">
              <div className="mb-1 text-[11.5px] font-semibold uppercase tracking-[.1em] text-text-faint">
                {binder.vault_name}
              </div>
              <h1 className="text-[19px] font-semibold">Emergency information</h1>
            </div>

            <div className="rounded-card border border-border bg-card p-6">
              <div className="mb-3 text-[14px] font-semibold">Emergency contacts</div>
              {binder.contacts.length === 0 ? (
                <div className="text-[12.5px] text-text-sub">None listed.</div>
              ) : (
                binder.contacts.map((c, i) => (
                  <div
                    key={i}
                    className="flex items-baseline justify-between border-t border-hairline py-2.5 first:border-t-0"
                  >
                    <div>
                      <span className="text-[13.5px] font-medium">{c.name}</span>
                      <span className="ml-2 text-[12px] text-text-sub">{c.relation}</span>
                    </div>
                    <a href={`tel:${c.phone}`} className="font-mono text-[13.5px] text-link">
                      {c.phone}
                    </a>
                  </div>
                ))
              )}
            </div>

            <div className="rounded-card border border-border bg-card p-6">
              <div className="mb-3 text-[14px] font-semibold">Medical</div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2.5 text-[13px]">
                {[
                  ["Blood group", binder.medical.blood_group],
                  ["Hospital", binder.medical.hospital],
                  ["Allergies", binder.medical.allergies],
                  ["Medications", binder.medical.medications],
                ].map(([label, value]) => (
                  <div key={label}>
                    <div className="text-[11.5px] text-text-faint">{label}</div>
                    <div className="font-medium">{value || "—"}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-card border border-border bg-card p-6">
              <div className="mb-3 text-[14px] font-semibold">Insurance</div>
              {binder.insurance.length === 0 ? (
                <div className="text-[12.5px] text-text-sub">No policies on file.</div>
              ) : (
                binder.insurance.map((p, i) => (
                  <div key={i} className="border-t border-hairline py-2.5 first:border-t-0">
                    <div className="text-[13.5px] font-medium">{p.provider}</div>
                    <div className="text-[12px] text-text-sub">
                      {p.title}
                      {p.policy_number && (
                        <span className="ml-2 font-mono text-text-faint">#{p.policy_number}</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <p className="text-center text-[11.5px] text-text-faint">
              This access was recorded and the family was notified. · Vaultly
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
