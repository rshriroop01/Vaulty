"use client";

/** Invite landing: shows who invited you and to what, then joins the vault.
 *  If you're not signed in yet, sign-in/sign-up bounce back here via ?next=. */

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { acceptInvite, getInviteInfo, type InviteInfo } from "@/lib/family";

export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const router = useRouter();
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    getInviteInfo(token)
      .then(setInfo)
      .catch(() => setError("This invitation is invalid or has expired."));
  }, [token]);

  async function onAccept() {
    setPending(true);
    setError(null);
    const resp = await acceptInvite(token);
    if (resp.ok) {
      router.push("/dashboard");
      router.refresh();
      return;
    }
    setPending(false);
    if (resp.status === 401) {
      setError("Sign in or create an account first, then accept the invitation.");
    } else {
      const problem = await resp.json().catch(() => null);
      setError(problem?.detail ?? "Could not accept the invitation.");
    }
  }

  const next = encodeURIComponent(`/invite/${token}`);

  return (
    <div className="grid min-h-screen place-items-center bg-app px-6 text-text">
      <div className="w-[420px] rounded-xl border border-border bg-card p-8 shadow-[0_2px_8px_rgba(22,50,79,.05)]">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="grid h-7 w-7 place-items-center rounded-[7px] bg-ink font-mono text-[13px] font-bold text-white">
            V
          </div>
          <span className="text-base font-bold tracking-tight">Vaultly</span>
        </div>

        {error && !info ? (
          <p className="text-[13.5px] text-urgent">{error}</p>
        ) : info === null ? (
          <div className="h-16 animate-pulse rounded-control bg-hairline" />
        ) : (
          <>
            <h1 className="text-[19px] font-semibold">Join {info.vault_name}</h1>
            <p className="mt-1.5 text-[13px] leading-relaxed text-text-sub">
              <strong>{info.invited_by}</strong> invited{" "}
              <span className="font-mono text-[12px]">{info.email}</span> to join as{" "}
              <strong>{info.role === "emergency" ? "emergency-only member" : info.role}</strong>.
            </p>
            {error && (
              <div className="mt-3 rounded-tag bg-warn-bg px-3 py-2 text-[12px] font-medium text-warn">
                {error}
              </div>
            )}
            <button
              onClick={() => void onAccept()}
              disabled={pending}
              className="mt-5 w-full rounded-control bg-ink py-3 text-[13.5px] font-semibold text-white disabled:opacity-60"
            >
              {pending ? "Joining…" : "Accept invitation"}
            </button>
            <div className="mt-4 text-center text-[12px] text-text-sub">
              New here?{" "}
              <Link href={`/signup?next=${next}`} className="font-medium text-link">
                Create an account
              </Link>{" "}
              · Have one?{" "}
              <Link href={`/signin?next=${next}`} className="font-medium text-link">
                Sign in
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
