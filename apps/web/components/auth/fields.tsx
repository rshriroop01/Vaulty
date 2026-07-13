"use client";

/** Shared input styling per the Ledger spec: 1px #DFE4E9, radius 8, 11px 14px padding,
 *  focus ring 1.5px ink. */
export function Field({
  label,
  labelRight,
  ...input
}: { label: string; labelRight?: React.ReactNode } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <div className="mb-1.5 flex justify-between">
        <label htmlFor={input.id} className="text-[12px] font-semibold text-[#4c5561]">
          {label}
        </label>
        {labelRight}
      </div>
      <input
        {...input}
        className="w-full rounded-control border border-input-border bg-card px-3.5 py-[11px] text-[13.5px] text-text outline-none placeholder:text-text-faint focus:border-[1.5px] focus:border-ink"
      />
    </div>
  );
}

export function PrimaryButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className="w-full rounded-control bg-ink py-3 text-center text-[13.5px] font-semibold text-white transition-opacity hover:opacity-95 disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function GoogleButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-center gap-[9px] rounded-control border border-input-border bg-card p-[11px] text-[13px] font-medium hover:bg-[#f8fafc]"
    >
      <span
        className="h-3.5 w-3.5 rounded-full"
        style={{
          background: "conic-gradient(#4285f4 0 25%, #34a853 0 50%, #fbbc05 0 75%, #ea4335 0)",
        }}
      />
      Continue with Google
    </button>
  );
}

export function OrDivider() {
  return (
    <div className="my-3.5 flex items-center gap-2.5 text-[11px] text-[#b0b8c1]">
      <span className="h-px flex-1 bg-hairline" />
      OR
      <span className="h-px flex-1 bg-hairline" />
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="mb-3.5 rounded-tag bg-urgent-bg px-[9px] py-[5px] text-[12px] font-medium text-urgent">
      {message}
    </div>
  );
}
