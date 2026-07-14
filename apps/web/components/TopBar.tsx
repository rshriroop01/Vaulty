"use client";

import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";

/** Dashboard top bar per screen 1a: ask bar (⌘K lands in M4), Add document, avatar. */
export function TopBar({ name }: { name: string }) {
  const router = useRouter();
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  async function signOut() {
    await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => null);
    router.push("/signin");
    router.refresh();
  }

  return (
    <div className="mb-6 flex items-center gap-3.5">
      <button
        onClick={() => window.dispatchEvent(new Event("vaultly:open-search"))}
        className="flex flex-1 items-center gap-2.5 rounded-[9px] border border-input-border bg-card px-4 py-[11px] text-left shadow-[0_1px_2px_rgba(22,50,79,.04)]"
      >
        <span className="h-3.5 w-3.5 flex-none rounded-full border-2 border-text-faint" />
        <span className="text-[13.5px] text-text-faint">
          Ask Vaultly — “which warranties expire next month?”
        </span>
        <span className="ml-auto rounded-[4px] border border-border px-1.5 py-px font-mono text-[11px] text-[#b0b8c1]">
          ⌘K
        </span>
      </button>
      <button className="flex items-center gap-[9px] rounded-[9px] bg-ink px-[18px] py-[11px] text-[13px] font-semibold text-white">
        ＋ Add document
      </button>
      <button
        onClick={signOut}
        title="Sign out"
        className="grid h-9 w-9 place-items-center rounded-full bg-avatar text-[12px] font-semibold text-ink"
      >
        {initials}
      </button>
    </div>
  );
}
