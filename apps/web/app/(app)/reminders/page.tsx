"use client";

/** Reminders center — screen 2e: urgency groups, checkbox rows with source-doc
 *  links, right rail with delivery toggles, lead-time chips, delivery rate. */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  createReminder,
  deleteReminder,
  getReminderStats,
  listReminders,
  setReminderCompleted,
  urgency,
  type Reminder,
  type ReminderStats,
} from "@/lib/reminders";

function monoDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

function Row({
  reminder,
  onToggle,
  onDelete,
}: {
  reminder: Reminder;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const u = urgency(reminder.due_date);
  return (
    <div className="group flex items-center gap-3.5 border-t border-hairline px-[18px] py-3 hover:bg-[#f8fafc]">
      <button
        onClick={onToggle}
        aria-label="Complete reminder"
        className="h-4 w-4 flex-none rounded-[5px] border-[1.5px] border-[#c8cfd7] hover:border-ink"
      />
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-medium">{reminder.title}</div>
        <div className="text-[12px] text-text-sub">
          {reminder.document_title ? (
            <>
              From{" "}
              <Link href="/documents" className="text-link">
                {reminder.document_title}
              </Link>{" "}
              ·{" "}
            </>
          ) : null}
          Email
        </div>
      </div>
      <span className="whitespace-nowrap font-mono text-[12px] font-medium text-[#4c5561]">
        {monoDate(reminder.due_date)}
      </span>
      <span
        className={`whitespace-nowrap rounded-tag px-[9px] py-[3px] text-[11.5px] font-semibold ${u.className}`}
      >
        {u.label}
      </span>
      <button
        onClick={onDelete}
        className="invisible rounded-[6px] px-2 py-1 text-[12px] font-semibold text-urgent hover:bg-urgent-bg group-hover:visible"
      >
        Delete
      </button>
    </div>
  );
}

export default function RemindersPage() {
  const [reminders, setReminders] = useState<Reminder[] | null>(null);
  const [stats, setStats] = useState<ReminderStats | null>(null);
  const [showForm, setShowForm] = useState(false);

  const refresh = useCallback(async () => {
    const [list, s] = await Promise.all([
      listReminders().catch(() => []),
      getReminderStats().catch(() => null),
    ]);
    setReminders(list);
    setStats(s);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onToggle(id: string) {
    await setReminderCompleted(id, true);
    void refresh();
  }
  async function onDelete(id: string) {
    await deleteReminder(id);
    void refresh();
  }

  const soon = (reminders ?? []).filter((r) => urgency(r.due_date).daysLeft <= 30);
  const later = (reminders ?? []).filter((r) => urgency(r.due_date).daysLeft > 30);

  return (
    <>
      <div className="mb-5 flex items-center">
        <div>
          <h1 className="text-[21px] font-semibold tracking-[-0.01em]">Reminders</h1>
          <p className="mt-0.5 text-[13px] text-text-sub">
            Most are created automatically from your documents.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="ml-auto rounded-[9px] bg-ink px-[18px] py-[11px] text-[13px] font-semibold text-white"
        >
          ＋ New reminder
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            await createReminder({
              title: String(form.get("title")),
              due_date: String(form.get("due_date")),
            });
            setShowForm(false);
            void refresh();
          }}
          className="mb-4 flex items-end gap-3 rounded-[10px] border border-border bg-card px-[18px] py-4"
        >
          <div className="flex-1">
            <label
              htmlFor="title"
              className="mb-1.5 block text-[12px] font-semibold text-[#4c5561]"
            >
              What should we remind you about?
            </label>
            <input
              id="title"
              name="title"
              required
              placeholder="Passport renewal"
              className="w-full rounded-control border border-input-border px-3.5 py-[9px] text-[13.5px] outline-none focus:border-ink"
            />
          </div>
          <div>
            <label
              htmlFor="due_date"
              className="mb-1.5 block text-[12px] font-semibold text-[#4c5561]"
            >
              Due date
            </label>
            <input
              id="due_date"
              name="due_date"
              type="date"
              required
              className="rounded-control border border-input-border px-3.5 py-[9px] font-mono text-[12.5px] outline-none focus:border-ink"
            />
          </div>
          <button className="rounded-control bg-ink px-4 py-[10px] text-[13px] font-semibold text-white">
            Create
          </button>
        </form>
      )}

      <div className="grid grid-cols-[1.6fr_1fr] items-start gap-4">
        <div className="grid gap-4">
          <div className="overflow-hidden rounded-[10px] border border-border bg-card">
            <div className="px-[18px] pb-2.5 pt-[13px] text-[13px] font-semibold text-[#4c5561]">
              Needs attention · next 30 days
            </div>
            {reminders === null ? (
              <div className="space-y-2 px-[18px] pb-4">
                {[0, 1].map((i) => (
                  <div key={i} className="h-10 animate-pulse rounded-control bg-hairline" />
                ))}
              </div>
            ) : soon.length === 0 ? (
              <div className="m-[0_18px_16px] rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
                Nothing due in the next 30 days.
              </div>
            ) : (
              soon.map((r) => (
                <Row
                  key={r.id}
                  reminder={r}
                  onToggle={() => void onToggle(r.id)}
                  onDelete={() => void onDelete(r.id)}
                />
              ))
            )}
          </div>

          <div className="overflow-hidden rounded-[10px] border border-border bg-card">
            <div className="px-[18px] pb-2.5 pt-[13px] text-[13px] font-semibold text-[#4c5561]">
              Later
            </div>
            {later.length === 0 ? (
              <div className="m-[0_18px_16px] rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
                Nothing scheduled further out.
              </div>
            ) : (
              later.map((r) => (
                <Row
                  key={r.id}
                  reminder={r}
                  onToggle={() => void onToggle(r.id)}
                  onDelete={() => void onDelete(r.id)}
                />
              ))
            )}
          </div>
        </div>

        <div className="grid gap-4">
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-3 text-[14px] font-semibold">Delivery</div>
            <div className="flex items-center justify-between border-b border-[#f2f4f6] py-2">
              <span className="text-[13px]">Email</span>
              <span className="relative inline-block h-5 w-[34px] rounded-[10px] bg-ink">
                <span className="absolute right-0.5 top-0.5 h-4 w-4 rounded-full bg-white" />
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-[#f2f4f6] py-2">
              <span className="text-[13px] text-text-faint">Push notifications · mobile (V3)</span>
              <span className="relative inline-block h-5 w-[34px] rounded-[10px] bg-[#e6eaee]">
                <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white" />
              </span>
            </div>
            <div className="pb-0.5 pt-2.5">
              <div className="mb-2 text-[12px] text-text-sub">Default lead times</div>
              <div className="flex gap-2">
                {["30d", "7d", "1d"].map((t) => (
                  <span
                    key={t}
                    className="rounded-[6px] bg-nav-active px-[11px] py-[5px] font-mono text-[12px] font-semibold text-ink"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-2 text-[12px] text-text-sub">Delivery rate</div>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[26px] font-semibold text-ok">
                {stats?.delivery_rate != null ? `${(stats.delivery_rate * 100).toFixed(1)}%` : "—"}
              </span>
              <span className="text-[11.5px] text-text-faint">
                {stats && stats.sent_total + stats.failed_total > 0
                  ? `${stats.sent_total} of ${stats.sent_total + stats.failed_total} sent`
                  : "no sends yet"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
