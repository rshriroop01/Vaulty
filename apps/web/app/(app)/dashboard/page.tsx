import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { getMe } from "@/lib/server-auth";

// Category accents from the approved 1a design data
const CATEGORIES = [
  { label: "Receipts", color: "#3b6fe0" },
  { label: "Warranties", color: "#1f8577" },
  { label: "Insurance", color: "#e26a3c" },
  { label: "Medical", color: "#946200" },
  { label: "IDs & Legal", color: "#6a5acd" },
  { label: "Home", color: "#4c5561" },
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="m-[12px_18px_16px] rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
      {children}
    </div>
  );
}

export default async function DashboardPage() {
  const me = await getMe();
  if (!me) redirect("/signin");
  const firstName = me.name.split(" ")[0];
  const memberCount = 1; // becomes real at M7 (family sharing)

  const stats = [
    { label: "Documents", value: "0", sub: "add your first", color: "#171d26" },
    { label: "Action needed", value: "0", sub: "deadlines <30 days", color: "#171d26" },
    { label: "Reminders set", value: "0", sub: "email delivery", color: "#171d26" },
    { label: "Family members", value: String(memberCount), sub: "of 6 seats", color: "#171d26" },
  ];

  return (
    <>
      <TopBar name={me.name} />
      <h1 className="mb-0.5 text-[21px] font-semibold tracking-[-0.01em]">
        {greeting()}, {firstName}
      </h1>
      <p className="mb-[22px] text-[13px] text-text-sub">
        No deadlines need attention. Add documents to get started.
      </p>

      <div className="mb-[22px] grid grid-cols-4 gap-3.5">
        {stats.map((s) => (
          <div key={s.label} className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-2 text-[12px] text-text-sub">{s.label}</div>
            <div className="flex items-baseline gap-2">
              <span
                className="font-mono text-[26px] font-semibold tracking-[-0.02em]"
                style={{ color: s.color }}
              >
                {s.value}
              </span>
              <span className="text-[11.5px] text-text-faint">{s.sub}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[1.5fr_1fr] items-start gap-3.5">
        <div className="overflow-hidden rounded-[10px] border border-border bg-card">
          <div className="flex items-baseline justify-between px-[18px] pb-3 pt-[15px]">
            <span className="text-[14px] font-semibold">Upcoming deadlines</span>
            <span className="text-[12px] font-medium text-link">View all</span>
          </div>
          <EmptyState>
            Nothing tracked yet — deadlines appear automatically when documents with dates are
            added.
          </EmptyState>
        </div>

        <div className="grid gap-3.5">
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-[15px]">
            <div className="mb-3 text-[14px] font-semibold">Vault</div>
            <div className="grid grid-cols-2 gap-[9px]">
              {CATEGORIES.map((c) => (
                <div
                  key={c.label}
                  className="flex items-center gap-[9px] rounded-control border border-hairline px-[11px] py-[9px]"
                >
                  <span
                    className="h-[9px] w-[9px] flex-none rounded-[2px]"
                    style={{ background: c.color }}
                  />
                  <span className="text-[12.5px] font-medium">{c.label}</span>
                  <span className="ml-auto font-mono text-[11.5px] text-text-faint">0</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[10px] border border-border bg-card px-[18px] py-[15px]">
            <div className="mb-2.5 flex items-baseline justify-between">
              <span className="text-[14px] font-semibold">Recently added</span>
            </div>
            <div className="rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
              Uploads land here — drag &amp; drop arrives with the Documents milestone.
            </div>
          </div>

          <div className="rounded-[10px] bg-ink px-[18px] py-[15px] text-white">
            <div className="mb-1 text-[13.5px] font-semibold">Emergency binder</div>
            <div className="mb-2.5 text-[12px] leading-[1.5] text-[#b9c6d3]">
              No delegates yet · QR not issued · last accessed never
            </div>
            <span className="inline-block rounded-[6px] bg-white/14 px-3 py-1.5 text-[12px] font-semibold">
              Manage access
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
