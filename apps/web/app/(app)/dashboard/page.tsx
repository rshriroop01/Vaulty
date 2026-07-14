import Link from "next/link";
import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { CATEGORIES, formatBytes } from "@/lib/categories";
import { urgency, type Reminder } from "@/lib/reminders";
import { getMe } from "@/lib/server-auth";
import {
  getDocumentsServer,
  getReminderStatsServer,
  getRemindersServer,
  getUsageServer,
} from "@/lib/server-data";

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

/** 1a deadline row: 44px date chip in urgency colorway, title, meta, pill. */
function DeadlineRow({ reminder }: { reminder: Reminder }) {
  const u = urgency(reminder.due_date);
  const due = new Date(reminder.due_date + "T00:00:00");
  const chipTone =
    u.daysLeft < 14
      ? "bg-urgent-bg text-urgent"
      : u.daysLeft <= 30
        ? "bg-warn-bg text-warn"
        : "bg-ok-bg text-ok";
  return (
    <div className="flex items-center gap-3.5 border-t border-hairline px-[18px] py-3">
      <div className={`w-11 flex-none rounded-[7px] py-[5px] text-center ${chipTone}`}>
        <div className="font-mono text-[15px] font-semibold leading-tight">{due.getDate()}</div>
        <div className="text-[9.5px] font-semibold uppercase tracking-[.08em]">
          {due.toLocaleDateString("en-US", { month: "short" })}
        </div>
      </div>
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-medium">{reminder.title}</div>
        <div className="text-[12px] text-text-sub">
          {reminder.document_title ? `From ${reminder.document_title} · ` : ""}Email reminder
        </div>
      </div>
      <span
        className={`ml-auto whitespace-nowrap rounded-tag px-[9px] py-[3px] text-[11.5px] font-semibold ${u.className}`}
      >
        {u.label}
      </span>
    </div>
  );
}

export default async function DashboardPage() {
  const me = await getMe();
  if (!me) redirect("/signin");
  const [usage, documents, reminders, reminderStats] = await Promise.all([
    getUsageServer(),
    getDocumentsServer(),
    getRemindersServer(),
    getReminderStatsServer(),
  ]);
  const firstName = me.name.split(" ")[0];
  const docCount = usage?.document_count ?? 0;
  const recent = (documents ?? []).slice(0, 4);
  const deadlines = (reminders ?? []).slice(0, 5);
  const needsAttention = reminderStats?.needs_attention ?? 0;

  const stats = [
    {
      label: "Documents",
      value: String(docCount),
      sub: docCount === 0 ? "add your first" : formatBytes(usage?.storage_bytes ?? 0),
    },
    { label: "Action needed", value: String(needsAttention), sub: "deadlines <30 days" },
    {
      label: "Reminders set",
      value: String(reminderStats?.total_active ?? 0),
      sub:
        reminderStats?.delivery_rate != null
          ? `${(reminderStats.delivery_rate * 100).toFixed(1)}% delivered`
          : "email delivery",
    },
    {
      label: "Family members",
      value: String(usage?.member_count ?? 1),
      sub: "of 6 seats",
    },
  ];

  return (
    <>
      <TopBar name={me.name} />
      <h1 className="mb-0.5 text-[21px] font-semibold tracking-[-0.01em]">
        {greeting()}, {firstName}
      </h1>
      <p className="mb-[22px] text-[13px] text-text-sub">
        {docCount === 0
          ? "No deadlines need attention. Add documents to get started."
          : needsAttention > 0
            ? `${needsAttention} deadline${needsAttention === 1 ? "" : "s"} need${needsAttention === 1 ? "s" : ""} attention this month.`
            : `${docCount} document${docCount === 1 ? "" : "s"} protected. No deadlines need attention.`}
      </p>

      <div className="mb-[22px] grid grid-cols-4 gap-3.5">
        {stats.map((s) => (
          <div key={s.label} className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-2 text-[12px] text-text-sub">{s.label}</div>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[26px] font-semibold tracking-[-0.02em] text-[#171d26]">
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
            <Link href="/reminders" className="text-[12px] font-medium text-link">
              View all
            </Link>
          </div>
          {deadlines.length === 0 ? (
            <EmptyState>
              Nothing tracked yet — deadlines appear automatically when documents with dates are
              added.
            </EmptyState>
          ) : (
            deadlines.map((r) => <DeadlineRow key={r.id} reminder={r} />)
          )}
        </div>

        <div className="grid gap-3.5">
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-[15px]">
            <div className="mb-3 text-[14px] font-semibold">Vault</div>
            <div className="grid grid-cols-2 gap-[9px]">
              {CATEGORIES.map((c) => (
                <div
                  key={c.key}
                  className="flex items-center gap-[9px] rounded-control border border-hairline px-[11px] py-[9px]"
                >
                  <span
                    className="h-[9px] w-[9px] flex-none rounded-[2px]"
                    style={{ background: c.color }}
                  />
                  <span className="text-[12.5px] font-medium">{c.label}</span>
                  <span className="ml-auto font-mono text-[11.5px] text-text-faint">
                    {usage?.categories?.[c.key] ?? 0}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[10px] border border-border bg-card px-[18px] py-[15px]">
            <div className="mb-2.5 flex items-baseline justify-between">
              <span className="text-[14px] font-semibold">Recently added</span>
              <Link href="/documents" className="text-[11.5px] font-medium text-link">
                Add more
              </Link>
            </div>
            {recent.length === 0 ? (
              <div className="rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
                Uploads land here —{" "}
                <Link href="/documents" className="font-medium text-link">
                  add your first document
                </Link>
                .
              </div>
            ) : (
              recent.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-[11px] border-t border-[#f2f4f6] py-2 first:border-t-0"
                >
                  <div className="grid h-9 w-[30px] flex-none place-items-center rounded-[4px] border border-border bg-app font-mono text-[8.5px] font-semibold text-text-faint">
                    {(r.file_name.split(".").pop() ?? "").toUpperCase().slice(0, 4)}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] font-medium">{r.title}</div>
                    <div className="text-[11px] text-text-faint">
                      {formatBytes(r.size_bytes)} ·{" "}
                      {new Date(r.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                  </div>
                </div>
              ))
            )}
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
