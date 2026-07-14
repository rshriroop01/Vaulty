import { API_BASE_URL, apiFetch } from "@/lib/api";

export type Reminder = {
  id: string;
  title: string;
  due_date: string;
  channel: string;
  lead_times: number[];
  document_id: string | null;
  document_title: string | null;
  completed: boolean;
  created_at: string;
};

export type ReminderStats = {
  total_active: number;
  needs_attention: number;
  sent_total: number;
  failed_total: number;
  delivery_rate: number | null;
};

const withCreds: RequestInit = { credentials: "include" };

export const listReminders = () => apiFetch<Reminder[]>("/api/v1/reminders", withCreds);

export const getReminderStats = () => apiFetch<ReminderStats>("/api/v1/reminders/stats", withCreds);

export const createReminder = (input: { title: string; due_date: string; document_id?: string }) =>
  apiFetch<Reminder>("/api/v1/reminders", {
    method: "POST",
    ...withCreds,
    body: JSON.stringify(input),
  });

export const setReminderCompleted = (id: string, completed: boolean) =>
  apiFetch<Reminder>(`/api/v1/reminders/${id}`, {
    method: "PATCH",
    ...withCreds,
    body: JSON.stringify({ completed }),
  });

export const deleteReminder = (id: string) =>
  fetch(`${API_BASE_URL}/api/v1/reminders/${id}`, { method: "DELETE", ...withCreds });

/** Urgency colorways from the token spec: <14d urgent, 14–30d warn, else ok. */
export function urgency(dueDate: string): {
  label: string;
  className: string;
  daysLeft: number;
} {
  const days = Math.ceil((new Date(dueDate + "T00:00:00").getTime() - Date.now()) / 86400000);
  if (days < 14)
    return {
      label: days <= 0 ? "Due today" : `${days}d left`,
      className: "bg-urgent-bg text-urgent",
      daysLeft: days,
    };
  if (days <= 30)
    return { label: `${days}d left`, className: "bg-warn-bg text-warn", daysLeft: days };
  return { label: "Scheduled", className: "bg-ok-bg text-ok", daysLeft: days };
}
