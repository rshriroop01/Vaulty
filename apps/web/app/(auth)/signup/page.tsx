"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";
import { Field, FormError, GoogleButton, OrDivider, PrimaryButton } from "@/components/auth/fields";

function SignUpPageInner() {
  const router = useRouter();
  const next = useSearchParams().get("next") ?? "/dashboard";
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(e.currentTarget);
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.get("name"),
        email: form.get("email"),
        password: form.get("password"),
      }),
    }).catch(() => null);
    if (res?.ok) {
      router.push(next);
      router.refresh();
      return;
    }
    setPending(false);
    if (!res) setError("Cannot reach the Vaultly API. Is the stack running?");
    else {
      const problem = await res.json().catch(() => null);
      setError(problem?.detail ?? "Sign-up failed");
    }
  }

  return (
    <div className="w-[380px] rounded-xl border border-border bg-card p-[32px_32px_28px] shadow-[0_2px_8px_rgba(22,50,79,.05)]">
      <div className="mb-1 text-[20px] font-semibold">Create your account</div>
      <div className="mb-[22px] text-[13px] text-text-sub">
        Your vault is ready in under a minute
      </div>
      <FormError message={error} />
      <form onSubmit={onSubmit} className="grid gap-3.5">
        <Field
          label="Full name"
          id="name"
          name="name"
          autoComplete="name"
          required
          placeholder="Shriroop Roychoudhury"
        />
        <Field
          label="Email"
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
        />
        <div>
          <Field
            label="Password"
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
          />
          <div className="mt-1.5 text-[11.5px] text-text-faint">
            At least 8 characters, with a letter and a number.
          </div>
        </div>
        <PrimaryButton type="submit" disabled={pending}>
          {pending ? "Creating your vault…" : "Continue"}
        </PrimaryButton>
      </form>
      <OrDivider />
      <GoogleButton
        onClick={() => setError("Google sign-up is coming soon — use email for now.")}
      />
      <div className="mt-5 text-center text-[12px] text-text-sub">
        Already have an account?{" "}
        <Link href="/signin" className="font-medium text-link">
          Sign in
        </Link>
      </div>
    </div>
  );
}

export default function SignUpPage() {
  return (
    <Suspense>
      <SignUpPageInner />
    </Suspense>
  );
}
