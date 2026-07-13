/** Category accents from the approved 1a design data. */
export const CATEGORIES = [
  { key: "receipts", label: "Receipts", color: "#3b6fe0" },
  { key: "warranties", label: "Warranties", color: "#1f8577" },
  { key: "insurance", label: "Insurance", color: "#e26a3c" },
  { key: "medical", label: "Medical", color: "#946200" },
  { key: "ids_legal", label: "IDs & Legal", color: "#6a5acd" },
  { key: "home", label: "Home", color: "#4c5561" },
] as const;

export function categoryLabel(key: string): string {
  return CATEGORIES.find((c) => c.key === key)?.label ?? "Other";
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
