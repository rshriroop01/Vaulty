"use client";

/** Family — screen 2i: members with role dropdowns, pending invites, and the
 *  category-access matrix (cells cycle full → view → none). */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import {
  createInvite,
  getMembers,
  patchMember,
  removeMember,
  type Member,
  type MembersResponse,
} from "@/lib/family";

const PLAN_UPGRADE_TYPE_SUFFIX = "/plan-upgrade-required";

/** Matches components/AnswerCard.tsx's AnswerUpgradeCard styling (dashed
 *  navy-adjacent card) — that component only takes a bare detail string, so
 *  this adds the "Upgrade" link the invite flow needs. */
function FamilyPlanUpsell({ detail }: { detail: string }) {
  return (
    <div className="mb-4 flex items-center justify-between rounded-card border border-dashed border-border bg-card px-6 py-5">
      <div>
        <div className="text-[10.5px] font-semibold uppercase tracking-[.1em] text-text-faint">
          Family plan required
        </div>
        <p className="mt-1.5 text-[13px] text-text-sub">{detail}</p>
      </div>
      <Link
        href="/billing"
        className="ml-4 flex-none rounded-control bg-ink px-4 py-[10px] text-[13px] font-semibold text-white"
      >
        Upgrade
      </Link>
    </div>
  );
}

const ROLES = ["admin", "member", "emergency"] as const;
const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  emergency: "Emergency only",
};

const ACCESS_CYCLE: Record<string, string> = { full: "view", view: "none", none: "full" };
const ACCESS_GLYPH: Record<string, { glyph: string; className: string; title: string }> = {
  full: { glyph: "●", className: "text-ink", title: "Full access" },
  view: { glyph: "◐", className: "text-warn", title: "View only" },
  none: { glyph: "◯", className: "text-text-faint", title: "No access" },
};

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function defaultAccess(member: Member, category: string): string {
  if (member.role === "owner" || member.role === "admin") return "full";
  const fallback = member.role === "emergency" ? "none" : "full";
  return member.category_access?.[category] ?? fallback;
}

export default function FamilyPage() {
  const [data, setData] = useState<MembersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upsell, setUpsell] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);

  const refresh = useCallback(async () => {
    setData(await getMembers().catch(() => null));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const me = data?.members.find((m) => m.is_me);
  const iAmOwner = me?.role === "owner";

  async function onRoleChange(member: Member, role: string) {
    setError(null);
    try {
      await patchMember(member.membership_id, { role });
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change role");
    }
  }

  async function onCycleAccess(member: Member, category: string) {
    if (!iAmOwner || member.role === "owner" || member.role === "admin") return;
    const next = ACCESS_CYCLE[defaultAccess(member, category)];
    const matrix: Record<string, string> = {};
    for (const c of CATEGORIES) matrix[c.key] = defaultAccess(member, c.key);
    matrix[category] = next;
    setError(null);
    try {
      await patchMember(member.membership_id, { category_access: matrix });
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update access");
    }
  }

  return (
    <>
      <div className="mb-5 flex items-center">
        <div>
          <h1 className="text-[21px] font-semibold tracking-[-0.01em]">Family</h1>
          <p className="mt-0.5 text-[13px] text-text-sub">
            {data ? `${data.vault_name} · ${data.members.length} of 6 seats` : "Loading…"}
          </p>
        </div>
        <button
          onClick={() => setInviteOpen((v) => !v)}
          className="ml-auto rounded-[9px] bg-ink px-[18px] py-[11px] text-[13px] font-semibold text-white"
        >
          ＋ Invite member
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-tag bg-urgent-bg px-3 py-2 text-[12px] font-medium text-urgent">
          {error}
        </div>
      )}

      {upsell && <FamilyPlanUpsell detail={upsell} />}

      {inviteOpen && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            setError(null);
            setUpsell(null);
            try {
              await createInvite(String(form.get("email")), String(form.get("role")));
              setInviteOpen(false);
              void refresh();
            } catch (err) {
              if (
                err instanceof ApiError &&
                err.status === 403 &&
                err.type?.endsWith(PLAN_UPGRADE_TYPE_SUFFIX)
              ) {
                setUpsell(err.message);
              } else {
                setError(err instanceof Error ? err.message : "Invite failed");
              }
            }
          }}
          className="mb-4 flex items-end gap-3 rounded-[10px] border border-border bg-card px-[18px] py-4"
        >
          <div className="flex-1">
            <label
              htmlFor="email"
              className="mb-1.5 block text-[12px] font-semibold text-[#4c5561]"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              placeholder="family@example.com"
              className="w-full rounded-control border border-input-border px-3.5 py-[9px] text-[13.5px] outline-none focus:border-ink"
            />
          </div>
          <div>
            <label htmlFor="role" className="mb-1.5 block text-[12px] font-semibold text-[#4c5561]">
              Role
            </label>
            <select
              id="role"
              name="role"
              defaultValue="member"
              className="rounded-control border border-input-border bg-card px-3 py-[9px] text-[13px] outline-none focus:border-ink"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </div>
          <button className="rounded-control bg-ink px-4 py-[10px] text-[13px] font-semibold text-white">
            Send invite
          </button>
        </form>
      )}

      <div className="mb-4 overflow-hidden rounded-[10px] border border-border bg-card">
        <div className="px-[18px] pb-2.5 pt-[13px] text-[14px] font-semibold">Members</div>
        {(data?.members ?? []).map((m) => (
          <div
            key={m.membership_id}
            className="flex items-center gap-3 border-t border-hairline px-[18px] py-3"
          >
            <div className="grid h-8 w-8 flex-none place-items-center rounded-full bg-avatar text-[11px] font-semibold text-ink">
              {initials(m.name)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13.5px] font-medium">
                {m.name}
                {m.is_me && <span className="ml-1.5 text-[11px] text-text-faint">(you)</span>}
              </div>
              <div className="text-[12px] text-text-sub">{m.email}</div>
            </div>
            {m.role === "owner" || !iAmOwner || m.is_me ? (
              <span className="rounded-tag bg-nav-active px-[9px] py-[3px] text-[11.5px] font-semibold text-ink">
                {ROLE_LABELS[m.role] ?? m.role}
              </span>
            ) : (
              <>
                <select
                  value={m.role}
                  onChange={(e) => void onRoleChange(m, e.target.value)}
                  className="rounded-control border border-input-border bg-card px-2 py-1.5 text-[12px] outline-none focus:border-ink"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </select>
                <button
                  onClick={async () => {
                    await removeMember(m.membership_id);
                    void refresh();
                  }}
                  className="rounded-[6px] px-2 py-1 text-[12px] font-semibold text-urgent hover:bg-urgent-bg"
                >
                  Remove
                </button>
              </>
            )}
          </div>
        ))}
        {(data?.pending_invites ?? []).map((invite) => (
          <div
            key={invite.id}
            className="flex items-center gap-3 border-t border-hairline bg-app/50 px-[18px] py-3"
          >
            <div className="grid h-8 w-8 flex-none place-items-center rounded-full border border-dashed border-[#c8cfd7] text-[11px] font-semibold text-text-faint">
              ?
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13.5px] font-medium">{invite.email}</div>
              <div className="text-[12px] text-text-sub">
                Invited as {ROLE_LABELS[invite.role] ?? invite.role} · pending
              </div>
            </div>
            <span className="rounded-tag bg-warn-bg px-[9px] py-[3px] text-[11.5px] font-semibold text-warn">
              Invite sent
            </span>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-[10px] border border-border bg-card">
        <div className="flex items-baseline justify-between px-[18px] pb-2.5 pt-[13px]">
          <span className="text-[14px] font-semibold">Category access</span>
          <span className="text-[11.5px] text-text-faint">
            ● full · ◐ view · ◯ none {iAmOwner ? "— click a cell to change" : ""}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-t border-hairline">
                <th className="px-[18px] py-2 text-left font-mono text-[10px] font-semibold uppercase tracking-[.1em] text-text-faint">
                  Member
                </th>
                {CATEGORIES.map((c) => (
                  <th
                    key={c.key}
                    className="px-2 py-2 text-center font-mono text-[10px] font-semibold uppercase tracking-[.1em] text-text-faint"
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.members ?? []).map((m) => (
                <tr key={m.membership_id} className="border-t border-hairline">
                  <td className="px-[18px] py-2.5 text-[13px] font-medium">{m.name}</td>
                  {CATEGORIES.map((c) => {
                    const level = defaultAccess(m, c.key);
                    const glyph = ACCESS_GLYPH[level];
                    const locked = m.role === "owner" || m.role === "admin" || !iAmOwner;
                    return (
                      <td key={c.key} className="px-2 py-2.5 text-center">
                        <button
                          onClick={() => void onCycleAccess(m, c.key)}
                          disabled={locked}
                          title={glyph.title}
                          className={`text-[15px] ${glyph.className} ${locked ? "cursor-default opacity-70" : "hover:scale-110"}`}
                        >
                          {glyph.glyph}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
