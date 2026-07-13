export type VaultSummary = {
  id: string;
  name: string;
  plan: "free" | "premium" | "family";
  role: "owner" | "admin" | "member" | "emergency";
};

export type Me = {
  id: string;
  email: string;
  name: string;
  vaults: VaultSummary[];
};
