"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { API_BASE_URL, tryRefreshSession } from "@/lib/api";
import { Field, FormError, GoogleButton, OrDivider, PrimaryButton } from "@/components/auth/fields";

function SignInPageInner() {
  const router = useRouter();
  const next = useSearchParams().get("next") ?? "/dashboard";
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // Landed here with an expired access token but a live refresh session?
  // Rotate silently and bounce back in.
  useEffect(() => {
    void tryRefreshSession().then((ok) => {
      if (ok) {
        router.replace(next);
        router.refresh();
      }
    });
  }, [router, next]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(e.currentTarget);
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    }).catch(() => null);
    if (res?.ok) {
      router.push(next);
      router.refresh();
      return;
    }
    setPending(false);
    if (!res) setError("Cannot reach the Vaultly API. Is the stack running?");
    else setError((await res.json().catch(() => null))?.detail ?? "Sign-in failed");
  }

  return (
    <div className="w-[380px] rounded-xl border border-border bg-card p-[32px_32px_28px] shadow-[0_2px_8px_rgba(22,50,79,.05)]">
      <div className="mb-1 text-[20px] font-semibold">Welcome back</div>
      <div className="mb-[22px] text-[13px] text-text-sub">Sign in to your vault</div>
      <FormError message={error} />
      <form onSubmit={onSubmit} className="grid gap-3.5">
        <Field
          label="Email"
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
        />
        <Field
          label="Password"
          labelRight={<span className="text-[12px] text-link">Forgot?</span>}
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <PrimaryButton type="submit" disabled={pending}>
          {pending ? "Signing in…" : "Continue"}
        </PrimaryButton>
      </form>
      <OrDivider />
      <GoogleButton
        onClick={() => setError("Google sign-in is coming soon — use email for now.")}
      />
      <div className="mt-5 text-center text-[12px] text-text-sub">
        New to Vaultly?{" "}
        <Link href="/signup" className="font-medium text-link">
          Create an account
        </Link>
      </div>
      <div className="mt-3.5 border-t border-hairline pt-3.5 text-center text-[11px] text-text-faint">
        If 2FA is enabled, a 6-digit code step follows.
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense>
      <SignInPageInner />
    </Suspense>
  );
}
