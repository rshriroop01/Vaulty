import { redirect } from "next/navigation";
import { CommandK } from "@/components/CommandK";
import { Sidebar } from "@/components/Sidebar";
import { formatBytes } from "@/lib/categories";
import { getMe } from "@/lib/server-auth";
import { getReminderStatsServer, getUsageServer } from "@/lib/server-data";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me) redirect("/signin");
  const [usage, reminderStats] = await Promise.all([getUsageServer(), getReminderStatsServer()]);

  const plan = usage?.plan ?? me.vaults[0]?.plan ?? "free";
  const used = usage?.storage_bytes ?? 0;
  const limit = usage?.storage_limit_bytes ?? null;
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  return (
    <div className="flex min-h-screen bg-app">
      <Sidebar
        plan={plan}
        storageUsed={formatBytes(used)}
        storagePct={pct}
        remindersCount={reminderStats?.needs_attention ?? 0}
      />
      <main className="min-w-0 flex-1 p-[24px_32px_32px]">{children}</main>
      <CommandK />
    </div>
  );
}
