import { API_BASE_URL, apiFetch } from "@/lib/api";

export type Member = {
  membership_id: string;
  user_id: string;
  name: string;
  email: string;
  role: string;
  category_access: Record<string, string> | null;
  is_me: boolean;
};

export type PendingInvite = {
  id: string;
  email: string;
  role: string;
  expires_at: string;
};

export type MembersResponse = {
  vault_name: string;
  members: Member[];
  pending_invites: PendingInvite[];
};

export type ChecklistItem = { key: string; label: string; done: boolean; sub: string };

export type Contact = { name: string; phone: string; relation: string };
export type Delegate = { name: string; relation: string };
export type MedicalInfo = {
  blood_group?: string;
  allergies?: string;
  medications?: string;
  hospital?: string;
};

export type Binder = {
  contacts: Contact[];
  medical: MedicalInfo;
  delegates: Delegate[];
  checklist: ChecklistItem[];
  qr_active: boolean;
  qr_issued_at: string | null;
  access_log: { at: string; action: string }[];
};

export type PublicBinder = {
  vault_name: string;
  contacts: Contact[];
  medical: MedicalInfo;
  insurance: { provider: string; policy_number: string | null; title: string }[];
  updated_at: string | null;
};

export type InviteInfo = {
  vault_name: string;
  invited_by: string;
  role: string;
  email: string;
};

const withCreds: RequestInit = { credentials: "include" };
const post = (body: unknown): RequestInit => ({
  method: "POST",
  ...withCreds,
  body: JSON.stringify(body),
});

export const getMembers = () => apiFetch<MembersResponse>("/api/v1/family/members", withCreds);

export const createInvite = (email: string, role: string) =>
  apiFetch<PendingInvite>("/api/v1/family/invites", post({ email, role }));

export const patchMember = (
  membershipId: string,
  patch: { role?: string; category_access?: Record<string, string> },
) =>
  apiFetch<Member>(`/api/v1/family/members/${membershipId}`, {
    method: "PATCH",
    ...withCreds,
    body: JSON.stringify(patch),
  });

export const removeMember = (membershipId: string) =>
  fetch(`${API_BASE_URL}/api/v1/family/members/${membershipId}`, {
    method: "DELETE",
    ...withCreds,
  });

export const getInviteInfo = (token: string) =>
  apiFetch<InviteInfo>(`/api/v1/family/invites/${token}`);

export const acceptInvite = (token: string) =>
  fetch(`${API_BASE_URL}/api/v1/family/invites/${token}/accept`, {
    method: "POST",
    ...withCreds,
  });

export const getBinder = () => apiFetch<Binder>("/api/v1/emergency", withCreds);

export const updateBinder = (input: {
  contacts: Contact[];
  medical: MedicalInfo;
  delegates: Delegate[];
}) =>
  apiFetch<Binder>("/api/v1/emergency", {
    method: "PUT",
    ...withCreds,
    body: JSON.stringify(input),
  });

export const issueQr = (pin: string) =>
  apiFetch<{ token: string; issued_at: string }>("/api/v1/emergency/qr", post({ pin }));

export const revokeQr = () =>
  fetch(`${API_BASE_URL}/api/v1/emergency/qr/revoke`, { method: "POST", ...withCreds });

export const accessBinder = (token: string, pin: string) =>
  apiFetch<PublicBinder>(`/api/v1/emergency/access/${token}`, post({ pin }));
