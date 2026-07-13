import { redirect } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { getMe } from "@/lib/server-auth";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me) redirect("/signin");
  const plan = me.vaults[0]?.plan ?? "free";

  return (
    <div className="flex min-h-screen bg-app">
      <Sidebar plan={plan} storageUsed="0 MB" />
      <main className="min-w-0 flex-1 p-[24px_32px_32px]">{children}</main>
    </div>
  );
}
