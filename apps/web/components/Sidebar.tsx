"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Sidebar({
  plan,
  storageUsed,
  storagePct,
  remindersCount = 0,
}: {
  plan: string;
  storageUsed: string;
  storagePct: number;
  remindersCount?: number;
}) {
  const pathname = usePathname();
  const NAV = [
    { label: "Dashboard", href: "/dashboard" },
    { label: "Documents", href: "/documents" },
    { label: "Reminders", href: "/reminders", count: remindersCount },
    { label: "Insurance", href: "/insurance" },
    { label: "Medical bills", href: "/medical" },
    { label: "Emergency binder", href: "/emergency" },
    { label: "Family", href: "/family" },
  ];
  return (
    <aside className="flex w-[232px] flex-none flex-col border-r border-border bg-card py-5">
      <div className="flex items-center gap-2.5 px-5 pb-[22px]">
        <div className="grid h-7 w-7 place-items-center rounded-[7px] bg-ink font-mono text-[13px] font-bold text-white">
          V
        </div>
        <span className="text-base font-bold tracking-[-0.01em]">Vaultly</span>
      </div>
      {NAV.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`mx-2.5 flex items-center gap-[11px] rounded-[7px] px-3 py-[9px] text-[13.5px] ${
              active ? "bg-nav-active font-semibold text-ink" : "font-normal text-[#4c5561]"
            }`}
          >
            <span className={`h-2 w-2 rounded-[2px] ${active ? "bg-ink" : "bg-[#c8cfd7]"}`} />
            {item.label}
            {item.count ? (
              <span className="ml-auto rounded-[9px] bg-urgent-bg px-[7px] py-px font-mono text-[11px] font-semibold text-urgent">
                {item.count}
              </span>
            ) : null}
          </Link>
        );
      })}
      <div className="mt-auto border-t border-hairline px-5 pt-4">
        <div className="mb-1.5 text-[11px] text-text-sub">
          Storage · {plan.charAt(0).toUpperCase() + plan.slice(1)}
        </div>
        <div className="h-[5px] rounded-[3px] bg-[#e6eaee]">
          <div
            className="h-[5px] rounded-[3px] bg-ink"
            style={{ width: `${Math.max(storagePct, 2)}%` }}
          />
        </div>
        <div className="mt-1.5 font-mono text-[11px] text-text-sub">{storageUsed} used</div>
      </div>
    </aside>
  );
}
